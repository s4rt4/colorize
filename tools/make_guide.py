"""Build the Indonesian user guide: docs/Panduan-Colorize.pdf

    python tools/make_guide.py            # screenshots (if missing) + PDF
    python tools/make_guide.py --shots    # retake the screenshots first
    python tools/make_guide.py --lengkap  # full edition: + colour knowledge for
                                          # designers, project recipes, appendices
                                          # (docs/Panduan-Colorize-Lengkap.pdf)

Needs reportlab (pip install reportlab). Fonts: Source Sans 3 / Source Code Pro
(SIL OFL), downloaded into build/guide/fonts on first run. Colour samples in the
diagrams are computed with Colorize's own colour engine, so they match the app.
"""

import colorsys
import math
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image as PILImage  # noqa: E402
from PIL import ImageDraw, ImageFont  # noqa: E402
from reportlab.graphics.shapes import Circle, Drawing, Line, Polygon, Rect, String, Wedge  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER, TA_LEFT  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    BaseDocTemplate,
    CondPageBreak,
    Frame,
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents  # noqa: E402

from colorize import __version__  # noqa: E402
from colorize.core.cmyk import SYSTEM_PROFILE_DIR, CmykProofer  # noqa: E402
from colorize.core.color import hex_to_rgb, to_oklch  # noqa: E402
from colorize.core.contrast import contrast_ratio, format_ratio  # noqa: E402
from colorize.core.cvd import simulate_hex  # noqa: E402
from colorize.core.gamut import map_to_srgb  # noqa: E402
from colorize.core.harmony import RULE_LABELS, RULES, harmony  # noqa: E402
from colorize.core.mix import gradient  # noqa: E402
from colorize.core.scale import tint_shade_scale  # noqa: E402

BUILD = ROOT / "build" / "guide"
SHOTS = BUILD / "shots"
FONTS = BUILD / "fonts"
FULL = "--lengkap" in sys.argv
OUT = ROOT / "docs" / ("Panduan-Colorize-Lengkap.pdf" if FULL else "Panduan-Colorize.pdf")
LEVEL = 1 if FULL else 0  # TOC level of a chapter; the full edition groups chapters into parts

FONT_FILES = {
    "Sans": "SourceSans3-Regular.ttf",
    "Sans-It": "SourceSans3-It.ttf",
    "Sans-Semi": "SourceSans3-Semibold.ttf",
    "Sans-Bold": "SourceSans3-Bold.ttf",
    "Sans-Light": "SourceSans3-Light.ttf",
    "Mono": "SourceCodePro-Regular.ttf",
}
FONT_URLS = {
    "SourceCodePro-Regular.ttf": "https://github.com/adobe-fonts/source-code-pro/raw/release/TTF/SourceCodePro-Regular.ttf",
}

INK = colors.HexColor("#1F1F1F")
MUTED = colors.HexColor("#5F6368")
ACCENT = colors.HexColor("#1473E6")
RULE = colors.HexColor("#D9DDE3")
HEADER_BG = colors.HexColor("#EAF2FD")
BOXES = {
    "tip": ("Tips", colors.HexColor("#E8F5EE"), colors.HexColor("#2D9D78")),
    "note": ("Catatan", colors.HexColor("#FFF6E0"), colors.HexColor("#D9A21B")),
    "term": ("Istilah", colors.HexColor("#EAF2FD"), colors.HexColor("#1473E6")),
    "warn": ("Perhatian", colors.HexColor("#FDECEC"), colors.HexColor("#C9252D")),
}

PAGE_W, PAGE_H = A4
MARGIN = 2 * cm
TEXT_W = PAGE_W - 2 * MARGIN


# --------------------------------------------------------------------- setup


def ensure_fonts() -> None:
    FONTS.mkdir(parents=True, exist_ok=True)
    for name, file in FONT_FILES.items():
        path = FONTS / file
        if not path.exists():
            url = FONT_URLS.get(file, f"https://github.com/adobe-fonts/source-sans/raw/release/TTF/{file}")
            urllib.request.urlretrieve(url, path)
        pdfmetrics.registerFont(TTFont(name, str(path)))
    pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="Sans-Bold", italic="Sans-It", boldItalic="Sans-Bold")


def ensure_shots(force: bool) -> None:
    if force or not (SHOTS / "overview.png").exists():
        subprocess.run([sys.executable, str(ROOT / "tools" / "guide_shots.py"), str(SHOTS)], check=True)


# -------------------------------------------------------------------- styles

S = {}


def make_styles() -> None:
    base = dict(fontName="Sans", fontSize=10.5, leading=15.5, textColor=INK)
    S["body"] = ParagraphStyle("body", **base, spaceAfter=7)
    S["lead"] = ParagraphStyle("lead", **{**base, "fontSize": 12, "leading": 17.5, "textColor": colors.HexColor("#333333")}, spaceAfter=10)
    S["small"] = ParagraphStyle("small", **{**base, "fontSize": 9.5, "leading": 13.5})
    S["cell"] = ParagraphStyle("cell", **{**base, "fontSize": 9.5, "leading": 13})
    S["cellb"] = ParagraphStyle("cellb", **{**base, "fontSize": 9.5, "leading": 13, "fontName": "Sans-Semi"})
    S["caption"] = ParagraphStyle(
        "caption", fontName="Sans-It", fontSize=9, leading=12.5, textColor=MUTED, alignment=TA_CENTER, spaceBefore=4, spaceAfter=12
    )
    S["chapno"] = ParagraphStyle("chapno", fontName="Sans-Semi", fontSize=11, leading=14, textColor=ACCENT, spaceAfter=2)
    S["h1"] = ParagraphStyle("h1", fontName="Sans-Bold", fontSize=24, leading=29, textColor=INK, spaceAfter=12)
    S["h2"] = ParagraphStyle("h2", fontName="Sans-Bold", fontSize=14.5, leading=19, textColor=INK, spaceBefore=12, spaceAfter=6)
    S["h3"] = ParagraphStyle("h3", fontName="Sans-Semi", fontSize=11.5, leading=15.5, textColor=INK, spaceBefore=6, spaceAfter=3)
    S["boxtitle"] = ParagraphStyle("boxtitle", fontName="Sans-Bold", fontSize=10, leading=14, spaceAfter=2)
    S["boxbody"] = ParagraphStyle("boxbody", **{**base, "fontSize": 10, "leading": 14.5}, spaceAfter=3)
    S["toc0"] = ParagraphStyle("toc0", fontName="Sans-Semi", fontSize=11, leading=17, leftIndent=0, textColor=INK)
    S["toc1"] = ParagraphStyle("toc1", fontName="Sans", fontSize=9.5, leading=13.5, leftIndent=16, textColor=MUTED)
    S["partno"] = ParagraphStyle("partno", fontName="Sans-Semi", fontSize=13, leading=17, textColor=ACCENT, spaceAfter=6)
    S["part"] = ParagraphStyle("part", fontName="Sans-Bold", fontSize=34, leading=40, textColor=INK, spaceAfter=18)
    S["partblurb"] = ParagraphStyle("partblurb", fontName="Sans", fontSize=12.5, leading=19, textColor=MUTED)
    S["tocpart"] = ParagraphStyle("tocpart", fontName="Sans-Bold", fontSize=12, leading=18, textColor=ACCENT,
                                  spaceBefore=10)
    S["tochead"] = ParagraphStyle("tochead", fontName="Sans-Bold", fontSize=24, leading=29, spaceAfter=16)


# ---------------------------------------------------------------- builders

story: list = []


def P(text: str, style: str = "body") -> None:
    story.append(Paragraph(text, S[style]))


def heading(text: str, level: int) -> Paragraph:
    para = Paragraph(text, S["h1" if level == 0 else "h2"])
    para.toc_level = level + LEVEL
    para.running_title = level == 0
    return para


def _page_break() -> None:
    # a trailing spacer that spills onto a fresh page would leave that page blank
    while story and isinstance(story[-1], Spacer):
        story.pop()
    story.append(PageBreak())


def part(label: str, title: str, blurb: str) -> None:
    """A divider page opening one part of the full edition."""
    _page_break()
    story.append(Spacer(1, 6 * cm))
    story.append(Paragraph(label, S["partno"]))
    para = Paragraph(title, S["part"])
    para.toc_level = 0
    para.running_title = True
    story.append(para)
    story.append(Paragraph(blurb, S["partblurb"]))


_chapter = [0]


def chapter(title: str) -> None:
    _chapter[0] += 1
    _page_break()
    story.append(Paragraph(f"BAB {_chapter[0]}", S["chapno"]))
    story.append(heading(title, 0))


def section(title: str) -> None:
    story.append(CondPageBreak(4 * cm))
    story.append(heading(title, 1))


def sub(title: str) -> None:
    story.append(Paragraph(title, S["h3"]))


def bullets(items, style: str = "body") -> None:
    story.append(
        ListFlowable(
            [ListItem(Paragraph(t, S[style]), leftIndent=14, value="circle") for t in items],
            bulletType="bullet",
            start="•",
            bulletFontName="Sans",
            bulletColor=ACCENT,
            leftIndent=14,
            spaceAfter=6,
        )
    )


def steps(items) -> None:
    story.append(
        ListFlowable(
            [ListItem(Paragraph(t, S["body"]), leftIndent=18) for t in items],
            bulletType="1",
            bulletFontName="Sans-Bold",
            bulletColor=ACCENT,
            leftIndent=18,
            spaceAfter=6,
        )
    )


def box(kind: str, *paras: str, title: str | None = None) -> None:
    label, bg, edge = BOXES[kind]
    title_style = ParagraphStyle("bt", parent=S["boxtitle"], textColor=edge)
    content = [Paragraph(title or label, title_style)] + [Paragraph(t, S["boxbody"]) for t in paras]
    table = Table([[content]], colWidths=[TEXT_W])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), bg),
                ("LINEBEFORE", (0, 0), (0, -1), 3, edge),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(Spacer(1, 4))
    story.append(KeepTogether(table))
    story.append(Spacer(1, 8))


def table(rows, widths, header: bool = True) -> None:
    data = []
    for r, row in enumerate(rows):
        style = "cellb" if header and r == 0 else "cell"
        data.append([c if not isinstance(c, str) else Paragraph(c, S[style]) for c in row])
    t = Table(data, colWidths=[w * TEXT_W for w in widths], repeatRows=1 if header else 0)
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        commands += [("BACKGROUND", (0, 0), (-1, 0), HEADER_BG), ("LINEBELOW", (0, 0), (-1, 0), 1, ACCENT)]
    t.setStyle(TableStyle(commands))
    story.append(t)
    story.append(Spacer(1, 10))


