"""Builds a minimal ICC v4 RGB matrix/TRC display profile, so tests can embed a real
Display P3 profile without shipping a binary file."""

import struct

from coloraide import Color

_D50 = (0.9642, 1.0, 0.8249)
# sRGB transfer curve as ICC parametricCurveType function 3: Y = (aX+b)^g  if X >= d, else cX
_SRGB_CURVE = (2.4, 1 / 1.055, 0.055 / 1.055, 1 / 12.92, 0.04045)


def _s15(value: float) -> bytes:
    return struct.pack(">i", round(value * 65536))


def _xyz(x, y, z) -> bytes:
    return b"XYZ " + b"\0" * 4 + _s15(x) + _s15(y) + _s15(z)


def _para() -> bytes:
    return b"para" + b"\0" * 4 + struct.pack(">HH", 3, 0) + b"".join(_s15(v) for v in _SRGB_CURVE)


def _mluc(text: str) -> bytes:
    encoded = text.encode("utf-16-be")
    return b"mluc" + b"\0" * 4 + struct.pack(">II", 1, 12) + b"enUS" + struct.pack(">II", len(encoded), 28) + encoded


def _pad(data: bytes) -> bytes:
    return data + b"\0" * (-len(data) % 4)


def matrix_profile(space: str, description: str) -> bytes:
    """Profile for a coloraide RGB space (e.g. 'display-p3') using the sRGB curve."""
    columns = [Color(space, rgb).convert("xyz-d50").coords() for rgb in ([1, 0, 0], [0, 1, 0], [0, 0, 1])]
    curve = _para()
    tags = [
        (b"desc", _mluc(description)),
        (b"cprt", _mluc("No copyright, test profile")),
        (b"wtpt", _xyz(*_D50)),
        (b"rXYZ", _xyz(*columns[0])),
        (b"gXYZ", _xyz(*columns[1])),
        (b"bXYZ", _xyz(*columns[2])),
        (b"rTRC", curve),
        (b"gTRC", curve),
        (b"bTRC", curve),
    ]
    offset = 128 + 4 + 12 * len(tags)
    table, body = b"", b""
    for signature, data in tags:
        data = _pad(data)
        table += signature + struct.pack(">II", offset + len(body), len(data))
        body += data
    size = offset + len(body)
    header = (
        struct.pack(">I", size)
        + b"lcms"
        + struct.pack(">I", 0x04300000)
        + b"mntrRGB XYZ "
        + struct.pack(">6H", 2026, 1, 1, 0, 0, 0)
        + b"acsp"
        + b"\0" * 4  # platform
        + b"\0" * 4  # flags
        + b"\0" * 8  # manufacturer, model
        + b"\0" * 8  # attributes
        + struct.pack(">I", 0)  # perceptual intent
        + _xyz(*_D50)[8:]
        + b"\0" * 4  # creator
        + b"\0" * 16  # profile ID
        + b"\0" * 28
    )
    assert len(header) == 128
    return header + struct.pack(">I", len(tags)) + table + body
