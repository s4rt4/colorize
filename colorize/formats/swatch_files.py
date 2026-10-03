"""Binary/text swatch files shared with other apps: Adobe Swatch Exchange and GIMP palettes.

ASE layout (big-endian): "ASEF", version 1.0, block count, then blocks of
``u16 type, u32 length, payload``. Types: 0xC001 group start, 0xC002 group end,
0x0001 color entry. A color entry is ``u16 name length (UTF-16 units incl. NUL),
UTF-16BE name, 4-char model, float32 values, u16 kind`` (0 global, 1 spot, 2 normal).
"""

import struct

from colorize.core.color import hex_to_rgb, normalize_hex, rgb_to_hex

ASE_SIGNATURE = b"ASEF"
_GROUP_START, _GROUP_END, _COLOR = 0xC001, 0xC002, 0x0001
_KIND_NORMAL = 2


class SwatchFileError(ValueError):
    pass


# --------------------------------------------------------------------- ASE


def _ase_name(text: str) -> bytes:
    encoded = text.encode("utf-16-be") + b"\0\0"
    return struct.pack(">H", len(encoded) // 2) + encoded


def _block(kind: int, payload: bytes) -> bytes:
    return struct.pack(">HI", kind, len(payload)) + payload


def write_ase(name: str, colors) -> bytes:
    """One group named after the palette; swatches are named by their hex value."""
    blocks = [_block(_GROUP_START, _ase_name(name))]
    for hex_color in colors:
        hex_color = normalize_hex(hex_color)
        r, g, b = (c / 255 for c in hex_to_rgb(hex_color))
        payload = _ase_name(hex_color) + b"RGB " + struct.pack(">fffH", r, g, b, _KIND_NORMAL)
        blocks.append(_block(_COLOR, payload))
    blocks.append(_block(_GROUP_END, b""))
    return ASE_SIGNATURE + struct.pack(">HHI", 1, 0, len(blocks)) + b"".join(blocks)


def _read_name(data: bytes, offset: int) -> tuple[str, int]:
    (units,) = struct.unpack_from(">H", data, offset)
    start = offset + 2
    end = start + units * 2
    return data[start:end].decode("utf-16-be").rstrip("\0"), end


def _model_to_hex(model: bytes, values: tuple) -> str:
    if model == b"RGB ":
        return rgb_to_hex(*(round(min(max(v, 0.0), 1.0) * 255) for v in values))
    if model == b"Gray":
        level = round(min(max(values[0], 0.0), 1.0) * 255)
        return rgb_to_hex(level, level, level)
    if model == b"CMYK":  # device CMYK has no colorimetric meaning without a profile: naive conversion
        c, m, y, k = values
        return rgb_to_hex(*(round(255 * (1 - min(1.0, v * (1 - k) + k))) for v in (c, m, y)))
    if model == b"LAB ":  # Adobe stores L 0-1 (x100) and a/b as-is, D50
        lightness, a, b = values
        from coloraide import Color  # slow import; Lab swatches are rare

        # coloraide's "lab" space is CIE Lab with a D50 white, as ASE uses.
        srgb = Color("lab", [lightness * 100, a, b]).convert("srgb").fit("srgb")
        return srgb.to_string(hex=True).upper()
    raise SwatchFileError(f"unsupported ASE color model {model!r}")


def read_ase(data: bytes) -> tuple[str, list[str]]:
    """Returns (first group name or "", colors). Groups are flattened."""
    name, entries = read_ase_named(data)
    return name, [hex_color for _, hex_color in entries]


def read_ase_named(data: bytes) -> tuple[str, list[tuple[str, str]]]:
    """(first group name or "", [(swatch name, hex)]). Groups are flattened."""
    if data[:4] != ASE_SIGNATURE:
        raise SwatchFileError("not an Adobe Swatch Exchange file")
    try:
        (count,) = struct.unpack_from(">I", data, 8)
        offset, name, colors = 12, "", []
        for _ in range(count):
            kind, length = struct.unpack_from(">HI", data, offset)
            offset += 6
            body_end = offset + length
            if kind == _GROUP_START and not name:
                name, _ = _read_name(data, offset)
            elif kind == _COLOR:
                swatch_name, pos = _read_name(data, offset)
                model = data[pos : pos + 4]
                pos += 4
                n = {b"RGB ": 3, b"LAB ": 3, b"CMYK": 4, b"Gray": 1}.get(model)
                if n is None:
                    raise SwatchFileError(f"unsupported ASE color model {model!r}")
                values = struct.unpack_from(f">{n}f", data, pos)
                colors.append((swatch_name, _model_to_hex(model, values)))
            offset = body_end
    except struct.error as exc:
        raise SwatchFileError("truncated or damaged ASE file") from exc
    return name, colors


# --------------------------------------------------------------------- GPL


def write_gpl(name: str, colors, columns: int = 8) -> str:
    lines = ["GIMP Palette", f"Name: {name}", f"Columns: {columns}", "#"]
    for hex_color in colors:
        r, g, b = hex_to_rgb(hex_color)
        lines.append(f"{r:3d} {g:3d} {b:3d}\t{normalize_hex(hex_color)}")
    return "\n".join(lines) + "\n"


def read_gpl(text: str) -> tuple[str, list[str]]:
    name, entries = read_gpl_named(text)
    return name, [hex_color for _, hex_color in entries]


def read_gpl_named(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Like read_gpl, keeping each color's name (the text after R G B; may be empty)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "GIMP Palette":
        raise SwatchFileError("not a GIMP palette (first line must be 'GIMP Palette')")
    name, colors = "", []
    for number, raw in enumerate(lines[1:], start=2):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("Name:"):
            name = line[5:].strip()
            continue
        if line.startswith("Columns:"):
            continue
        parts = line.split(None, 3)
        try:
            r, g, b = (int(p) for p in parts[:3])
            colors.append((parts[3].strip() if len(parts) > 3 else "", rgb_to_hex(r, g, b)))
        except ValueError as exc:
            raise SwatchFileError(f"line {number}: expected 'R G B [name]'") from exc
    return name, colors