def _trim_bottom(path: Path) -> Path:
    """Panels are captured at full dock height; drop the empty rows below their content."""
    import numpy as np

    with PILImage.open(path) as im:
        rgb = np.asarray(im.convert("RGB")).astype(int)
    blank = np.abs(rgb - rgb[-1, rgb.shape[1] // 2]).max(axis=(1, 2)) <= 3
    rows = np.nonzero(~blank)[0]
    bottom = min(rgb.shape[0], (rows[-1] if rows.size else rgb.shape[0]) + 24)
    out = BUILD / "trimmed" / path.name
    out.parent.mkdir(parents=True, exist_ok=True)
    PILImage.fromarray(rgb[:bottom].astype("uint8")).save(out)
    return out


def _image(name: str, width: float) -> Image:
    path = name if isinstance(name, Path) else SHOTS / f"{name}.png"
    if not isinstance(name, Path) and name.startswith("panel-"):
        path = _trim_bottom(path)
    with PILImage.open(path) as im:
        w, h = im.size
    return Image(str(path), width=width, height=width * h / w)


def figure(name, caption: str, width: float = 1.0, border: bool = True) -> None:
    img = _image(name, width * TEXT_W)
    t = Table([[img]], colWidths=[width * TEXT_W + 2])
    if border:
        t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, RULE), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    story.append(KeepTogether([t, Paragraph(caption, S["caption"])]))


def figures(items, width: float = 0.47) -> None:
    """Images side by side: [(name, caption), ...]."""
    cells = [[_image(name, width * TEXT_W) for name, _ in items], [Paragraph(c, S["caption"]) for _, c in items]]
    t = Table(cells, colWidths=[TEXT_W / len(items)] * len(items))
    t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, 0), "TOP")]))
    story.append(KeepTogether(t))
    story.append(Spacer(1, 6))


def drawing(d: Drawing, caption: str) -> None:
    t = Table([[d]], colWidths=[TEXT_W])
    t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    story.append(KeepTogether([t, Paragraph(caption, S["caption"])]))


def K(keys: str) -> str:
    """Keyboard keys in running text."""
    return f'<font name="Sans-Semi" color="#1473E6">{keys}</font>'


def M(path: str) -> str:
    """A menu path."""
    return f"<b>{path}</b>"


# ------------------------------------------------------------ vector diagrams


def hexc(h: str):
    return colors.HexColor(h)


def chip_row(d: Drawing, x: float, y: float, hexes, size: float = 26, gap: float = 4, labels=None, label_size=7.5):
    for i, h in enumerate(hexes):
        d.add(Rect(x + i * (size + gap), y, size, size, fillColor=hexc(h), strokeColor=hexc("#C8CCD2"), strokeWidth=0.5))
        if labels:
            d.add(String(x + i * (size + gap) + size / 2, y - 10, labels[i], fontName="Sans", fontSize=label_size,
                         fillColor=MUTED, textAnchor="middle"))


def workflow_diagram() -> Drawing:
    d = Drawing(TEXT_W, 96)
    steps_ = [("Ide atau foto", "warna awal"), ("Palet", "kumpulkan & susun"), ("Periksa", "kontras, buta warna, cetak"),
              ("Pakai", "ekspor & mockup")]
    w, gap = 108, (TEXT_W - 4 * 108) / 3
    for i, (name, note) in enumerate(steps_):
        x = i * (w + gap)
        accent = i == 1
        d.add(Rect(x, 24, w, 56, rx=8, ry=8, fillColor=HEADER_BG if accent else colors.white,
                   strokeColor=ACCENT if accent else hexc("#9AA3AD"), strokeWidth=1.5 if accent else 1))
        d.add(String(x + w / 2, 58, name, fontName="Sans-Bold", fontSize=11, fillColor=INK, textAnchor="middle"))
        d.add(String(x + w / 2, 40, note, fontName="Sans", fontSize=8, fillColor=MUTED, textAnchor="middle"))
        if i < 3:
            x1, x2 = x + w + 4, x + w + gap - 4
            d.add(Line(x1, 52, x2 - 4, 52, strokeColor=hexc("#9AA3AD"), strokeWidth=1.2))
            d.add(Polygon([x2, 52, x2 - 7, 56, x2 - 7, 48], fillColor=hexc("#9AA3AD"), strokeColor=None))
    d.add(String(0, 6, "Alur kerja umum di Colorize", fontName="Sans-It", fontSize=8, fillColor=MUTED))
    return d


def hex_anatomy() -> Drawing:
    hex_color = "#3D6A9E"
    r, g, b = hex_to_rgb(hex_color)
    d = Drawing(TEXT_W, 120)
    d.add(Rect(0, 20, 90, 90, rx=6, ry=6, fillColor=hexc(hex_color), strokeColor=None))
    x = 120
    d.add(String(x, 80, "#", fontName="Mono", fontSize=26, fillColor=MUTED))
    parts = [("3D", r, "#D62728", "Merah"), ("6A", g, "#2CA02C", "Hijau"), ("9E", b, "#1F77B4", "Biru")]
    for i, (text, value, c, name) in enumerate(parts):
        px = x + 22 + i * 52
        d.add(String(px, 80, text, fontName="Mono", fontSize=26, fillColor=hexc(c)))
        d.add(String(px + 16, 64, f"{name}", fontName="Sans", fontSize=8.5, fillColor=MUTED, textAnchor="middle"))
        d.add(String(px + 16, 52, f"= {value}", fontName="Sans-Semi", fontSize=9, fillColor=INK, textAnchor="middle"))
    bx = 300
    for i, (_, value, c, name) in enumerate(parts):
        y = 88 - i * 26
        d.add(String(bx, y + 3, name, fontName="Sans", fontSize=9, fillColor=INK))
        d.add(Rect(bx + 40, y, 140, 12, fillColor=hexc("#EEF0F3"), strokeColor=None))
        d.add(Rect(bx + 40, y, 140 * value / 255, 12, fillColor=hexc(c), strokeColor=None))
        d.add(String(bx + 186, y + 2, f"{value} / 255", fontName="Sans", fontSize=8.5, fillColor=MUTED))
    d.add(String(0, 4, "Kode HEX adalah tiga angka (merah, hijau, biru) yang ditulis dalam heksadesimal.",
                 fontName="Sans-It", fontSize=8, fillColor=MUTED))
    return d


def oklch_strips() -> Drawing:
    d = Drawing(TEXT_W, 168)
    rows = [
        ("Lightness (terang)", [map_to_srgb(v / 10, 0.07, 250).hex for v in range(1, 11)], "gelap  →  terang"),
        ("Chroma (kepekatan)", [map_to_srgb(0.66, v * 0.02, 30).hex for v in range(10)], "kusam  →  pekat"),
        ("Hue (rona)", [map_to_srgb(0.72, 0.12, h).hex for h in range(0, 360, 36)], "merah → kuning → hijau → biru → ungu"),
    ]
    for i, (name, hexes, note) in enumerate(rows):
        y = 124 - i * 52
        d.add(String(0, y + 10, name, fontName="Sans-Semi", fontSize=10, fillColor=INK))
        chip_row(d, 130, y, hexes, size=30, gap=3)
        d.add(String(130, y - 11, note, fontName="Sans", fontSize=8, fillColor=MUTED))
    return d


def hsl_vs_oklch() -> Drawing:
    hues = [60, 120, 240, 300]
    names = ["kuning", "hijau", "biru", "magenta"]
    hsl = []
    for h in hues:
        r, g, b = colorsys.hls_to_rgb(h / 360, 0.5, 1.0)
        hsl.append("#{:02X}{:02X}{:02X}".format(round(r * 255), round(g * 255), round(b * 255)))
    ok = [map_to_srgb(0.7, 0.12, to_oklch(c)[2]).hex for c in hsl]

    def gray(c):
        return map_to_srgb(to_oklch(c)[0], 0, 0).hex

    d = Drawing(TEXT_W, 170)
    for i, (label, row) in enumerate((("HSL, lightness 50%", hsl), ("OKLCH, lightness 70%", ok))):
        x = i * (TEXT_W / 2)
        d.add(String(x, 156, label, fontName="Sans-Semi", fontSize=10, fillColor=INK))
        chip_row(d, x, 104, row, size=44, gap=6, labels=names)
        d.add(String(x, 70, "dilihat tanpa warna (abu-abu):", fontName="Sans", fontSize=8, fillColor=MUTED))
        chip_row(d, x, 22, [gray(c) for c in row], size=44, gap=6)
    d.add(String(0, 4, "Di HSL, kuning tampak jauh lebih terang daripada biru walau angkanya sama. Di OKLCH, angka sama = terang sama.",
                 fontName="Sans-It", fontSize=8, fillColor=MUTED))
    return d


def harmony_grid() -> Drawing:
    d = Drawing(TEXT_W, 300)
    per_row, cell_w, cell_h = 3, TEXT_W / 3, 145
    for n, rule in enumerate(RULES):
        col, row = n % per_row, n // per_row
        cx, cy, r = col * cell_w + cell_w / 2, 300 - row * cell_h - 70, 46
        for i in range(36):
            hue = i * 10
            d.add(Wedge(cx, cy, r, hue - 5.5, hue + 5.5, fillColor=hexc(map_to_srgb(0.75, 0.11, hue).hex),
                        strokeColor=None))
        d.add(Circle(cx, cy, r * 0.58, fillColor=colors.white, strokeColor=None))
        result = harmony(rule, 0.6, 0.13, 30)
        for k, (lightness, chroma, hue) in enumerate(result.colors):
            radius = r * (0.79 if rule != "monochromatic" else 0.62 + 0.3 * k / max(len(result.colors) - 1, 1))
            px, py = cx + radius * math.cos(math.radians(hue)), cy + radius * math.sin(math.radians(hue))
            d.add(Line(cx, cy, px, py, strokeColor=hexc("#8A8F96"), strokeWidth=0.8))
            base = k == result.base_index
            d.add(Circle(px, py, 6.5 if base else 5, fillColor=hexc(map_to_srgb(lightness, chroma, hue).hex),
                         strokeColor=colors.white, strokeWidth=1.5))
        d.add(String(cx, cy - r - 16, RULE_LABELS[rule], fontName="Sans-Semi", fontSize=10, fillColor=INK,
                     textAnchor="middle"))
    return d


def scale_strip() -> Drawing:
    scale = tint_shade_scale("#E63946")
    d = Drawing(TEXT_W, 76)
    size, gap = 38, (TEXT_W - 11 * 38) / 10
    for i, step in enumerate(scale):
        x = i * (size + gap)
        d.add(Rect(x, 26, size, size, fillColor=hexc(step.hex), strokeColor=hexc("#C8CCD2"), strokeWidth=0.5))
        d.add(String(x + size / 2, 14, str(step.step), fontName="Sans-Semi" if step.is_base else "Sans", fontSize=8.5,
                     fillColor=ACCENT if step.is_base else MUTED, textAnchor="middle"))
        if step.is_base:
            d.add(Rect(x, 6, size, 2, fillColor=ACCENT, strokeColor=None))
    return d


def gradient_bars() -> Drawing:
    d = Drawing(TEXT_W, 104)
    n = 80
    for i, (label, space) in enumerate((("OKLab", "oklab"), ("sRGB", "srgb"))):
        y = 62 - i * 44
        d.add(String(0, y + 12, label, fontName="Sans-Semi", fontSize=10, fillColor=INK))
        width = (TEXT_W - 60) / n
        for k, c in enumerate(gradient(["#0000FF", "#FFFF00"], n, space)):
            d.add(Rect(60 + k * width, y, width + 0.4, 30, fillColor=hexc(c), strokeColor=None))
    return d


