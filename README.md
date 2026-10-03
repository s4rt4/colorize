# Colorize

Offline desktop color manager with an Adobe-style interface. Plan: `colorize-plan.md`.

## Setup

`python` on this machine's PATH is Inkscape's bundled interpreter, so create the venv
with the Python launcher:

```
py -3.14 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## Run

```
.venv\Scripts\python -m colorize
```

## Test

```
.venv\Scripts\python -m pytest
```

UI tests run headless (`QT_QPA_PLATFORM=offscreen`, set in `tests/conftest.py`).

## Layout

```
colorize/
  core/      color math, no Qt: hex/OKLCH, harmony rules, sRGB gamut mapping,
             NumPy OKLab renderer for per-pixel fields
  model/     Palette, Document (+ QUndoStack), AppState, HarmonyModel, undoable commands
  ui/        shell, panels, document canvas, preferences
    themes/  tokens (dark / gray / light), generated QSS, recolored SVG icons
    fonts/   Source Sans 3 (SIL OFL, license alongside)
  formats/   palette files: native JSON (M1); ASE, GPL, CSS, Tailwind, tokens (M4)
  storage/   SQLite (M4)
```

## Color decisions

- Harmony wheel: angle = OKLCH hue, radius = chroma, at the base color's lightness.
  The dimmed part of the wheel is outside sRGB.
- Out-of-gamut colors are mapped with CSS Color 4 style chroma reduction
  (coloraide `oklch-chroma`) and flagged: dashed handles, ⚠ on swatches, a warning in
  the color picker (click it to snap to the gamut edge).
- Hue rules keep lightness and chroma; monochromatic steps lightness by 0.12.

## Palette files

`File › Save` writes UTF-8 JSON:

```json
{"format": "colorize.palette", "version": 1, "name": "Brand", "colors": [{"hex": "#3D6A9E"}]}
```

Rules: `core/` stays Qt-free; the UI never edits a Palette directly, only through
`Document` methods that push undo commands.

## Shortcuts

| Key | Action |
|---|---|
| V I W E C B H Z | Select, Eyedropper, Harmony, Extract, Contrast, Color Blindness, Hand, Zoom |
| Space (hold) | Temporary Hand tool |
| X / D | Swap / default foreground and background |
| Tab | Show/hide all panels and bars |
| Shift+F1 / Shift+F2 | Darker / lighter interface |
| Ctrl+K | Preferences |
| Ctrl+Z, Ctrl+Shift+Z | Undo, redo |
| Ctrl+= / Ctrl+- / Ctrl+0 / Ctrl+1 | Zoom in / out / fit / 100% |
| Del | Delete selected swatch |

Settings (theme, window, panel layout, custom workspaces) are stored in
`%APPDATA%\Colorize\Colorize.ini`.

## License

Code: MIT, see `LICENSE`. The bundled Source Sans 3 font is licensed separately under the
SIL Open Font License (`colorize/ui/fonts/OFL-SourceSans3.txt`).
