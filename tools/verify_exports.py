"""Check exports with the real consumers (needs Node.js/npm and network for the first run).

    python tools/verify_exports.py

- Tailwind v4 (@theme) compiled by the official @tailwindcss/cli: utilities exist.
- Tailwind v3 config loaded by tailwindcss@3: utilities exist with our colors.
- CSS variables parsed strictly by Lightning CSS.
- Design tokens built by Style Dictionary v5 (DTCG color objects).
- ASE parsed by the independent `swatch` Python package.
Work happens in a temp folder; nothing is installed into the project.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from colorize.formats.swatch_files import write_ase  # noqa: E402
from colorize.formats.text_formats import css_variables, design_tokens, tailwind_v3, tailwind_v4  # noqa: E402

NAME, PREFIX = "Brand", "brand"
COLORS = ["#1F3A5F", "#F2C14E", "#4D9078"]
NPM = shutil.which("npm") or "npm"
NPX = shutil.which("npx") or "npx"
results: list[tuple[str, bool, str]] = []


def run(cmd, cwd) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def npm_install(folder: Path, *packages: str) -> None:
    run([NPM, "init", "-y"], folder)
    proc = run([NPM, "install", "--no-audit", "--no-fund", "--silent", *packages], folder)
    if proc.returncode:
        raise RuntimeError(proc.stderr[-800:])


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append((label, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {label}  {detail}")


def tailwind4(base: Path) -> None:
    folder = base / "tw4"
    folder.mkdir()
    npm_install(folder, "tailwindcss@4", "@tailwindcss/cli@4")
    (folder / "index.html").write_text('<div class="bg-brand-1 text-brand-2 border-brand-3"></div>', encoding="utf-8")
    for syntax in ("hex", "oklch"):
        (folder / "input.css").write_text('@import "tailwindcss";\n' + tailwind_v4(NAME, COLORS, PREFIX, syntax), encoding="utf-8")
        proc = run([NPX, "@tailwindcss/cli", "-i", "input.css", "-o", "out.css"], folder)
        out = (folder / "out.css").read_text(encoding="utf-8") if (folder / "out.css").exists() else ""
        ok = proc.returncode == 0 and ".bg-brand-1" in out and "--color-brand-1" in out and ".text-brand-2" in out
        check(f"Tailwind v4 @theme ({syntax})", ok, "" if ok else proc.stderr[-400:])


def tailwind3(base: Path) -> None:
    folder = base / "tw3"
    folder.mkdir()
    npm_install(folder, "tailwindcss@3")
    (folder / "index.html").write_text('<div class="bg-brand-1 text-brand-2"></div>', encoding="utf-8")
    (folder / "colorize.config.js").write_text(tailwind_v3(NAME, COLORS, PREFIX), encoding="utf-8")
    # Our export is a whole config; a project merges it. Add `content` the way a user would.
    (folder / "tailwind.config.js").write_text(
        "const c = require('./colorize.config.js');\nc.content = ['./index.html'];\nmodule.exports = c;\n", encoding="utf-8"
    )
    (folder / "input.css").write_text("@tailwind utilities;\n", encoding="utf-8")
    proc = run([NPX, "tailwindcss", "-c", "tailwind.config.js", "-i", "input.css", "-o", "out.css"], folder)
    out = (folder / "out.css").read_text(encoding="utf-8") if (folder / "out.css").exists() else ""
    ok = proc.returncode == 0 and ".bg-brand-1" in out and "rgb(31 58 95" in out
    check("Tailwind v3 config", ok, "" if ok else (proc.stderr or out)[-400:])


def lightning_css(base: Path) -> None:
    folder = base / "lcss"
    folder.mkdir()
    npm_install(folder, "lightningcss-cli")
    for syntax in ("hex", "rgb", "hsl", "oklch"):
        (folder / "in.css").write_text(css_variables(NAME, COLORS, PREFIX, syntax), encoding="utf-8")
        proc = run([NPX, "lightningcss", "--minify", "in.css"], folder)
        ok = proc.returncode == 0 and "--brand-1:" in proc.stdout
        check(f"CSS variables parse ({syntax})", ok, "" if ok else proc.stderr[-400:])


def style_dictionary(base: Path) -> None:
    folder = base / "sd"
    folder.mkdir()
    npm_install(folder, "style-dictionary@5")
    (folder / "tokens.json").write_text(design_tokens(NAME, COLORS, PREFIX), encoding="utf-8")
    config = {
        "source": ["tokens.json"],
        "platforms": {"css": {"transformGroup": "css", "buildPath": "build/", "files": [{"destination": "vars.css", "format": "css/variables"}]}},
    }
    (folder / "config.json").write_text(json.dumps(config), encoding="utf-8")
    (folder / "package.json").write_text(json.dumps({"type": "module"}), encoding="utf-8")
    proc = run([NPX, "style-dictionary", "build", "--config", "config.json"], folder)
    out_file = folder / "build" / "vars.css"
    out = out_file.read_text(encoding="utf-8") if out_file.exists() else ""
    ok = proc.returncode == 0 and "--brand-1: #1f3a5f" in out.lower()
    check("Design tokens (Style Dictionary 5)", ok, out.strip().replace("\n", " ")[:200] if not ok else "")


def ase_swatch(base: Path) -> None:
    folder = base / "ase"
    folder.mkdir()
    venv = folder / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    py = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    proc = run([str(py), "-m", "pip", "install", "-q", "swatch"], folder)
    if proc.returncode:
        check("ASE (swatch package)", False, proc.stderr[-400:])
        return
    path = folder / "brand.ase"
    path.write_bytes(write_ase(NAME, COLORS))
    script = (
        "import json, swatch; data = swatch.parse(r'%s'); print(json.dumps(data))" % path
    )
    proc = run([str(py), "-c", script], folder)
    try:
        parsed = json.loads(proc.stdout)
        group = parsed[0]
        names = [s["name"] for s in group["swatches"]]
        values = [s["data"]["values"] for s in group["swatches"]]
        ok = group["name"] == NAME and names == COLORS and all(
            [round(v * 255) for v in vals] == [int(c[i : i + 2], 16) for i in (1, 3, 5)] for vals, c in zip(values, COLORS)
        )
        check("ASE (swatch package)", ok, "" if ok else proc.stdout[:300])
    except (ValueError, KeyError, IndexError):
        check("ASE (swatch package)", False, (proc.stderr or proc.stdout)[-400:])


def main() -> int:
    base = Path(tempfile.mkdtemp(prefix="colorize-verify-"))
    for step in (tailwind4, tailwind3, lightning_css, style_dictionary, ase_swatch):
        try:
            step(base)
        except Exception as exc:  # report and keep going: each check is independent
            check(step.__name__, False, str(exc)[-400:])
    shutil.rmtree(base, ignore_errors=True)
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