def contrast_examples() -> Drawing:
    pairs = [("#000000", "#FFFFFF"), ("#767676", "#FFFFFF"), ("#7A8FB0", "#FFFFFF"), ("#FFFFFF", "#F2C14E")]
    d = Drawing(TEXT_W, 104)
    w, gap = (TEXT_W - 3 * 10) / 4, 10
    for i, (fg, bg) in enumerate(pairs):
        x = i * (w + gap)
        d.add(Rect(x, 34, w, 64, fillColor=hexc(bg), strokeColor=hexc("#C8CCD2"), strokeWidth=0.6))
        d.add(String(x + 12, 64, "Aa", fontName="Sans-Bold", fontSize=22, fillColor=hexc(fg)))
        d.add(String(x + 12, 46, "Contoh teks biasa", fontName="Sans", fontSize=9, fillColor=hexc(fg)))
        ratio = contrast_ratio(fg, bg)
        verdict = "lulus AA" if ratio >= 4.5 else ("hanya teks besar" if ratio >= 3 else "tidak lulus")
        col = "#2D9D78" if ratio >= 4.5 else ("#B7791F" if ratio >= 3 else "#C9252D")
        d.add(String(x + w / 2, 18, format_ratio(ratio), fontName="Sans-Bold", fontSize=11, fillColor=INK, textAnchor="middle"))
        d.add(String(x + w / 2, 5, verdict, fontName="Sans-Semi", fontSize=8.5, fillColor=hexc(col), textAnchor="middle"))
    return d


def cvd_rows() -> Drawing:
    palette = ["#1F77B4", "#FF7F0E", "#2CA02C", "#D62728", "#9467BD", "#8C564B"]
    rows = [("Penglihatan normal", None), ("Protanopia (lemah merah)", "protan"), ("Deuteranopia (lemah hijau)", "deutan"),
            ("Tritanopia (lemah biru)", "tritan"), ("Akromatopsia (tanpa warna)", "achroma")]
    d = Drawing(TEXT_W, 190)
    for i, (label, kind) in enumerate(rows):
        y = 160 - i * 36
        hexes = palette if kind is None else [simulate_hex(c, kind, 1.0) for c in palette]
        d.add(String(0, y + 9, label, fontName="Sans-Semi" if kind is None else "Sans", fontSize=9.5, fillColor=INK))
        chip_row(d, 170, y, hexes, size=44, gap=4)
    return d


def print_pairs():
    path = SYSTEM_PROFILE_DIR / "RSWOP.icm"
    if not path.exists():
        return None
    matches = CmykProofer(path).match(["#3D6A9E", "#F2C14E", "#0066FF", "#00C853", "#FF00AA", "#1F3A5F"])
    d = Drawing(TEXT_W, 96)
    w = TEXT_W / len(matches)
    for i, m in enumerate(matches):
        x = i * w + (w - 64) / 2
        d.add(Rect(x, 34, 32, 52, fillColor=hexc(m.hex), strokeColor=None))
        d.add(Rect(x + 32, 34, 32, 52, fillColor=hexc(m.print_hex), strokeColor=None))
        d.add(String(x + 16, 24, "layar", fontName="Sans", fontSize=7.5, fillColor=MUTED, textAnchor="middle"))
        d.add(String(x + 48, 24, "cetak", fontName="Sans", fontSize=7.5, fillColor=MUTED, textAnchor="middle"))
        tone = "#2D9D78" if m.shift == "match" else ("#B7791F" if m.shift == "slight" else "#C9252D")
        d.add(String(x + 32, 8, f"ΔE {m.delta_e:.1f}", fontName="Sans-Semi", fontSize=9, fillColor=hexc(tone), textAnchor="middle"))
    return d


def annotated_overview() -> Path:
    """The overview screenshot with numbered markers on each part of the window."""
    import json

    src = SHOTS / "overview.png"
    regions = json.loads((SHOTS / "overview.json").read_text(encoding="utf-8"))
    img = PILImage.open(src).convert("RGB")
    scale = img.width / 1440
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(str(FONTS / "SourceSans3-Bold.ttf"), int(30 * scale))
    marks = [("menu", 1, (0.45, 0.5)), ("options", 2, (0.6, 0.5)), ("tools", 3, (0.5, 0.42)), ("tabs", 4, (0.35, 0.5)),
             ("canvas", 5, (0.5, 0.55)), ("panels", 6, (0.5, 0.45)), ("status", 7, (0.5, 0.5))]
    for key, number, (fx, fy) in marks:
        x, y, w, h = regions[key]
        cx, cy = (x + w * fx) * scale, (y + h * fy) * scale
        r = 25 * scale
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(20, 115, 230), outline=(255, 255, 255), width=int(3.5 * scale))
        draw.text((cx, cy), str(number), fill=(255, 255, 255), font=font, anchor="mm")
    out = BUILD / "overview-annotated.png"
    img.save(out)
    return out


# --------------------------------------------------------------------- pages


class GuideDoc(BaseDocTemplate):
    def __init__(self, path: Path):
        super().__init__(
            str(path), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=2.3 * cm, bottomMargin=2 * cm,
            title="Panduan Colorize" + (" - Edisi Lengkap" if FULL else ""), author="Colorize", subject=f"Buku panduan Colorize {__version__}",
        )
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="body")
        self.addPageTemplates([
            PageTemplate("cover", [frame], onPage=self._cover),
            PageTemplate("body", [frame], onPageEnd=self._chrome),
        ])
        self.chapter_title = ""
        self._seq = 0

    def beforeDocument(self):
        # multiBuild lays the story out several times; bookmark keys must repeat exactly
        self._seq = 0
        self.chapter_title = ""

    def afterFlowable(self, flowable):
        level = getattr(flowable, "toc_level", None)
        if level is None:
            return
        text = flowable.getPlainText()
        if getattr(flowable, "running_title", False):
            self.chapter_title = text
        self._seq += 1
        key = f"h{self._seq}"
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(text, key, level=level, closed=level > 0)
        self.notify("TOCEntry", (level, text, self.page, key))

    def _cover(self, canv, doc):
        canv.saveState()
        canv.setFillColor(colors.HexColor("#1B1B1B"))
        canv.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
        canv.drawImage(str(SHOTS / "logo.png"), MARGIN, PAGE_H - 9.5 * cm, width=4.2 * cm, height=4.2 * cm, mask="auto")
        canv.setFillColor(colors.HexColor("#F0F0F0"))
        canv.setFont("Sans-Light", 48)
        canv.drawString(MARGIN, PAGE_H - 12.4 * cm, "Colorize")
        canv.setFont("Sans-Semi", 20)
        canv.setFillColor(colors.HexColor("#7AB8FF"))
        canv.drawString(MARGIN, PAGE_H - 13.7 * cm, "Edisi Lengkap" if FULL else "Buku Panduan Lengkap")
        canv.setFont("Sans", 12.5)
        canv.setFillColor(colors.HexColor("#B8B8B8"))
        lines = ((
            "Panduan aplikasi, ilmu warna untuk desainer grafis,",
            "resep proyek, dan referensi. Ditulis untuk pemula.",
        ) if FULL else (
            "Memilih, memeriksa, dan memakai warna dengan percaya diri.",
            "Ditulis untuk pemula: setiap istilah sulit dijelaskan.",
        ))
        for i, line in enumerate(lines):
            canv.drawString(MARGIN, PAGE_H - 15.0 * cm - i * 18, line)
        if (SHOTS / "wheel-oklch.png").exists():
            canv.drawImage(str(SHOTS / "wheel-oklch.png"), PAGE_W - 9.5 * cm, 3.0 * cm, width=8 * cm, height=8 * cm,
                           mask="auto")
        canv.setFont("Sans", 10)
        canv.setFillColor(colors.HexColor("#8A8A8A"))
        canv.drawString(MARGIN, 2.4 * cm, f"Untuk Colorize versi {__version__} · Windows 10/11")
        canv.drawString(MARGIN, 1.8 * cm, "Lisensi aplikasi: MIT · Huruf: Source Sans 3 (SIL Open Font License)")
        canv.restoreState()

    def _chrome(self, canv, doc):
        canv.saveState()
        canv.setStrokeColor(RULE)
        canv.setLineWidth(0.5)
        canv.line(MARGIN, PAGE_H - 1.5 * cm, PAGE_W - MARGIN, PAGE_H - 1.5 * cm)
        canv.setFont("Sans", 8.5)
        canv.setFillColor(MUTED)
        canv.drawString(MARGIN, PAGE_H - 1.3 * cm, "Panduan Colorize")
        canv.drawRightString(PAGE_W - MARGIN, PAGE_H - 1.3 * cm, self.chapter_title)
        canv.drawCentredString(PAGE_W / 2, 1.1 * cm, str(doc.page))
        canv.restoreState()


# ------------------------------------------------------------------- content


def write_content(overview: Path) -> None:
    story.append(NextPageTemplate("body"))
    story.append(PageBreak())
    levels = [S["tocpart"], S["toc0"], S["toc1"]] if FULL else [S["toc0"], S["toc1"]]
    toc = TableOfContents(levelStyles=levels, dotsMinLevel=0)
    story.append(Paragraph("Daftar Isi", S["tochead"]))
    story.append(toc)
    if FULL:
        part("BAGIAN I", "Menggunakan Colorize",
             "Mengenal aplikasi dari nol: memasang, mengenal layar, menyusun palet, memeriksa keterbacaan, "
             "menyiapkan warna untuk cetak, sampai mengirim warna ke program lain.")

    # 1 -----------------------------------------------------------------
    chapter("Pengantar")
    P("Colorize adalah aplikasi untuk <b>memilih, merapikan, dan memeriksa warna</b>, lalu memakainya di pekerjaan Anda. "
      "Aplikasi ini bekerja tanpa internet dan tampilannya dibuat mirip Photoshop atau Illustrator, jadi terasa akrab "
      "bila Anda pernah memakai produk Adobe.", "lead")
    P("<b>Untuk siapa?</b> Siapa saja yang berurusan dengan warna: desainer grafis, pembuat website atau aplikasi, pemilik "
      "usaha yang menyiapkan warna merek, guru, atau pelajar. Anda tidak perlu paham teori warna untuk mulai. Setiap istilah "
      "sulit dijelaskan saat pertama muncul, dan semuanya dikumpulkan lagi di Glosarium di bagian akhir buku.")
    drawing(workflow_diagram(), "Gambar 1.1 · Dari ide sampai warna yang siap dipakai")
    section("Apa saja yang bisa dilakukan?")
    table([
        ["Kebutuhan Anda", "Fitur di Colorize", "Bab"],
        ["Menyusun kumpulan warna (palet)", "Dokumen palet, panel Swatches, Library", "5, 13"],
        ["Memilih warna dengan teliti", "Color picker, Eyedropper, ambil warna dari layar", "6"],
        ["Mencari warna yang serasi", "Harmony (roda warna), Scale, Gradient", "7, 8"],
        ["Mengambil warna dari foto", "Extract from Image", "9"],
        ["Memastikan teks mudah dibaca semua orang", "Contrast, Color Blindness", "10"],
        ["Menyiapkan warna untuk dicetak", "Print (CMYK), Match (buku warna)", "11"],
        ["Melihat palet di contoh tampilan", "Mockup", "12"],
        ["Memakai warna di website atau software desain", "Export (CSS, Tailwind, ASE, GPL)", "13"],
    ], [0.42, 0.46, 0.12])
    section("Cara membaca buku ini")
    bullets([
        "Bab 2 sampai 5 adalah dasar. Sebaiknya dibaca berurutan.",
        "Bab 6 sampai 14 boleh dibaca sesuai kebutuhan, misalnya langsung ke Bab 10 bila Anda ingin memeriksa keterbacaan teks.",
        f"Petunjuk menu ditulis seperti {M('Palette › Preview Mockup')}: klik menu <i>Palette</i>, lalu pilih <i>Preview Mockup</i>.",
        f"Tombol keyboard ditulis seperti {K('Ctrl+S')}: tahan tombol Ctrl, lalu tekan S.",
        *([
            "Bagian II (Bab 15 sampai 26) berisi ilmu warna untuk desainer grafis: cara mata melihat warna, kontras, "
            "komposisi, psikologi warna, merek, layar, visualisasi data, cetak, dan manajemen warna.",
            "Bagian III (Bab 27 sampai 30) berisi resep proyek: contoh pekerjaan nyata dari awal sampai selesai.",
        ] if FULL else []),
        "Kotak berwarna berisi hal penting: <b>Tips</b> (hijau), <b>Catatan</b> (kuning), <b>Istilah</b> (biru), dan <b>Perhatian</b> (merah).",
    ])
    box("tip", "Nama menu dan tombol di aplikasi memakai bahasa Inggris, seperti di produk Adobe. Buku ini menulis nama "
        "aslinya supaya mudah dicari di layar, lalu menjelaskan artinya dalam bahasa Indonesia.")

    # 2 -----------------------------------------------------------------
    chapter("Memasang dan Membuka Colorize")
    P("Colorize tidak perlu dipasang (di-install). Cukup unduh satu file zip, ekstrak, lalu jalankan.", "lead")
    section("Kebutuhan komputer")
    table([
        ["Hal", "Kebutuhan"],
        ["Sistem operasi", "Windows 10 atau Windows 11, 64-bit"],
        ["Ruang penyimpanan", "Sekitar 100 MB setelah diekstrak"],
        ["Internet", "Tidak perlu. Hanya dipakai saat mengunduh."],
        ["Program lain", "Tidak perlu. Python dan pustaka lain sudah ada di dalam folder aplikasi."],
    ], [0.3, 0.7])
    section("Mengunduh dan mengekstrak")
    steps([
        "Buka halaman rilis Colorize di GitHub: <b>github.com/s4rt4/colorize/releases</b>.",
        "Pada rilis terbaru, klik file <b>Colorize-0.2.0-win64.zip</b> untuk mengunduhnya.",
        "Buka folder Downloads, klik kanan file zip tersebut, lalu pilih <b>Extract All…</b> (Ekstrak Semua).",
        "Pilih tempat menyimpan, misalnya folder Dokumen, lalu klik <b>Extract</b>.",
        "Di dalam hasil ekstrak ada folder <b>Colorize</b>. Buka folder itu dan klik dua kali <b>Colorize.exe</b>.",
    ])
    box("tip", "Agar mudah dibuka lagi, klik kanan <b>Colorize.exe</b> lalu pilih <b>Show more options › Send to › Desktop "
        "(create shortcut)</b>. Ikon Colorize akan muncul di desktop.")
    section("Peringatan Windows saat pertama kali")
    P("Saat pertama dijalankan, Windows mungkin menampilkan kotak biru bertuliskan <b>Windows protected your PC</b>. "
      "Ini normal untuk aplikasi baru yang belum memiliki tanda tangan digital (code signing) berbayar, bukan tanda adanya virus.")
    steps(["Klik tulisan <b>More info</b> di kotak biru tersebut.", "Klik tombol <b>Run anyway</b> yang kemudian muncul.",
           "Peringatan ini hanya muncul sekali. Berikutnya Colorize langsung terbuka."])
    box("term", "<b>Code signing</b> adalah semacam stempel resmi pada file program yang membuktikan siapa pembuatnya. "
        "Stempel ini berbayar. Tanpanya, Windows memberi peringatan sebagai langkah hati-hati.")
    section("Layar pembuka dan layar awal")
    P("Saat Colorize dibuka, muncul <b>layar pembuka</b> (splash screen) bergambar logo selama sekitar dua detik. "
      "Teks kecil di bagian bawahnya menunjukkan apa yang sedang disiapkan.")
    figure("splash", "Gambar 2.1 · Layar pembuka Colorize", 0.75)
    P("Setelah itu jendela utama terbuka dengan satu palet contoh. Bila semua palet ditutup, Colorize menampilkan "
      f"<b>layar awal</b> dengan tombol <b>New Palette</b> untuk membuat palet baru (sama dengan {K('Ctrl+N')}).")
    figure("home", "Gambar 2.2 · Layar awal saat tidak ada dokumen terbuka", 0.85)
    box("note", "Pengaturan, library palet, dan catatan kesalahan disimpan di folder <b>%APPDATA%\\Colorize</b>. "
        "Folder aplikasi bisa dipindah atau dihapus tanpa menghilangkan data tersebut.")

    # 3 -----------------------------------------------------------------
    chapter("Mengenal Layar Kerja")
    P("Layar Colorize terbagi menjadi tujuh bagian. Kenali bagian-bagian ini lebih dulu; bab-bab berikutnya akan sering "
      "menyebut namanya.", "lead")
    figure(overview, "Gambar 3.1 · Bagian-bagian layar kerja (angka dijelaskan di tabel berikut)")
    table([
        ["No.", "Nama", "Fungsi"],
        ["1", "Menu bar", "Daftar menu: File, Edit, Color, Palette, View, Window, Help."],
        ["2", "Options bar", "Pengaturan untuk alat yang sedang aktif. Isinya berganti sesuai alat."],
        ["3", "Toolbar", "Kotak alat di sisi kiri, plus kotak warna depan dan belakang di bawahnya."],
        ["4", "Tab dokumen", "Setiap palet, gambar, atau mockup yang terbuka mendapat satu tab."],
        ["5", "Kanvas", "Area kerja utama yang menampilkan isi tab aktif."],
        ["6", "Panel", "Jendela kecil bertab di kanan: Color, Swatches, Harmony, Contrast, dan lainnya."],
        ["7", "Status bar", "Informasi singkat: zoom, jumlah warna, dan warna depan dalam angka."],
    ], [0.08, 0.2, 0.72])
    section("Toolbar dan alat-alatnya")
    P("Setiap alat punya satu huruf pintasan. Tekan hurufnya untuk berpindah alat tanpa mengklik.")
    story.append(KeepTogether([Table([[_image("toolbar", 0.06 * TEXT_W), _tools_table()]],
                                     colWidths=[0.12 * TEXT_W, 0.88 * TEXT_W],
                                     style=[("VALIGN", (0, 0), (-1, -1), "TOP")])]))
    story.append(Spacer(1, 8))
    box("tip", f"Tahan tombol {K('Spasi')} untuk sementara memakai alat Hand (menggeser tampilan). Lepaskan, dan alat "
        "sebelumnya aktif kembali, persis seperti di Photoshop.")
    section("Options bar")
    P("Options bar berada tepat di bawah menu. Isinya mengikuti alat yang dipilih: aturan harmoni untuk alat Harmony, "
      "jumlah warna untuk Extract, ukuran sampel untuk Eyedropper, dan seterusnya.")
    figure("optionsbar", "Gambar 3.2 · Options bar saat alat Select aktif", 1.0)
    section("Panel")
    P("Panel adalah jendela kecil di sisi kanan. Beberapa panel berbagi satu kelompok dan bisa dipilih lewat tabnya.")
    bullets([
        "<b>Memindah panel:</b> tarik tab panel ke tempat lain. Garis biru menunjukkan posisi jatuhnya.",
        "<b>Melepas panel:</b> tarik tabnya keluar dari jendela; panel menjadi jendela terapung.",
        f"<b>Menutup dan membuka lagi:</b> klik tanda silang pada tab. Untuk membuka kembali, pilih namanya di menu {M('Window')}.",
        f"<b>Menciutkan jadi ikon:</b> klik tombol » di pojok kanan atas kelompok panel, atau pilih "
        f"{M('Window › Collapse Panels to Icons')}. Klik ikon untuk membuka panelnya sesaat.",
        f"<b>Menyembunyikan semuanya:</b> tekan {K('Tab')} untuk menyembunyikan seluruh panel dan bar; tekan lagi untuk memunculkannya.",
    ])
    figure("collapsed", "Gambar 3.3 · Panel diciutkan menjadi deretan ikon di tepi kanan", 0.9)
    section("Workspace (susunan panel)")
    P(f"<b>Workspace</b> adalah susunan panel yang sudah diatur untuk satu jenis pekerjaan. Pilih lewat {M('Window › Workspace')}.")
    table([
        ["Workspace", "Cocok untuk", "Panel yang tampil"],
        ["Essentials", "Pekerjaan umum (bawaan)", "Color, Swatches, Harmony, Contrast, Color Blindness, History, Export, Libraries"],
        ["Palette", "Menyusun dan mengirim palet", "Swatches, Libraries, Export, Color, Harmony, Scale, Gradient, Print, Match"],
        ["Accessibility", "Memeriksa keterbacaan", "Contrast, Color Blindness, Print, Color, Swatches"],
    ], [0.2, 0.3, 0.5])
    box("tip", f"Susunan panel kesayangan bisa disimpan: atur panelnya, lalu pilih {M('Window › Workspace › New Workspace…')} "
        f"dan beri nama. Bila susunan berantakan, pilih {M('Window › Workspace › Reset')} untuk mengembalikannya.")
    section("Tab dokumen, zoom, dan status bar")
    P("Judul tab menunjukkan nama dokumen dan zoom, misalnya <i>Untitled-1 @ 100%</i>. Tanda bintang (*) berarti ada "
      f"perubahan yang belum disimpan. Zoom diatur dengan {K('Ctrl+=')} (perbesar), {K('Ctrl+-')} (perkecil), {K('Ctrl+0')} "
      f"(pas layar), dan {K('Ctrl+1')} (100%). Bisa juga dengan {K('Ctrl')} + roda mouse.")
    P("Status bar di bagian paling bawah menampilkan zoom, jumlah warna di palet, warna yang dipilih, dan kode warna depan "
      "dalam format HEX dan OKLCH (dijelaskan di Bab 4).")

    # 4 -----------------------------------------------------------------
    chapter("Dasar-dasar Warna")
    P("Bab ini menjelaskan cara komputer mencatat warna. Pemahaman singkat ini membuat semua fitur Colorize lebih masuk akal.", "lead")
    section("Warna di layar adalah campuran cahaya")
    P("Setiap titik di layar (piksel) memancarkan cahaya merah, hijau, dan biru. Campuran ketiganya menghasilkan semua warna "
      "yang Anda lihat. Cara mencatat warna seperti ini disebut <b>RGB</b> (Red, Green, Blue). Setiap komponen bernilai 0 "
      "(mati) sampai 255 (paling terang).")
    bullets(["Ketiganya 0 = hitam. Ketiganya 255 = putih.", "Merah 255 saja = merah terang. Merah dan hijau 255 = kuning.",
             "Ketiganya sama besar = abu-abu."])
    section("Kode HEX")
    P("<b>HEX</b> adalah cara singkat menulis RGB, sering dipakai di website dan software desain. Kode HEX diawali tanda # lalu "
      "enam huruf atau angka: dua untuk merah, dua untuk hijau, dua untuk biru.")
    drawing(hex_anatomy(), "Gambar 4.1 · Kode #3D6A9E berarti merah 61, hijau 106, biru 158")
    box("term", "<b>Heksadesimal</b> adalah cara menulis angka memakai 16 simbol (0 sampai 9, lalu A sampai F). Dua simbol "
        "cukup untuk angka 0 sampai 255. Anda tidak perlu menghitungnya sendiri; Colorize selalu menampilkan angka RGB-nya juga.")
    section("Kenapa butuh cara lain: OKLCH")
    P("RGB dan HEX cocok untuk komputer, tetapi sulit untuk manusia. Coba tebak: apakah #3D6A9E lebih terang dari #9E3D6A? "
      "Cara lama seperti HSL mencoba membantu, tetapi angkanya tidak sesuai penglihatan: kuning dan biru dengan nilai "
      "<i>lightness</i> yang sama tampak sangat berbeda terangnya.")
    drawing(hsl_vs_oklch(), "Gambar 4.2 · HSL menipu mata; OKLCH tidak")
    P("Colorize memakai <b>OKLCH</b>, cara mencatat warna yang dirancang mengikuti mata manusia. Setiap warna dijelaskan "
      "dengan tiga angka yang mudah dibayangkan:")
    drawing(oklch_strips(), "Gambar 4.3 · Tiga sifat warna dalam OKLCH")
    table([
        ["Sifat", "Artinya", "Nilai"],
        ["L · Lightness", "Seberapa terang warna terlihat", "0% (hitam) sampai 100% (putih)"],
        ["C · Chroma", "Seberapa pekat atau kuat warnanya; 0 berarti abu-abu", "0 sampai sekitar 0.37"],
        ["H · Hue", "Rona: merah, kuning, hijau, biru, dan seterusnya", "0 sampai 360 derajat (posisi di roda warna)"],
    ], [0.22, 0.48, 0.3])
    P("Contoh: <font name='Mono'>oklch(51.6% 0.097 253.2)</font> berarti warna dengan terang sedang, cukup pekat, berona biru. "
      "Colorize menampilkan format ini di panel Color dan status bar, berdampingan dengan HEX.")
    section("Gamut: batas warna yang bisa ditampilkan")
    P("Tidak semua kombinasi angka OKLCH bisa ditampilkan layar. Kumpulan warna yang bisa ditampilkan disebut <b>gamut</b>. "
      "Layar biasa memakai gamut bernama <b>sRGB</b>. Di roda warna Colorize, area yang pudar adalah warna di luar sRGB.")
    figures([("wheel-oklch", "Gambar 4.4 · Roda warna pada lightness 72%. Bagian cerah bisa ditampilkan; bagian pudar di luar gamut."),
             ("wheel-ryb", "Gambar 4.5 · Roda yang sama dalam susunan pelukis (RYB), dijelaskan di Bab 7")], 0.4)
    P("Bila Anda memilih warna di luar gamut, Colorize otomatis menampilkan warna terdekat yang bisa ditampilkan, dengan "
      "mengurangi kepekatannya saja (rona dan terang tetap). Warna seperti ini selalu diberi tanda: lingkaran bergaris putus-putus "
      "di roda, ikon segitiga peringatan di contoh warna, dan catatan di bawahnya.")
    section("Warna depan dan warna belakang")
    P("Seperti Photoshop, Colorize selalu memegang dua warna aktif: <b>foreground</b> (warna depan, kotak atas) dan "
      "<b>background</b> (warna belakang, kotak bawah). Keduanya terlihat di bawah toolbar. Banyak fitur memakai keduanya, "
      "misalnya pemeriksaan kontras (teks = depan, latar = belakang) dan gradien (dari depan ke belakang).")
    bullets([f"{K('X')} menukar warna depan dan belakang.", f"{K('D')} mengembalikan ke hitam dan putih.",
             "Klik salah satu kotak untuk memilih warnanya dengan color picker."])

    # 5 -----------------------------------------------------------------
    chapter("Palet: Kumpulan Warna Anda")
    P("<b>Palet</b> adalah kumpulan warna yang dipakai bersama, misalnya warna merek sebuah usaha. Di Colorize, setiap palet "
      "adalah sebuah dokumen dengan tabnya sendiri. Setiap warna di dalamnya disebut <b>swatch</b>.", "lead")
    figure("canvas", "Gambar 5.1 · Palet di kanvas. Swatch ketiga sedang dipilih (bingkai biru).", 0.95)
    section("Membuat palet")
    steps([f"Pilih {M('File › New Palette')} atau tekan {K('Ctrl+N')}.",
           "Tab baru bernama <i>Untitled-2</i> (atau nomor berikutnya) muncul dengan palet kosong.",
           f"Untuk mengganti nama, pilih {M('Palette › Rename Palette…')}, ketik nama baru, lalu klik OK."])
    section("Menambah, memilih, dan mengatur swatch")
    table([
        ["Ingin…", "Caranya"],
        ["Menambah warna depan ke palet", "Klik tombol + di panel Swatches, atau tombol <b>Add to Swatches</b> di panel Color."],
        ["Memilih sebuah swatch", "Klik swatch tersebut. Tombol panah di keyboard juga bisa dipakai."],
        ["Menjadikan swatch sebagai warna depan", "Klik dua kali swatch tersebut."],
        ["Mengubah urutan", "Tarik swatch ke posisi baru. Garis biru menunjukkan tempat jatuhnya."],
        ["Mengganti warna swatch", f"Pilih swatch, atur warna depan, lalu {M('Palette › Replace Swatch with Foreground')}."],
        ["Menghapus swatch", f"Pilih swatch, lalu tekan {K('Delete')} atau klik ikon tempat sampah di panel Swatches."],
        ["Melihat semua pilihan", "Klik kanan sebuah swatch untuk membuka menu singkat."],
    ], [0.38, 0.62])
    figures([("panel-swatches", "Gambar 5.2 · Panel Swatches: daftar ringkas, tombol + dan hapus"),
             ("panel-history", "Gambar 5.3 · Panel History: setiap langkah tercatat")], 0.4)
    section("Membatalkan kesalahan (Undo)")
    P(f"Hampir semua perubahan pada palet bisa dibatalkan dengan {K('Ctrl+Z')} dan diulang dengan {K('Ctrl+Shift+Z')}. "
      "Panel <b>History</b> menampilkan daftar langkah; klik sebuah langkah untuk kembali ke keadaan saat itu. Setiap palet "
      "punya riwayatnya sendiri.")
    box("note", "Warna depan dan belakang tidak masuk riwayat, sama seperti di Photoshop. Yang tercatat adalah perubahan pada palet.")
    section("Menyimpan dan membuka")
    steps([f"Pilih {M('File › Save')} atau tekan {K('Ctrl+S')}.",
           "Pilih folder, beri nama file, lalu klik Save. Palet disimpan sebagai file <b>.json</b>.",
           f"Untuk membuka lagi: {M('File › Open…')} ({K('Ctrl+O')}), atau tarik file ke jendela Colorize. "
           f"File yang baru dibuka tercatat di {M('File › Open Recent')}."])
    box("warn", "Bila menutup palet yang belum disimpan, Colorize bertanya: <b>Save</b> (simpan), <b>Discard</b> (buang perubahan), "
        "atau <b>Cancel</b> (batal menutup). Pilih Save bila ragu.")
    box("term", "<b>JSON</b> adalah format file teks yang rapi dan umum dipakai program. File palet Colorize bisa dibuka di "
        "editor teks biasa, dan isinya hanyalah nama palet serta daftar kode warna.")

    # 6 -----------------------------------------------------------------
    chapter("Memilih Warna")
    P("Ada empat cara mendapatkan warna: mengetik kodenya, memilih di color picker, mengambil dari palet atau gambar, dan "
      "mengambil dari mana saja di layar.", "lead")
    section("Panel Color")
    figures([("panel-color", "Gambar 6.1 · Panel Color: kotak warna depan/belakang, kode HEX, RGB, dan OKLCH")], 0.5)
    bullets(["Ketik kode HEX di kotak <b>Hex</b> lalu tekan Enter untuk mengganti warna depan. Kode pendek seperti <i>f80</i> juga diterima.",
             "Baris RGB dan OKLCH menunjukkan warna yang sama dalam cara pencatatan lain.",
             "Ikon pipet di samping kotak Hex mengambil warna dari layar (lihat bagian terakhir bab ini)."])
    section("Color picker")
    P("Klik kotak warna depan atau belakang (di bawah toolbar atau di panel Color) untuk membuka <b>color picker</b>.")
    figure("picker", "Gambar 6.2 · Color picker. Ikon segitiga di kanan atas muncul karena warna ini di luar gamut.", 0.8)
    table([
        ["Bagian", "Kegunaan"],
        ["Bidang besar (kiri)", "Geser ke kanan untuk warna lebih pekat, ke atas untuk lebih terang. Rona tetap."],
        ["Strip pelangi (tengah)", "Geser naik-turun untuk mengganti rona (hue)."],
        ["Dua kotak di kanan atas", "Atas: warna baru. Bawah: warna lama. Klik warna lama untuk kembali."],
        ["Ikon segitiga peringatan", "Warna berada di luar gamut layar. Klik untuk mengambil warna terdekat yang bisa ditampilkan."],
        ["L, C, H, # dan RGB", "Ketik angka langsung untuk ketepatan."],
    ], [0.32, 0.68])
    section("Eyedropper: mengambil warna dari palet atau gambar")
    steps([f"Pilih alat Eyedropper dengan menekan {K('I')}.", "Klik sebuah swatch atau bagian gambar. Warnanya menjadi warna depan.",
           f"Tahan {K('Alt')} sambil mengklik untuk mengisi warna belakang."])
    P("Di Options bar, <b>Sample Size</b> menentukan berapa titik yang diambil: <i>Point Sample</i> (satu titik), atau rata-rata "
      "3×3 dan 5×5 titik. Rata-rata berguna untuk foto, karena satu titik foto sering sedikit berbeda dari sekitarnya.")
    section("Mengambil warna dari mana saja di layar")
    P(f"Pilih {M('Color › Sample Screen Color')} atau tekan {K('Shift+I')}. Layar membeku dan kaca pembesar muncul di dekat "
      f"kursor. Klik untuk mengambil warna, atau tekan {K('Esc')} untuk batal. Ini bekerja di semua monitor, termasuk di website "
      "atau aplikasi lain yang sedang terbuka.")
    figure("screen-sampler", "Gambar 6.3 · Kaca pembesar saat mengambil warna layar. Kotak putih = area yang diambil.", 0.6)
    box("note", "Warna dari layar dibaca apa adanya. Bila monitor Anda diatur dengan profil warna khusus, hasilnya bisa sedikit "
        "berbeda dari file aslinya.")

    # 7 -----------------------------------------------------------------
    chapter("Harmoni Warna")
    P("<b>Harmoni warna</b> adalah aturan memilih beberapa warna yang serasi berdasarkan posisinya di roda warna. Anda memilih "
      "satu warna dasar, Colorize menghitung pasangannya.", "lead")
    section("Enam aturan harmoni")
    drawing(harmony_grid(), "Gambar 7.1 · Enam aturan harmoni. Titik besar = warna dasar, titik kecil = pasangannya.")
    table([
        ["Aturan", "Cara kerja", "Kesan dan contoh pemakaian"],
        ["Complementary", "Warna yang berseberangan di roda", "Kontras kuat. Cocok untuk tombol yang harus menonjol."],
        ["Analogous", "Warna-warna yang bertetangga", "Tenang dan menyatu. Cocok untuk latar dan ilustrasi."],
        ["Triadic", "Tiga warna dengan jarak sama", "Ceria dan seimbang. Cocok untuk anak-anak dan grafik."],
        ["Tetradic", "Empat warna berjarak sama", "Kaya warna. Pakai satu sebagai warna utama, sisanya sedikit."],
        ["Split Complementary", "Warna dasar dan dua tetangga dari lawannya", "Kontras tapi lebih lembut dari complementary."],
        ["Monochromatic", "Satu rona, berbeda terang", "Elegan dan aman. Cocok untuk tampilan formal."],
    ], [0.22, 0.36, 0.42])
    section("Memakai panel Harmony")
    figures([("panel-harmony", "Gambar 7.2 · Panel Harmony (aturan Triadic)")], 0.5)
    steps([f"Buka tab <b>Harmony</b> di panel kanan, atau tekan {K('W')}.",
           "Pilih aturan di daftar <b>Rule</b>.",
           "Tarik titik mana pun di roda. Semua titik ikut berputar bersama. Jarak dari tengah menentukan kepekatan.",
           "Atur <b>Lightness</b> dan <b>Chroma</b> dengan slider di bawah roda.",
           "Klik salah satu kotak hasil untuk menjadikannya warna depan, atau klik <b>Add to Swatches</b> untuk menambahkan semuanya ke palet.",
           "Tombol bulat di kanan atas memakai warna depan sebagai warna dasar."])
    section("Roda Perceptual dan roda Artist (RYB)")
    P("Di bawah daftar aturan ada pilihan <b>Wheel</b>:")
    bullets(["<b>Perceptual (OKLCH)</b>: rona disusun sesuai penglihatan mata. Jarak yang sama di roda terlihat sama berbedanya.",
             "<b>Artist (RYB)</b>: susunan roda pelukis yang diajarkan di sekolah, dengan merah, kuning, dan biru sebagai warna dasar. "
             "Pasangan lawannya: merah dengan hijau, kuning dengan ungu, biru dengan oranye. Roda ini juga dipakai Adobe Color."])
    figures([("panel-harmony-ryb", "Gambar 7.3 · Roda Artist (RYB): lawan merah adalah hijau")], 0.5)
    box("tip", "Tidak ada yang benar atau salah. Pakai RYB bila Anda terbiasa dengan teori warna lukis; pakai Perceptual bila "
        "ingin semua warna terlihat sama terang dan sama kuat.")

    # 8 -----------------------------------------------------------------
    chapter("Skala Warna dan Gradien")
    section("Skala tint dan shade (50 sampai 950)")
    P("Desain website dan aplikasi sering butuh satu warna dalam banyak tingkat terang, misalnya biru muda untuk latar dan biru "
      "tua untuk teks. Kumpulan ini disebut <b>skala</b>, dan tingkatnya diberi nomor 50 (paling terang) sampai 950 (paling gelap).")
    drawing(scale_strip(), "Gambar 8.1 · Skala dari warna merah #E63946. Garis biru = posisi warna asli (500).")
    box("term", "<b>Tint</b> adalah versi warna yang lebih terang (seolah dicampur putih). <b>Shade</b> adalah versi yang lebih gelap "
        "(seolah dicampur hitam).")
    figures([("panel-scale", "Gambar 8.2 · Panel Scale")], 0.5)
    steps(["Buka panel <b>Scale</b> (ada di workspace Palette, atau lewat menu Window).",
           "Klik tombol bulat untuk memakai warna depan sebagai warna dasar.",
           "Atur <b>Lightest</b> dan <b>Darkest</b> bila ingin ujung skala lebih terang atau lebih gelap.",
           "Klik <b>Add to Swatches</b> atau <b>New Palette</b>."])
    P("Langkah terangnya dibuat rata menurut penglihatan, dan warna dasar Anda tetap persis sama di posisinya. Saat diekspor, "
      "pilih <b>Names: Scale (50 – 950)</b> agar warnanya bernama seperti <i>brand-50</i> sampai <i>brand-950</i>.")
    section("Gradien")
    P("<b>Gradien</b> adalah peralihan halus dari satu warna ke warna lain. Panel <b>Gradient</b> membuat gradien dari warna depan "
      "ke warna belakang.")
    drawing(gradient_bars(), "Gambar 8.3 · Biru ke kuning. Campuran OKLab tetap cerah; sRGB (cara lama) kusam di tengah.")
    figures([("panel-gradient", "Gambar 8.4 · Panel Gradient")], 0.5)
    bullets([f"<b>Mix in</b>: cara mencampur. Pakai OKLab (disarankan). sRGB disediakan sebagai pembanding.",
             "<b>Steps</b>: berapa warna diambil dari gradien untuk dijadikan swatch.",
             "<b>Copy CSS</b>: menyalin kode gradien untuk website, lengkap dengan pengaturan pencampuran OKLab.",
             "Klik salah satu kotak langkah untuk menyalin kode HEX-nya."])

    # 9 -----------------------------------------------------------------
    chapter("Mengambil Palet dari Gambar")
    P("Colorize bisa membaca sebuah foto dan menemukan warna-warna utamanya secara otomatis. Cocok untuk mendapatkan palet dari "
      "foto produk, pemandangan, atau karya yang Anda sukai.", "lead")
    figure("image-extract", "Gambar 9.1 · Gambar terbuka di tabnya sendiri, dengan penanda dan strip warna hasil ekstraksi.")
    section("Langkah-langkah")
    steps([f"Pilih {M('File › Open Image…')} ({K('Ctrl+Shift+O')}), atau tarik file gambar ke jendela Colorize. "
           "Format yang didukung: PNG, JPG, WebP, TIFF, BMP, dan GIF.",
           "Gambar terbuka di tab baru. Warna utamanya langsung muncul di strip bawah, diurutkan dari yang paling banyak.",
           "Ubah jumlah warna di kotak <b>Colors</b> (2 sampai 16).",
           "Lingkaran di atas gambar menunjukkan dari mana setiap warna berasal. Tarik lingkaran untuk mengambil warna di titik lain.",
           "Atur urutan warna: tarik kotak di strip, atau klik <b>Sort</b> (paling banyak, terang ke gelap, rona, atau paling pekat).",
           "Klik <b>New Palette</b> untuk membuat palet baru, atau <b>Add to Swatches</b> untuk menambahkan ke palet terakhir."])
    box("tip", "Atur jumlah warna lebih dulu, baru urutannya. Mengubah jumlah warna menghitung ulang semuanya dan urutan kembali "
        "ke bawaan.")
    section("Hal yang dikerjakan Colorize di balik layar")
    bullets(["<b>Profil warna foto dibaca.</b> Foto dari iPhone dan banyak kamera memakai gamut lebih lebar bernama Display P3. "
             "Colorize mengubahnya ke sRGB lebih dulu, sehingga warnanya tidak melenceng. Informasinya tampil di bawah strip.",
             "<b>Bagian transparan diabaikan.</b> Pada logo PNG berlatar transparan, latarnya tidak ikut dihitung.",
             "<b>Hasilnya selalu sama.</b> Gambar yang sama selalu menghasilkan palet yang sama."])
    box("term", "<b>Profil warna</b> (ICC profile) adalah keterangan di dalam file gambar tentang cara membaca angka warnanya. "
        "Tanpa profil, gambar dianggap memakai sRGB.")

    # 10 ----------------------------------------------------------------
    chapter("Aksesibilitas: Warna untuk Semua Orang")
    P("Warna yang indah belum tentu nyaman dibaca. Sekitar 1 dari 12 laki-laki memiliki kelainan penglihatan warna, dan banyak "
      "orang membaca di bawah cahaya terang atau di layar redup. Bab ini menunjukkan cara memeriksanya.", "lead")
    section("Rasio kontras")
    P("<b>Kontras</b> adalah perbedaan terang antara teks dan latarnya. Standar internasional <b>WCAG</b> mengukurnya sebagai "
      "rasio, dari 1:1 (sama sekali tidak terbaca) sampai 21:1 (hitam di atas putih).")
    drawing(contrast_examples(), "Gambar 10.1 · Empat pasangan teks dan latar beserta rasio kontrasnya")
    table([
        ["Tingkat", "Rasio minimal", "Untuk"],
        ["AA", "4.5:1", "Teks biasa. Tingkat yang umumnya diwajibkan."],
        ["AA Large", "3:1", "Teks besar: 24 px ke atas, atau 18,5 px tebal ke atas."],
        ["AAA", "7:1", "Teks biasa, tingkat terbaik."],
        ["AAA Large", "4.5:1", "Teks besar, tingkat terbaik."],
        ["UI 3:1", "3:1", "Ikon, garis kotak isian, dan elemen tampilan lainnya."],
    ], [0.2, 0.2, 0.6])
    section("Panel Contrast")
    figures([("panel-contrast", "Gambar 10.2 · Panel Contrast: teks biru keabuan di atas putih gagal AA, lengkap dengan saran perbaikan")], 0.5)
    steps([f"Jadikan warna teks sebagai warna depan dan warna latar sebagai warna belakang. Tekan {K('X')} untuk menukarnya.",
           "Lihat kotak contoh di panel Contrast, rasio WCAG, dan daftar tanda centang (lulus) atau silang (tidak lulus).",
           "Di bagian <b>Fix for</b>, pilih target, misalnya AA.",
           "Klik salah satu warna saran. Saran hanya menggeser terang warnanya; ronanya tetap, sehingga warna merek tetap dikenali."])
    box("term", "<b>APCA</b> adalah cara mengukur kontras yang lebih baru dan sedang disiapkan untuk standar berikutnya. "
        "Angkanya ditulis Lc, misalnya Lc 60. Colorize menampilkannya sebagai panduan tambahan; untuk syarat resmi tetap pakai WCAG.")
    section("Simulasi buta warna")
    P("Panel <b>Color Blindness</b> menampilkan palet Anda seperti yang dilihat orang dengan jenis penglihatan warna berbeda.")
    drawing(cvd_rows(), "Gambar 10.3 · Satu palet dalam lima jenis penglihatan. Merah dan hijau hampir sama bagi deuteranopia.")
    table([
        ["Jenis", "Yang sulit dibedakan", "Seberapa umum"],
        ["Protan (lemah merah)", "Merah dengan hijau; merah tampak gelap", "Sekitar 1% laki-laki"],
        ["Deutan (lemah hijau)", "Merah dengan hijau", "Paling umum, sekitar 5% laki-laki"],
        ["Tritan (lemah biru)", "Biru dengan hijau, kuning dengan merah muda", "Jarang"],
        ["Akromatopsia", "Semua warna; hanya terang-gelap", "Sangat jarang"],
    ], [0.3, 0.42, 0.28])
    figures([("panel-cvd", "Gambar 10.4 · Panel Color Blindness dengan peringatan pasangan yang sulit dibedakan")], 0.5)
    bullets(["Tulisan merah <b>pairs hard to tell apart</b> berarti ada pasangan warna yang sulit dibedakan. Arahkan kursor ke "
             "tulisan itu untuk melihat pasangannya.",
             "Slider <b>Severity</b> mengatur tingkat keparahan. Di bawah 100% adalah bentuk ringan (anomali), yang lebih umum."])
    section("Proof Colors: melihat seluruh kanvas")
    P(f"Pilih {M('View › Proof Colors')} atau tekan {K('Ctrl+Y')}. Seluruh kanvas, termasuk gambar, ditampilkan sesuai jenis "
      "penglihatan yang dipilih di panel Color Blindness. Tekan lagi untuk kembali normal.")
    figure("image-proof", "Gambar 10.5 · Foto pemandangan dilihat dengan deuteranopia: matahari jingga menjadi kuning kusam", 0.8)
    box("tip", "Jangan andalkan warna saja untuk membedakan informasi, misalnya merah = gagal dan hijau = berhasil. Tambahkan "
        "ikon, tulisan, atau perbedaan terang yang jelas.")

    # 11 ----------------------------------------------------------------
    chapter("Warna untuk Cetak dan Buku Warna")
    section("Layar dan tinta itu berbeda")
    P("Layar membuat warna dari <b>cahaya</b> (RGB). Mesin cetak membuat warna dari <b>tinta</b> cyan, magenta, kuning, dan hitam, "
      "disingkat <b>CMYK</b>. Tinta tidak bisa menyamai semua warna layar, terutama warna yang sangat menyala.")
    d = print_pairs()
    if d is not None:
        drawing(d, "Gambar 11.1 · Kiri tiap pasangan: warna layar. Kanan: perkiraan hasil cetak. Biru dan hijau menyala bergeser jauh.")
    box("term", "<b>ΔE</b> (dibaca delta E) adalah angka seberapa berbeda dua warna terlihat. Di bawah 2: hampir sama. 2 sampai 5: "
        "sedikit berbeda. Di atas 5: perbedaannya jelas terlihat.")
    section("Panel Print")
    figures([("panel-print", "Gambar 11.2 · Panel Print dengan profil SWOP bawaan Windows")], 0.5)
    table([
        ["Bagian", "Artinya"],
        ["Profile", "Jenis mesin cetak dan kertas. Windows menyediakan <i>SWOP Standard</i> (cetak offset Amerika)."],
        ["Intent", "Cara menyesuaikan warna di luar jangkauan. <i>Relative Colorimetric</i> cocok untuk kebanyakan kebutuhan."],
        ["Kotak ganda", "Kiri: warna layar. Kanan: perkiraan hasil cetak."],
        ["C M Y K %", "Takaran tinta yang perlu diberikan ke percetakan."],
        ["ΔE dan tandanya", "Centang = sama. Tilde (~) = sedikit bergeser. Segitiga = bergeser jelas."],
        ["Use Print Colors", "Mengganti warna yang bergeser jelas dengan warna yang benar-benar bisa dicetak."],
    ], [0.26, 0.74])
    box("note", "Profil ICC menggambarkan satu kondisi cetak tertentu. Tanyakan percetakan Anda profil yang mereka pakai, misalnya "
        f"<i>Coated FOGRA39</i> yang umum di Eropa dan Asia, lalu muat lewat pilihan <b>Load Profile…</b>. Profil SWOP bawaan Windows "
        "sudah tua dan kurang teliti di warna biru gelap.")
    section("Buku warna: Pantone, RAL, dan warna CSS")
    P("<b>Buku warna</b> adalah daftar warna bernama yang disepakati industri, sehingga semua orang menyebut warna yang sama. "
      "Panel <b>Match</b> mencarikan warna buku yang paling mirip untuk warna depan dan untuk setiap swatch di palet.")
    figures([("panel-match", "Gambar 11.3 · Panel Match dengan buku bawaan CSS Named Colors")], 0.5)
    bullets(["Buku bawaan adalah 148 <b>warna bernama CSS</b> (seperti tomato, coral, royalblue) yang bebas dipakai.",
             "<b>Pantone dan RAL tidak disertakan</b> karena datanya berlisensi. Bila Anda punya, misalnya dari Adobe Illustrator atau "
             "Pantone Connect, ekspor sebagai file .ase lalu impor dengan tombol + di panel Match. Nama warnanya ikut tersimpan.",
             "Klik dua kali hasil di daftar atas untuk menjadikannya warna depan.",
             "<b>Use Book Colors</b> mengganti seluruh palet dengan padanan terdekatnya dalam satu langkah (bisa dibatalkan)."])
    box("term", "<b>Pantone</b> adalah buku warna standar untuk cetak dan produk. <b>RAL</b> adalah buku warna standar untuk cat "
        "dan industri, banyak dipakai di Eropa.")

    # 12 ----------------------------------------------------------------
    chapter("Mockup: Melihat Palet di Tampilan Nyata")
    P("Warna sering terlihat berbeda saat dipakai bersama. <b>Mockup</b> menerapkan palet Anda ke contoh halaman website atau "
      "dashboard, sehingga Anda bisa menilainya sebelum dipakai sungguhan.", "lead")
    figure("mockup-window", "Gambar 12.1 · Tab Mockup dengan template Landing Page")
    section("Membuka mockup")
    steps([f"Buka palet yang ingin dicoba, lalu pilih {M('Palette › Preview Mockup')} ({K('Ctrl+Shift+M')}).",
           "Tab baru <i>Mockup – nama palet</i> terbuka. Setiap perubahan pada palet langsung terlihat di mockup.",
           "Pilih contoh tampilan di <b>Template</b>: Landing Page atau Dashboard."])
    figures([("mockup-landing", "Gambar 12.2 · Landing Page"), ("mockup-dashboard", "Gambar 12.3 · Dashboard")], 0.47)
    section("Peran warna")
    P("Colorize membagi warna palet ke beberapa <b>peran</b> secara otomatis:")
    table([
        ["Peran", "Dipakai untuk", "Dipilih dari"],
        ["Background", "Latar halaman", "Warna paling terang (paling gelap di mode Dark)"],
        ["Text", "Teks utama", "Warna gelap yang lulus kontras AA di atas latar"],
        ["Primary", "Tombol utama, judul berwarna", "Warna paling pekat"],
        ["Secondary, Accent", "Tombol kedua, label, sorotan", "Warna pekat berikutnya dengan rona berbeda"],
        ["Surface, Border, Muted text", "Kartu, garis, teks keterangan", "Dicampur dari latar dan teks"],
    ], [0.26, 0.34, 0.4])
    bullets(["<b>Shuffle</b>: mencoba susunan lain untuk Primary, Secondary, dan Accent.",
             "<b>Dark</b>: membalik ke tampilan gelap.",
             "Klik tombol peran di bawah untuk memilih warnanya sendiri, atau kembali ke <i>Automatic</i>.",
             "Baris paling bawah memeriksa kontras setiap pasangan teks di mockup. Teks merah berarti ada yang belum lulus.",
             "<b>Export SVG…</b> dan <b>Export PNG…</b> menyimpan mockup sebagai gambar untuk presentasi."])

    # 13 ----------------------------------------------------------------
    chapter("Ekspor, Impor, dan Library")
    section("Ekspor: memakai warna di program lain")
    P(f"Panel <b>Export</b> mengubah palet menjadi format yang dipahami program lain. Buka panelnya atau pilih {M('File › Export…')} "
      f"({K('Ctrl+Shift+E')}).")
    figures([("panel-export", "Gambar 13.1 · Panel Export dengan format Tailwind CSS v4")], 0.5)
    table([
        ["Format", "Untuk siapa", "Dipakai di"],
        ["CSS Variables", "Pembuat website", "File CSS website mana pun"],
        ["Tailwind CSS v4 / v3", "Pembuat website dengan Tailwind", "Proyek Tailwind (kelas seperti bg-brand-1)"],
        ["Design Tokens (W3C)", "Tim desain dan pengembang", "Figma Tokens, Style Dictionary, dan alat sejenis"],
        ["Adobe Swatch Exchange (.ase)", "Desainer grafis", "Photoshop, Illustrator, InDesign"],
        ["GIMP / Inkscape (.gpl)", "Pengguna software gratis", "GIMP, Inkscape, Krita"],
        ["Color List", "Siapa saja", "Daftar kode warna biasa"],
    ], [0.3, 0.3, 0.4])
    steps(["Pilih <b>Format</b>.", "Pilih <b>Colors as</b>: HEX, RGB, HSL, atau OKLCH (tidak berlaku untuk semua format).",
           "Isi <b>Name prefix</b>, misalnya <i>brand</i>, agar warnanya bernama brand-1, brand-2, dan seterusnya.",
           "Periksa pratinjau, lalu klik <b>Copy</b> (salin) atau <b>Export…</b> (simpan sebagai file)."])
    box("tip", "Palet berisi 11 warna dari panel Scale bisa diberi nama 50 sampai 950 dengan memilih <b>Names: Scale (50 – 950)</b>.")
    section("Impor dari program lain")
    P(f"File <b>.ase</b> (Adobe) dan <b>.gpl</b> (GIMP, Inkscape) bisa dibuka lewat {M('File › Open…')} atau ditarik ke jendela. "
      "Isinya menjadi palet baru yang belum disimpan.")
    section("Library: koleksi palet")
    P("<b>Library</b> adalah lemari tempat menyimpan palet di dalam Colorize, tanpa perlu mengurus file satu per satu.")
    figures([("panel-library", "Gambar 13.2 · Panel Libraries dalam mode Similar")], 0.5)
    table([
        ["Ingin…", "Caranya"],
        ["Menyimpan palet aktif", f"Klik + di panel Libraries, atau {M('Palette › Save to Library')} ({K('Ctrl+Alt+S')})."],
        ["Membuka palet dari library", "Klik dua kali palet di daftar."],
        ["Mencari", "Ketik nama, tag, atau kode HEX di kotak pencarian."],
        ["Memberi tag", "Klik kanan palet, pilih <b>Edit Tags…</b>, tulis tag dipisah koma, misalnya: merek, web."],
        ["Menyaring per tag", "Pilih tag di daftar <b>All tags</b>."],
        ["Mencari palet dengan warna mirip", "Klik <b>Similar</b>. Palet diurutkan dari yang punya warna paling mirip dengan warna depan."],
        ["Memasukkan banyak file sekaligus", "Klik <b>Import Files</b> lalu pilih file .json, .ase, atau .gpl."],
        ["Mengganti nama atau menghapus", "Klik kanan palet, lalu pilih Rename… atau Delete…"],
    ], [0.36, 0.64])

    # 14 ----------------------------------------------------------------
    chapter("Menyesuaikan Colorize")
    section("Tema tampilan")
    P(f"Colorize punya tiga tingkat terang tampilan, seperti Photoshop: <b>Dark</b>, <b>Medium Gray</b> (bawaan), dan <b>Light</b>. "
      f"Ganti lewat {M('Edit › Preferences…')} ({K('Ctrl+K')}), lewat {M('Window › Interface Theme')}, atau dengan "
      f"{K('Shift+F1')} (lebih gelap) dan {K('Shift+F2')} (lebih terang).")
    figures([("theme-dark", "Dark"), ("overview", "Medium Gray"), ("theme-light", "Light")], 0.31)
    figures([("preferences", "Gambar 14.2 · Jendela Preferences")], 0.6)
    box("note", "Semua warna tampilan Colorize sengaja abu-abu netral, tanpa sedikit pun warna biru atau hangat. Dengan begitu, "
        "tampilan aplikasi tidak memengaruhi cara mata Anda menilai warna palet.")
    section("Daftar pintasan keyboard")
    table([
        ["Tombol", "Fungsi"],
        ["V, I, W, E, C, B, H, Z", "Alat Select, Eyedropper, Harmony, Extract, Contrast, Color Blindness, Hand, Zoom"],
        ["Spasi (tahan)", "Alat Hand sementara"],
        ["X / D", "Tukar warna depan-belakang / kembali ke hitam-putih"],
        ["Shift+I", "Ambil warna dari layar"],
        ["Alt + klik (Eyedropper)", "Isi warna belakang"],
        ["Ctrl+N / Ctrl+O / Ctrl+Shift+O", "Palet baru / buka palet atau gambar / buka gambar"],
        ["Ctrl+S / Ctrl+Shift+S / Ctrl+W", "Simpan / simpan sebagai / tutup tab"],
        ["Ctrl+Z / Ctrl+Shift+Z", "Batalkan / ulangi"],
        ["Delete", "Hapus swatch terpilih"],
        ["Ctrl+Shift+E", "Ekspor"],
        ["Ctrl+Alt+S", "Simpan ke library"],
        ["Ctrl+Shift+M", "Buka mockup"],
        ["Ctrl+Y", "Proof Colors (simulasi buta warna)"],
        ["Ctrl+= / Ctrl+- / Ctrl+0 / Ctrl+1", "Perbesar / perkecil / pas layar / 100%"],
        ["Tab", "Sembunyikan atau munculkan semua panel"],
        ["Shift+F1 / Shift+F2", "Tema lebih gelap / lebih terang"],
        ["Ctrl+K", "Preferences"],
    ], [0.38, 0.62])

    if FULL:
        import guide_extra

        guide_extra.write(sys.modules[__name__])
        part("LAMPIRAN", "Referensi", "Glosarium, tanya jawab, daftar periksa, tabel nama warna, angka-angka penting, "
             "dan bacaan lanjutan.")

    # 15 ----------------------------------------------------------------
    chapter("Glosarium")
    P("Daftar istilah dalam buku ini, diurutkan menurut abjad.", "lead")
    table([["Istilah", "Arti"]] + [[f"<b>{t}</b>", a] for t, a in glossary()], [0.26, 0.74])

    # 16 ----------------------------------------------------------------
    chapter("Tanya Jawab dan Pemecahan Masalah")
    for question, answer in FAQ + (guide_extra.FAQ if FULL else []):
        story.append(KeepTogether([Paragraph(question, S["h3"]), Paragraph(answer, S["body"])]))
    if FULL:
        guide_extra.write_appendix(sys.modules[__name__])


def glossary():
    terms = GLOSSARY
    if FULL:
        import guide_extra

        terms = terms + guide_extra.GLOSSARY
    return sorted(terms, key=lambda t: t[0].replace("ΔE", "delta").lower())


def _tools_table():
    rows = [["Alat", "Huruf", "Gunanya"],
            ["Select", "V", "Memilih dan menyusun swatch"],
            ["Eyedropper", "I", "Mengambil warna dari swatch atau gambar"],
            ["Harmony", "W", "Membuka panel harmoni warna"],
            ["Extract from Image", "E", "Pengaturan ekstraksi warna dari gambar"],
            ["Contrast Check", "C", "Membuka panel kontras"],
            ["Color Blindness", "B", "Membuka panel simulasi buta warna"],
            ["Hand", "H", "Menggeser tampilan kanvas"],
            ["Zoom", "Z", "Klik untuk memperbesar, Alt+klik memperkecil"]]
    data = [[Paragraph(c, S["cellb" if i == 0 else "cell"]) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[0.27 * TEXT_W, 0.1 * TEXT_W, 0.5 * TEXT_W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), HEADER_BG), ("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 4),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return t


GLOSSARY = [
    ("APCA", "Cara baru mengukur kontras teks yang sedang disiapkan untuk standar WCAG 3. Ditulis dengan Lc, misalnya Lc 75."),
    ("ASE", "Adobe Swatch Exchange: format file palet milik Adobe untuk Photoshop, Illustrator, dan InDesign."),
    ("Background", "Warna belakang, kotak bawah di bawah toolbar."),
    ("Buku warna", "Daftar warna bernama yang disepakati bersama, seperti Pantone, RAL, atau warna bernama CSS."),
    ("Buta warna", "Kelainan penglihatan sehingga beberapa warna sulit dibedakan. Jenis utamanya protan, deutan, tritan, dan akromatopsia."),
    ("Chroma", "Seberapa pekat atau kuat sebuah warna. Chroma 0 berarti abu-abu."),
    ("CMYK", "Cyan, Magenta, Yellow, Key (hitam): empat tinta dasar mesin cetak."),
    ("Color picker", "Jendela untuk memilih warna dengan menggeser atau mengetik angka."),
    ("CSS", "Bahasa untuk mengatur tampilan website, termasuk warnanya."),
    ("Design token", "Nama dan nilai yang disepakati tim, misalnya brand-500 = #E63946, agar desain dan kode memakai warna yang sama."),
    ("ΔE (delta E)", "Angka perbedaan dua warna menurut penglihatan. Di bawah 2 hampir sama, di atas 5 jelas berbeda."),
    ("Dock / panel", "Jendela kecil di tepi layar berisi alat tertentu, bisa dipindah dan digabung."),
    ("Eyedropper", "Alat pipet untuk mengambil warna dari swatch, gambar, atau layar."),
    ("Foreground", "Warna depan, kotak atas di bawah toolbar. Warna yang paling sering dipakai fitur Colorize."),
    ("Gamut", "Kumpulan warna yang bisa ditampilkan sebuah layar atau dicetak sebuah mesin."),
    ("GPL", "Format file palet milik GIMP, juga dipakai Inkscape dan Krita."),
    ("Gradien", "Peralihan halus dari satu warna ke warna lain."),
    ("Harmoni warna", "Aturan memilih warna serasi berdasarkan posisinya di roda warna."),
    ("HEX", "Kode warna enam huruf/angka diawali #, misalnya #3D6A9E."),
    ("HSL", "Cara lama mencatat warna dengan Hue, Saturation, Lightness. Mudah dihitung, tetapi tidak sesuai penglihatan."),
    ("Hue", "Rona warna: merah, kuning, hijau, biru, dan seterusnya. Dinyatakan dalam derajat 0 sampai 360."),
    ("Kontras", "Perbedaan terang antara dua warna, terutama teks dan latarnya."),
    ("Library", "Koleksi palet yang disimpan di dalam Colorize."),
    ("Lightness", "Seberapa terang sebuah warna terlihat, dari 0% (hitam) sampai 100% (putih)."),
    ("Mockup", "Contoh tampilan untuk mencoba palet sebelum dipakai sungguhan."),
    ("OKLab / OKLCH", "Cara mencatat warna yang mengikuti penglihatan manusia. OKLCH memakai Lightness, Chroma, dan Hue."),
    ("Palet", "Kumpulan warna yang dipakai bersama."),
    ("Pantone", "Buku warna standar industri cetak dan produk. Datanya berlisensi."),
    ("Profil ICC", "Keterangan cara sebuah perangkat (kamera, layar, mesin cetak) menghasilkan warna."),
    ("Proof", "Pratinjau hasil akhir, misalnya seperti dilihat penderita buta warna atau seperti setelah dicetak."),
    ("RAL", "Buku warna standar untuk cat dan industri. Datanya berlisensi."),
    ("RGB", "Red, Green, Blue: tiga cahaya dasar yang membentuk warna di layar."),
    ("RYB", "Red, Yellow, Blue: roda warna pelukis yang diajarkan di sekolah."),
    ("Shade", "Versi warna yang lebih gelap."),
    ("Splash screen", "Layar pembuka yang muncul sesaat ketika aplikasi dijalankan."),
    ("sRGB", "Gamut standar untuk layar komputer dan website."),
    ("Swatch", "Satu contoh warna di dalam palet."),
    ("Tailwind CSS", "Alat populer untuk membuat tampilan website dengan kelas siap pakai, seperti bg-blue-500."),
    ("Tint", "Versi warna yang lebih terang."),
    ("Undo", "Membatalkan langkah terakhir."),
    ("WCAG", "Web Content Accessibility Guidelines: standar internasional agar website bisa dipakai semua orang."),
    ("Workspace", "Susunan panel yang disimpan untuk satu jenis pekerjaan."),
]

FAQ = [
    ("Windows menolak membuka Colorize. Apakah berbahaya?",
     "Tidak. Peringatan <i>Windows protected your PC</i> muncul karena aplikasi belum memiliki tanda tangan digital berbayar. "
     "Klik <b>More info</b> lalu <b>Run anyway</b>. Peringatan hanya muncul sekali."),
    ("Di mana palet dan pengaturan saya disimpan?",
     "File palet (.json) disimpan di tempat yang Anda pilih saat menyimpan. Library, pengaturan, dan catatan kesalahan berada di "
     "<b>%APPDATA%\\Colorize</b>. Ketik alamat itu di kolom alamat File Explorer untuk membukanya."),
    ("Panel saya hilang atau susunannya berantakan.",
     f"Tekan {K('Tab')} bila semua panel tersembunyi. Untuk membuka satu panel, pilih namanya di menu Window. Untuk mengembalikan "
     f"susunan, pilih {M('Window › Workspace › Reset')}."),
    ("Kenapa ada warna yang diberi tanda atau tampak pudar di roda?",
     "Warna tersebut berada di luar gamut layar (sRGB). Colorize menampilkan warna terdekat yang bisa ditampilkan, dengan "
     "kepekatan sedikit dikurangi. Turunkan Chroma bila ingin tanda itu hilang."),
    ("Warna terlihat berbeda di laptop dan di HP.",
     "Setiap layar menampilkan warna sedikit berbeda, tergantung kualitas dan pengaturannya. Kodenya tetap sama. Untuk penilaian "
     "penting, gunakan layar yang sudah dikalibrasi."),
    ("Hasil cetak tidak sama dengan di layar.",
     "Itu wajar, karena tinta tidak bisa menyamai semua warna layar. Periksa palet di panel Print sebelum mencetak, pakai profil "
     "dari percetakan Anda, lalu ganti warna bertanda dengan <b>Use Print Colors</b>."),
    ("Kenapa tidak ada warna Pantone atau RAL?",
     "Data keduanya berlisensi dan tidak boleh dibagikan bebas. Bila Anda memilikinya, ekspor sebagai .ase dari program Adobe "
     "atau Pantone Connect, lalu impor di panel Match."),
    ("Kode warna dari Colorize tidak sama dengan yang ditampilkan program lain.",
     "Pastikan kedua program memakai format yang sama (misalnya sama-sama HEX). Program lama kadang menampilkan HSL atau "
     "membulatkan angka secara berbeda. Kode HEX selalu bisa dipakai sebagai patokan."),
    ("Bagaimana mengembalikan Colorize ke pengaturan awal?",
     "Tutup Colorize, buka folder <b>%APPDATA%\\Colorize</b>, lalu hapus file <b>Colorize.ini</b>. Library tidak ikut terhapus "
     "selama file <b>library.sqlite</b> tidak dihapus."),
    ("Colorize tiba-tiba menampilkan pesan kesalahan.",
     "Dokumen Anda tetap terbuka. Simpan pekerjaan, lalu laporkan masalahnya di halaman GitHub Colorize (bagian Issues) dengan "
     "menyertakan isi file <b>colorize.log</b> dari folder %APPDATA%\\Colorize."),
]


def main() -> None:
    ensure_fonts()
    ensure_shots("--shots" in sys.argv)
    make_styles()
    overview = annotated_overview()
    write_content(overview)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = GuideDoc(OUT)
    doc.multiBuild(story)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
