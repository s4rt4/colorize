"""Full edition of the user guide (make_guide.py --lengkap): colour knowledge for
graphic designers, project recipes and appendices.

write(g) / write_appendix(g) receive the running make_guide module and use its
story builders. Every colour in the diagrams is computed (OKLCH, CVD simulation,
ICC transforms), not hand-picked, unless it is a published standard
(Okabe-Ito) or an illustrative sample said to be one.
"""

import math
from pathlib import Path

import numpy as np
from PIL import Image as PILImage
from PIL import ImageCms, ImageDraw, ImageFilter, ImageFont
from reportlab.graphics.shapes import Circle, Drawing, Line, Polygon, PolyLine, Rect, String, Wedge
from reportlab.lib import colors

from colorize.core.cmyk import SYSTEM_PROFILE_DIR, CmykProofer, approximate_cmyk
from colorize.core.color import hex_to_rgb, to_oklch
from colorize.core.contrast import contrast_ratio, format_ratio
from colorize.core.cvd import simulate_hex
from colorize.core.delta_e import delta_e_hex
from colorize.core.gamut import map_to_srgb
from colorize.core.harmony import harmony
from colorize.core.mix import gradient, mix
from colorize.core.scale import tint_shade_scale

g = None  # the make_guide module, set by write()

INK = colors.HexColor("#1F1F1F")
MUTED = colors.HexColor("#5F6368")
EDGE = colors.HexColor("#C8CCD2")
SWOP = SYSTEM_PROFILE_DIR / "RSWOP.icm"


# ------------------------------------------------------------------ helpers


def ok(lightness, chroma, hue) -> str:
    return map_to_srgb(lightness, chroma, hue).hex


def gray_of(hex_color: str) -> str:
    return ok(to_oklch(hex_color)[0], 0, 0)


def hc(h: str):
    return colors.HexColor(h)


def text(d, x, y, s, size=9, font="Sans", color=INK, anchor="start"):
    d.add(String(x, y, s, fontName=font, fontSize=size, fillColor=color if not isinstance(color, str) else hc(color),
                 textAnchor=anchor))


def ink_on(hex_color: str) -> str:
    """Black or white, whichever reads better on the colour."""
    return "#FFFFFF" if contrast_ratio("#FFFFFF", hex_color) >= contrast_ratio("#111111", hex_color) else "#111111"


def chips(d, x, y, hexes, size=26, gap=4, labels=None, label_size=7.5, height=None):
    for i, h in enumerate(hexes):
        d.add(Rect(x + i * (size + gap), y, size, height or size, fillColor=hc(h), strokeColor=EDGE, strokeWidth=0.5))
        if labels:
            text(d, x + i * (size + gap) + size / 2, y - 10, labels[i], label_size, color=MUTED, anchor="middle")


def chip(hex_color: str, w=34, h=16) -> Drawing:
    d = Drawing(w, h)
    d.add(Rect(0, 0, w, h, fillColor=hc(hex_color), strokeColor=EDGE, strokeWidth=0.5))
    return d


_fig = [0, 0]


def fig(caption: str) -> str:
    chapter = g._chapter[0]
    if _fig[0] != chapter:
        _fig[:] = [chapter, 0]
    _fig[1] += 1
    return f"Gambar {chapter}.{_fig[1]} · {caption}"


def font(size, bold=True):
    return ImageFont.truetype(str(g.FONTS / ("SourceSans3-Bold.ttf" if bold else "SourceSans3-Regular.ttf")), size)


def save(img: PILImage.Image, name: str) -> Path:
    out = g.BUILD / "extra" / f"{name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


def proofer():
    return CmykProofer(SWOP) if SWOP.exists() else None


def cmyk_text(hex_color: str, prf=None) -> str:
    c, m, y, k = prf.match([hex_color])[0].cmyk if prf else approximate_cmyk(hex_color)
    return f"{c:.0f} {m:.0f} {y:.0f} {k:.0f}"


def cmyk_to_hex(c, m, y, k) -> str | None:
    """How a CMYK ink mix looks on screen, through the SWOP profile."""
    if not SWOP.exists():
        return None
    img = PILImage.new("CMYK", (1, 1), tuple(round(v * 2.55) for v in (c, m, y, k)))
    t = ImageCms.buildTransform(ImageCms.getOpenProfile(str(SWOP)), ImageCms.createProfile("sRGB"), "CMYK", "RGB")
    return "#{:02X}{:02X}{:02X}".format(*ImageCms.applyTransform(img, t).getpixel((0, 0)))


def landscape(w=1200, h=700) -> PILImage.Image:
    """The same synthetic landscape as the screenshots (no third-party photo)."""
    y = np.linspace(0, 1, h)[:, None, None]
    sky = (1 - y) * np.array([255, 196, 140]) + y * np.array([120, 120, 190])
    img = PILImage.fromarray(np.broadcast_to(sky, (h, w, 3)).astype(np.uint8).copy())
    d = ImageDraw.Draw(img)
    s = w / 1200
    d.ellipse((470 * s, 250 * s, 690 * s, 470 * s), fill=(255, 236, 170))
    d.rectangle((0, 470 * s, w, h), fill=(24, 44, 74))
    d.polygon([(0, 470 * s), (300 * s, 300 * s), (620 * s, 470 * s)], fill=(42, 64, 100))
    d.polygon([(480 * s, 470 * s), (900 * s, 260 * s), (1200 * s, 470 * s)], fill=(60, 82, 118))
    d.polygon([(0, 610 * s), (w, 560 * s), (w, h), (0, h)], fill=(34, 92, 76))
    return img.filter(ImageFilter.GaussianBlur(2 * s))


# -------------------------------------------------------- Part II diagrams


def wavelength_hex(w: float) -> str:
    """Approximate display colour of a spectral wavelength (Bruton)."""
    if w < 440:
        r, gg, b = -(w - 440) / 60, 0, 1
    elif w < 490:
        r, gg, b = 0, (w - 440) / 50, 1
    elif w < 510:
        r, gg, b = 0, 1, -(w - 510) / 20
    elif w < 580:
        r, gg, b = (w - 510) / 70, 1, 0
    elif w < 645:
        r, gg, b = 1, -(w - 645) / 65, 0
    else:
        r, gg, b = 1, 0, 0
    f = 0.3 + 0.7 * (w - 380) / 40 if w < 420 else (0.3 + 0.7 * (750 - w) / 50 if w > 700 else 1)
    return "#{:02X}{:02X}{:02X}".format(*(round(255 * (c * f) ** 0.8) for c in (r, gg, b)))


def spectrum() -> Drawing:
    W = g.TEXT_W
    d = Drawing(W, 120)
    x0, x1 = 30, W - 30
    n = 220
    for i in range(n):
        w = 380 + (750 - 380) * i / n
        d.add(Rect(x0 + (x1 - x0) * i / n, 50, (x1 - x0) / n + 0.4, 34, fillColor=hc(wavelength_hex(w)), strokeColor=None))

    def px(w):
        return x0 + (x1 - x0) * (w - 380) / 370

    for w in range(400, 751, 50):
        d.add(Line(px(w), 50, px(w), 45, strokeColor=MUTED, strokeWidth=0.6))
        text(d, px(w), 35, f"{w} nm", 7.5, color=MUTED, anchor="middle")
    for w, name in ((415, "ungu"), (470, "biru"), (500, "sian"), (530, "hijau"), (577, "kuning"), (600, "oranye"),
                    (670, "merah")):
        text(d, px(w), 90, name, 8.5, "Sans-Semi", anchor="middle")
    text(d, x0, 14, "← ultraviolet (tak terlihat)", 8, color=MUTED)
    text(d, x1, 14, "inframerah (tak terlihat) →", 8, color=MUTED, anchor="end")
    text(d, W / 2, 106, "cahaya yang bisa dilihat mata manusia", 8.5, "Sans-It", MUTED, "middle")
    return d


def cone_curves() -> Drawing:
    W = g.TEXT_W
    d = Drawing(W, 170)
    x0, x1, y0, y1 = 40, W - 20, 30, 150
    d.add(Line(x0, y0, x1, y0, strokeColor=MUTED, strokeWidth=0.7))
    d.add(Line(x0, y0, x0, y1, strokeColor=MUTED, strokeWidth=0.7))

    def px(w):
        return x0 + (x1 - x0) * (w - 380) / 320

    for w in range(400, 701, 50):
        text(d, px(w), y0 - 12, str(w), 7.5, color=MUTED, anchor="middle")
    text(d, x1, y0 - 24, "panjang gelombang (nm)", 7.5, color=MUTED, anchor="end")
    text(d, x0 - 6, y1 - 4, "kepekaan", 7.5, color=MUTED, anchor="end")
    curves = [("S (biru)", 440, 26, "#3B6FD8"), ("M (hijau)", 535, 42, "#2E9E4F"), ("L (merah)", 565, 48, "#D8452F")]
    for name, peak, width, col in curves:
        pts = []
        for w in range(380, 701, 4):
            pts += [px(w), y0 + (y1 - y0) * math.exp(-((w - peak) / width) ** 2 / 2)]
        d.add(PolyLine(pts, strokeColor=hc(col), strokeWidth=1.8))
        text(d, px(peak), y1 + 4, name, 8.5, "Sans-Semi", col, "middle")
    pts = []
    for w in range(380, 701, 4):
        pts += [px(w), y0 + 0.8 * (y1 - y0) * math.exp(-((w - 498) / 40) ** 2 / 2)]
    d.add(PolyLine(pts, strokeColor=hc("#8A8F96"), strokeWidth=1.2, strokeDashArray=[3, 2]))
    text(d, px(498) - 4, y0 + 0.8 * (y1 - y0) - 14, "batang", 8, "Sans-It", "#8A8F96", "end")
    return d


def venn(kind: str) -> Path:
    n = 640
    yy, xx = np.mgrid[0:n, 0:n]
    centers, r = [(320, 250), (245, 380), (395, 380)], 160
    masks = [((xx - cx) ** 2 + (yy - cy) ** 2) <= r * r for cx, cy in centers]
    if kind == "add":
        img = np.zeros((n, n, 3))
        for i, m in enumerate(masks):
            img[..., i] += m * 255
        names = ["Merah", "Hijau", "Biru"]
    else:
        img = np.full((n, n, 3), 255.0)
        for m, ink_ in zip(masks, [(0, 255, 255), (255, 0, 255), (255, 255, 0)]):
            img *= np.where(m[..., None], np.array(ink_) / 255, 1)
        names = ["Cyan", "Magenta", "Kuning"]
    pic = PILImage.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(pic)
    f = font(30)
    spots = [(320, 135), (150, 450), (490, 450)]
    for (x, y), name in zip(spots, names):
        rgb = pic.getpixel((x, y))
        lum = 0.3 * rgb[0] + 0.59 * rgb[1] + 0.11 * rgb[2]
        d.text((x, y), name, font=f, anchor="mm", fill=(0, 0, 0) if lum > 140 else (255, 255, 255))
    center = "Putih" if kind == "add" else "Hitam"
    d.text((320, 340), center, font=font(22), anchor="mm", fill=(0, 0, 0) if kind == "add" else (255, 255, 255))
    return save(pic, f"venn-{kind}")


def tint_tone_shade() -> Drawing:
    W = g.TEXT_W
    base = ok(0.6, 0.15, 30)
    rows = [("Tint", "dicampur putih", "#FFFFFF"), ("Tone", "dicampur abu-abu", "#8C8C8C"),
            ("Shade", "dicampur hitam", "#000000")]
    d = Drawing(W, 150)
    for i, (name, note, target) in enumerate(rows):
        y = 112 - i * 46
        text(d, 0, y + 12, name, 10.5, "Sans-Bold")
        text(d, 0, y, note, 8, color=MUTED)
        chips(d, 110, y - 4, gradient([base, target], 9, "oklab"), size=36, gap=4)
    text(d, 110, 2, "warna asli di kotak paling kiri", 8, "Sans-It", MUTED)
    return d


ITTEN = [("kuning", "#F4D81C", "P"), ("kuning-oranye", "#F7B21E", "T"), ("oranye", "#F08A1D", "S"),
         ("merah-oranye", "#E85A20", "T"), ("merah", "#D7262B", "P"), ("merah-ungu", "#A6265F", "T"),
         ("ungu", "#6C2C86", "S"), ("biru-ungu", "#433A91", "T"), ("biru", "#1F5DAA", "P"),
         ("biru-hijau", "#13878C", "T"), ("hijau", "#3CA24A", "S"), ("kuning-hijau", "#A6C63A", "T")]


def painter_wheel() -> Drawing:
    W = g.TEXT_W
    d = Drawing(W, 270)
    cx, cy, r, r_in = W / 2, 135, 100, 52
    for i, (name, col, kind) in enumerate(ITTEN):
        mid = 90 - i * 30
        d.add(Wedge(cx, cy, r, mid - 15, mid + 15, radius1=r_in, fillColor=hc(col), strokeColor=colors.white,
                    strokeWidth=1.5))
        a = math.radians(mid)
        tx, ty = cx + (r + r_in) / 2 * math.cos(a), cy + (r + r_in) / 2 * math.sin(a) - 4
        text(d, tx, ty, kind, 10, "Sans-Bold", ink_on(col), "middle")
        lx, ly = cx + (r + 12) * math.cos(a), cy + (r + 12) * math.sin(a) - 3
        anchor = "middle" if abs(math.cos(a)) < 0.3 else ("start" if math.cos(a) > 0 else "end")
        text(d, lx, ly, name, 8.5, anchor=anchor)
    text(d, cx, cy + 6, "P = primer", 8, "Sans-Semi", anchor="middle")
    text(d, cx, cy - 5, "S = sekunder", 8, "Sans-Semi", anchor="middle")
    text(d, cx, cy - 16, "T = tersier", 8, "Sans-Semi", anchor="middle")
    return d


def warm_cool() -> Drawing:
    W = g.TEXT_W
    d = Drawing(W, 110)
    warm = [c for _, c, _ in ITTEN[:6]]
    cool = [c for _, c, _ in ITTEN[6:]]
    for i, (label, row, note) in enumerate((("Hangat", warm, "kuning sampai merah-ungu: terasa dekat, aktif, bersemangat"),
                                            ("Dingin", cool, "ungu sampai kuning-hijau: terasa jauh, tenang, sejuk"))):
        y = 66 - i * 52
        text(d, 0, y + 12, label, 11, "Sans-Bold")
        chips(d, 70, y, row, size=34, gap=3)
        text(d, 70 + 6 * 37 + 10, y + 12, note, 8.5, color=MUTED)
    return d


def value_scale() -> Drawing:
    W = g.TEXT_W
    d = Drawing(W, 70)
    size = (W - 10 * 4) / 11
    for i in range(11):
        h = ok(i / 10, 0, 0)
        d.add(Rect(i * (size + 4), 22, size, 40, fillColor=hc(h), strokeColor=EDGE, strokeWidth=0.5))
        text(d, i * (size + 4) + size / 2, 8, f"{i * 10}%", 8, color=MUTED, anchor="middle")
    return d


def saturation_row() -> Drawing:
    W = g.TEXT_W
    d = Drawing(W, 64)
    size = (W - 9 * 4) / 10
    for i in range(10):
        h = ok(0.62, 0.02 * i, 145)
        d.add(Rect(i * (size + 4), 20, size, 40, fillColor=hc(h), strokeColor=EDGE, strokeWidth=0.5))
    text(d, 0, 6, "kusam (mendekati abu-abu)", 8, color=MUTED)
    text(d, W, 6, "jenuh / pekat", 8, color=MUTED, anchor="end")
    return d


def tinted_neutrals() -> Drawing:
    W = g.TEXT_W
    d = Drawing(W, 150)
    rows = [("Netral murni", 0, 0), ("Netral hangat", 0.014, 70), ("Netral dingin", 0.016, 250)]
    for i, (name, c, h) in enumerate(rows):
        y = 104 - i * 46
        text(d, 0, y + 12, name, 10, "Sans-Semi")
        chips(d, 110, y, [ok(L, c, h) for L in (0.97, 0.9, 0.8, 0.68, 0.55, 0.42, 0.3, 0.2)], size=38, gap=4)
    return d


def itten_contrasts() -> Drawing:
    W = g.TEXT_W
    cols, cw, ch = 4, W / 4, 128
    d = Drawing(W, 2 * ch)
    panels = [
        ("1. Kontras rona", "warna murni berbeda", lambda d, x, y: [
            d.add(Rect(x + 6 + i * 34, y + 18, 30, 30, fillColor=hc(c), strokeColor=None))
            for i, c in enumerate(("#D7262B", "#F4D81C", "#1F5DAA"))]),
        ("2. Terang-gelap", "beda terang", lambda d, x, y: [
            d.add(Rect(x + 6, y + 8, 50, 50, fillColor=hc(ok(0.25, 0.06, 260)), strokeColor=None)),
            d.add(Rect(x + 56, y + 8, 50, 50, fillColor=hc(ok(0.93, 0.04, 260)), strokeColor=None))]),
        ("3. Panas-dingin", "terang sama, suhu beda", lambda d, x, y: [
            d.add(Rect(x + 6, y + 8, 50, 50, fillColor=hc(ok(0.7, 0.15, 55)), strokeColor=None)),
            d.add(Rect(x + 56, y + 8, 50, 50, fillColor=hc(ok(0.7, 0.11, 210)), strokeColor=None))]),
        ("4. Komplementer", "berseberangan di roda", lambda d, x, y: [
            d.add(Rect(x + 6, y + 8, 50, 50, fillColor=hc(ok(0.6, 0.19, 28)), strokeColor=None)),
            d.add(Rect(x + 56, y + 8, 50, 50, fillColor=hc(ok(0.6, 0.15, 160)), strokeColor=None))]),
        ("5. Simultan", "abu-abu yang sama", lambda d, x, y: [
            d.add(Rect(x + 6, y + 8, 50, 50, fillColor=hc(ok(0.7, 0.16, 55)), strokeColor=None)),
            d.add(Rect(x + 56, y + 8, 50, 50, fillColor=hc(ok(0.55, 0.12, 200)), strokeColor=None)),
            d.add(Rect(x + 19, y + 21, 24, 24, fillColor=hc("#8C8C8C"), strokeColor=None)),
            d.add(Rect(x + 69, y + 21, 24, 24, fillColor=hc("#8C8C8C"), strokeColor=None))]),
        ("6. Kontras saturasi", "pekat dan kusam", lambda d, x, y: [
            d.add(Rect(x + 6, y + 8, 50, 50, fillColor=hc(ok(0.6, 0.17, 300)), strokeColor=None)),
            d.add(Rect(x + 56, y + 8, 50, 50, fillColor=hc(ok(0.6, 0.03, 300)), strokeColor=None))]),
        ("7. Kontras luas", "kuning 1 : ungu 3", lambda d, x, y: [
            d.add(Rect(x + 6, y + 8, 100, 50, fillColor=hc("#6C2C86"), strokeColor=None)),
            d.add(Rect(x + 72, y + 22, 24, 24, fillColor=hc("#F4D81C"), strokeColor=None))]),
    ]
    for i, (title, note, paint) in enumerate(panels):
        col, row = i % cols, i // cols
        x, y = col * cw + 4, (1 - row) * ch + 30
        d.add(Rect(x, y, 112, 66, fillColor=colors.white, strokeColor=EDGE, strokeWidth=0.5))
        paint(d, x, y)
        text(d, x, y - 14, title, 9.5, "Sans-Semi")
        text(d, x, y - 26, note, 8, color=MUTED)
    return d


def simultaneous() -> Drawing:
    W = g.TEXT_W
    d = Drawing(W, 150)
    gray = "#808080"
    bgs = ["#111111", "#F5F5F5", ok(0.78, 0.15, 90), ok(0.42, 0.13, 265)]
    w = (W - 3 * 10) / 4
    for i, bg in enumerate(bgs):
        x = i * (w + 10)
        d.add(Rect(x, 24, w, 120, fillColor=hc(bg), strokeColor=EDGE, strokeWidth=0.5))
        d.add(Rect(x + w / 2 - 22, 62, 44, 44, fillColor=hc(gray), strokeColor=None))
    text(d, W / 2, 6, "Keempat kotak tengah warnanya sama persis: #808080", 9, "Sans-Semi", anchor="middle")
    return d


def grayscale_test() -> Drawing:
    W = g.TEXT_W
    a = [ok(0.68, 0.13, h) for h in (30, 95, 150, 250, 320)]
    b = [ok(L, 0.13, h) for L, h in ((0.35, 260), (0.52, 30), (0.68, 150), (0.82, 95), (0.94, 320))]
    d = Drawing(W, 160)
    for i, (label, row) in enumerate((("Palet A: terang semua mirip", a), ("Palet B: terangnya berjenjang", b))):
        x = i * W / 2
        text(d, x, 148, label, 10, "Sans-Semi")
        chips(d, x, 98, row, size=38, gap=4)
        text(d, x, 84, "dilihat tanpa warna:", 8, color=MUTED)
        chips(d, x, 40, [gray_of(c) for c in row], size=38, gap=4)
        verdict, col = (("hampir tak bisa dibedakan", "#C9252D") if i == 0 else ("tetap jelas berbeda", "#2D9D78"))
        text(d, x, 22, verdict, 9, "Sans-Semi", col)
    return d


def layout_mock(d, x, y, w, h, bg, primary, accent, text_c, surface="#FFFFFF"):
    d.add(Rect(x, y, w, h, fillColor=hc(bg), strokeColor=EDGE, strokeWidth=0.5))
    d.add(Rect(x, y + h - 18, w, 18, fillColor=hc(primary), strokeColor=None))
    d.add(Rect(x + 8, y + h - 12, 30, 6, fillColor=hc(ink_on(primary)), strokeColor=None))
    d.add(Rect(x + 10, y + h - 46, w * 0.55, 9, fillColor=hc(text_c), strokeColor=None))
    for k in range(3):
        d.add(Rect(x + 10, y + h - 60 - k * 8, w * 0.7, 3.5, fillColor=hc(mix(text_c, bg, 0.45)), strokeColor=None))
    d.add(Rect(x + 10, y + h - 100, 46, 14, rx=3, ry=3, fillColor=hc(accent), strokeColor=None))
    d.add(Rect(x + 18, y + h - 95, 30, 4, fillColor=hc(ink_on(accent)), strokeColor=None))
    cw = (w - 30) / 2
    for k in range(2):
        cx = x + 10 + k * (cw + 10)
        d.add(Rect(cx, y + 8, cw, h - 122, fillColor=hc(surface), strokeColor=hc(mix(bg, text_c, 0.12)), strokeWidth=0.5))
        d.add(Rect(cx + 6, y + h - 132, cw * 0.5, 5, fillColor=hc(primary), strokeColor=None))


def proportion_603010() -> Drawing:
    W = g.TEXT_W
    d = Drawing(W, 190)
    bg, primary, accent, txt = "#F4EFE6", "#1F3B4D", "#E07A5F", "#22303A"
    bar_w = W * 0.42
    for i, (pct, col, name, note) in enumerate(((60, bg, "60% dominan", "latar, ruang kosong"),
                                                (30, primary, "30% pendukung", "header, judul, bidang"),
                                                (10, accent, "10% aksen", "tombol, ikon, sorotan"))):
        y = 140 - i * 52
        d.add(Rect(0, y, bar_w * pct / 60, 32, fillColor=hc(col), strokeColor=EDGE, strokeWidth=0.5))
        text(d, 0, y - 11, f"{name}: {note}", 8.5, "Sans-Semi")
    layout_mock(d, W * 0.52, 8, W * 0.48, 172, bg, primary, accent, txt)
    return d


def hierarchy() -> Drawing:
    W = g.TEXT_W
    d = Drawing(W, 170)
    w = (W - 20) / 2
    loud = [ok(0.62, 0.19, 28), ok(0.75, 0.16, 85), ok(0.6, 0.15, 150), ok(0.55, 0.16, 260), ok(0.6, 0.2, 330)]
    calm_accent = ok(0.6, 0.19, 28)
    for i in range(2):
        x = i * (w + 20)
        d.add(Rect(x, 24, w, 140, fillColor=colors.white, strokeColor=EDGE, strokeWidth=0.6))
        for k in range(5):
            bx, by = x + 12 + (k % 3) * ((w - 24) / 3), 120 - (k // 3) * 44
            col = loud[k] if i == 0 else (calm_accent if k == 1 else ok(0.93, 0.005, 250))
            d.add(Rect(bx, by, (w - 24) / 3 - 8, 30, rx=4, ry=4, fillColor=hc(col), strokeColor=None))
            label_col = ink_on(col)
            d.add(Rect(bx + 10, by + 13, 30, 4, fillColor=hc(label_col), strokeColor=None))
        text(d, x + w / 2, 8, "Semua berebut perhatian" if i == 0 else "Satu fokus yang jelas", 9.5, "Sans-Semi",
             "#C9252D" if i == 0 else "#2D9D78", "middle")
    return d


def brand_cards(palette, prf) -> Drawing:
    W = g.TEXT_W
    n = len(palette)
    gap = 8
    w = (W - gap * (n - 1)) / n
    d = Drawing(W, 176)
    for i, (name, h) in enumerate(palette):
        x = i * (w + gap)
        d.add(Rect(x, 70, w, 100, fillColor=hc(h), strokeColor=EDGE, strokeWidth=0.5))
        text(d, x + 6, 154, name, 9, "Sans-Bold", ink_on(h))
        r, gg, b = hex_to_rgb(h)
        L, C, H = to_oklch(h)
        rows = [("HEX", h), ("RGB", f"{r} {gg} {b}"), ("CMYK", cmyk_text(h, prf)), ("OKLCH", f"{L * 100:.0f}% {C:.2f} {H:.0f}")]
        for k, (label, value) in enumerate(rows):
            y = 56 - k * 15
            text(d, x, y, label, 7, "Sans-Semi", MUTED)
            text(d, x + w, y, value, 7.5, anchor="end")
    return d


def semantic() -> Drawing:
    W = g.TEXT_W
    rows = [("Berhasil", "Perubahan berhasil disimpan.", 150), ("Peringatan", "Kuota penyimpanan hampir habis.", 80),
            ("Galat", "Kata sandi salah, coba lagi.", 27), ("Info", "Versi baru tersedia.", 250)]
    d = Drawing(W, 4 * 34 + 6)
    for i, (name, msg, hue) in enumerate(rows):
        y = 3 * 34 + 4 - i * 34
        bg, edge, fg = ok(0.96, 0.03, hue), ok(0.62, 0.15, hue), ok(0.38, 0.1, hue)
        d.add(Rect(0, y, W * 0.74, 28, fillColor=hc(bg), strokeColor=None))
        d.add(Rect(0, y, 4, 28, fillColor=hc(edge), strokeColor=None))
        text(d, 14, y + 10, f"{name}: ", 9.5, "Sans-Bold", fg)
        text(d, 14 + 72, y + 10, msg, 9.5, color=fg)
        text(d, W * 0.76, y + 10, f"teks {fg} di latar {bg}: {format_ratio(contrast_ratio(fg, bg))}", 8, color=MUTED)
    return d


def ui_states() -> Drawing:
    W = g.TEXT_W
    base = (0.55, 0.17, 255)
    states = [("Normal", ok(*base), "#FFFFFF"), ("Hover", ok(base[0] - 0.06, base[1], base[2]), "#FFFFFF"),
              ("Ditekan", ok(base[0] - 0.12, base[1] - 0.02, base[2]), "#FFFFFF"),
              ("Nonaktif", ok(0.9, 0.02, base[2]), ok(0.62, 0.02, base[2])),
              ("Fokus", ok(*base), "#FFFFFF")]
    d = Drawing(W, 84)
    w = (W - 4 * 12) / 5
    for i, (name, bg, fg) in enumerate(states):
        x = i * (w + 12)
        if name == "Fokus":
            d.add(Rect(x - 3, 37, w + 6, 40, rx=8, ry=8, fillColor=None, strokeColor=hc(ok(0.55, 0.17, 255)), strokeWidth=2))
        d.add(Rect(x, 40, w, 34, rx=6, ry=6, fillColor=hc(bg), strokeColor=None))
        text(d, x + w / 2, 53, "Simpan", 10, "Sans-Semi", fg, "middle")
        text(d, x + w / 2, 26, name, 9, "Sans-Semi", anchor="middle")
        text(d, x + w / 2, 14, bg, 7.5, color=MUTED, anchor="middle")
        text(d, x + w / 2, 3, format_ratio(contrast_ratio(fg, bg)), 7.5, color=MUTED, anchor="middle")
    return d


def dark_mode() -> Drawing:
    W = g.TEXT_W
    d = Drawing(W, 190)
    w = (W - 2 * 12) / 3
    vivid, soft = ok(0.55, 0.22, 262), ok(0.72, 0.12, 262)
    panels = [
        ("Mode terang", "#FFFFFF", [ok(0.97, 0.004, 260), ok(0.94, 0.004, 260)], ok(0.25, 0.02, 260), vivid),
        ("Mode gelap yang baik", ok(0.2, 0.006, 260), [ok(0.25, 0.008, 260), ok(0.3, 0.01, 260)], ok(0.93, 0.005, 260), soft),
        ("Kurang tepat", "#000000", ["#000000", "#000000"], "#FFFFFF", "#0000FF"),
    ]
    for i, (name, bg, surfaces, fg, acc) in enumerate(panels):
        x = i * (w + 12)
        d.add(Rect(x, 30, w, 150, fillColor=hc(bg), strokeColor=EDGE, strokeWidth=0.5))
        d.add(Rect(x + 10, 120, w - 20, 50, rx=4, ry=4, fillColor=hc(surfaces[0]), strokeColor=None))
        d.add(Rect(x + 10, 60, w - 20, 52, rx=4, ry=4, fillColor=hc(surfaces[1]), strokeColor=None))
        text(d, x + 18, 152, "Judul kartu", 10, "Sans-Bold", fg)
        text(d, x + 18, 138, "Teks isi dengan kontras cukup.", 8, color=fg)
        text(d, x + 18, 92, "Tautan berwarna", 10, "Sans-Semi", acc)
        text(d, x + 18, 72, f"tautan {format_ratio(contrast_ratio(acc, surfaces[1]))}", 8, color=fg)
        d.add(Rect(x + 10, 38, 60, 16, rx=4, ry=4, fillColor=hc(acc), strokeColor=None))
        text(d, x + w / 2, 14, name, 9.5, "Sans-Semi", "#C9252D" if i == 2 else INK, "middle")
    return d


def text_on_photo() -> tuple[Path, Path]:
    base = landscape(900, 520)
    f_big, f_small = font(64), font(28, bold=False)
    plain = base.copy()
    d = ImageDraw.Draw(plain)
    d.text((60, 150), "Liburan Akhir Tahun", font=f_big, fill=(255, 255, 255))
    d.text((60, 230), "Diskon hingga 40% untuk semua paket", font=f_small, fill=(255, 255, 255))
    scrim = base.copy().convert("RGBA")
    overlay = PILImage.new("RGBA", scrim.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for y in range(scrim.height):
        alpha = int(190 * max(0, 1 - y / (scrim.height * 0.62)))
        od.line([(0, y), (scrim.width, y)], fill=(16, 22, 40, alpha))
    scrim = PILImage.alpha_composite(scrim, overlay).convert("RGB")
    d = ImageDraw.Draw(scrim)
    d.text((60, 150), "Liburan Akhir Tahun", font=f_big, fill=(255, 255, 255))
    d.text((60, 230), "Diskon hingga 40% untuk semua paket", font=f_small, fill=(255, 255, 255))
    return save(plain, "photo-plain"), save(scrim, "photo-scrim")


def text_sizes() -> Drawing:
    W = g.TEXT_W
    d = Drawing(W, 120)
    fg, bg = ok(0.6, 0.02, 260), "#FFFFFF"
    ratio = format_ratio(contrast_ratio(fg, bg))
    d.add(Rect(0, 0, W, 120, fillColor=hc(bg), strokeColor=EDGE, strokeWidth=0.5))
    text(d, 14, 82, "Judul besar tetap terbaca", 24, "Sans-Bold", fg)
    text(d, 14, 56, "Teks isi berukuran kecil dengan warna abu-abu yang sama mulai sulit dibaca di layar kecil.", 9,
         color=fg)
    text(d, 14, 40, "Keterangan foto yang lebih kecil lagi semakin melelahkan mata.", 7, color=fg)
    text(d, 14, 14, f"Semua teks di atas memakai {fg} di atas putih ({ratio}): cukup untuk teks besar, belum cukup untuk teks isi.",
         8, "Sans-It", MUTED)
    return d


OKABE_ITO = ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7", "#000000"]


def dataviz_palettes() -> Drawing:
    W = g.TEXT_W
    d = Drawing(W, 170)
    seq = [ok(0.96 - 0.08 * i, 0.03 + 0.017 * i, 250 - 4 * i) for i in range(8)]
    left = [ok(0.45 + 0.07 * i, 0.14 - 0.03 * i, 250) for i in range(4)]
    right = [ok(0.73 - 0.07 * i, 0.05 + 0.03 * i, 55) for i in range(4)]
    div = left + [ok(0.96, 0.0, 0)] + right
    rows = [("Kategorikal", "kelompok tanpa urutan (Okabe-Ito)", OKABE_ITO),
            ("Sekuensial", "nilai kecil ke besar", seq),
            ("Divergen", "di bawah dan di atas titik tengah", div)]
    for i, (name, note, row) in enumerate(rows):
        y = 124 - i * 56
        text(d, 0, y + 18, name, 10.5, "Sans-Bold")
        text(d, 0, y + 5, note, 8, color=MUTED)
        chips(d, 185, y, row, size=30, gap=2)
    return d


def bar_chart(d, x, y, w, h, values, fills, title):
    n = len(values)
    bw = w / n * 0.7
    for i, (v, f) in enumerate(zip(values, fills)):
        bx = x + i * w / n + (w / n - bw) / 2
        d.add(Rect(bx, y, bw, h * v, fillColor=hc(f), strokeColor=None))
    d.add(Line(x, y, x + w, y, strokeColor=MUTED, strokeWidth=0.6))
    text(d, x, y + h + 8, title, 9.5, "Sans-Semi")


def highlight_charts() -> Drawing:
    W = g.TEXT_W
    vals = [0.55, 0.72, 0.48, 0.95, 0.62, 0.4]
    rainbow = [ok(0.65, 0.17, h) for h in (25, 70, 130, 200, 260, 320)]
    focus = [ok(0.8, 0.0, 0)] * 6
    focus[3] = ok(0.58, 0.18, 30)
    d = Drawing(W, 150)
    w = (W - 30) / 2
    bar_chart(d, 0, 20, w, 110, vals, rainbow, "Semua batang berwarna")
    bar_chart(d, w + 30, 20, w, 110, vals, focus, "Satu warna untuk pesan utama")
    text(d, w + 30 + 3.5 * w / 6, 20 + 110 * 0.95 + 4, "tertinggi", 8, "Sans-Semi", focus[3], "middle")
    return d


def cvd_compare() -> Drawing:
    W = g.TEXT_W
    rainbow = ["#FF0000", "#FF8000", "#FFFF00", "#00C000", "#0080FF", "#8000FF"]
    oi = OKABE_ITO[:7]
    d = Drawing(W, 150)
    for i, (label, row) in enumerate((("Pelangi biasa", rainbow), ("Okabe-Ito", oi))):
        x = i * W / 2
        text(d, x, 136, label, 10, "Sans-Semi")
        chips(d, x, 96, row, size=28, gap=3)
        text(d, x, 82, "dilihat penderita deuteranopia:", 8, color=MUTED)
        chips(d, x, 44, [simulate_hex(c, "deutan", 1.0) for c in row], size=28, gap=3)
        verdict = ("merah, oranye, hijau tampak mirip", "#C9252D") if i == 0 else ("masih bisa dibedakan", "#2D9D78")
        text(d, x, 26, verdict[0], 9, "Sans-Semi", verdict[1])
    return d


def separations() -> tuple[Path, list[Path]]:
    """A picture split into its four printing plates through the SWOP profile."""
    img = landscape(600, 350)
    if SWOP.exists():
        t = ImageCms.buildTransform(ImageCms.createProfile("sRGB"), ImageCms.getOpenProfile(str(SWOP)), "RGB", "CMYK",
                                    ImageCms.Intent.RELATIVE_COLORIMETRIC)
        cmyk = ImageCms.applyTransform(img, t)
    else:
        cmyk = img.convert("CMYK")
    arr = np.asarray(cmyk).astype(float) / 255
    inks = [(0, 174, 239), (236, 0, 140), (255, 242, 0), (35, 31, 32)]
    plates = []
    for i, (name, ink_) in enumerate(zip("CMYK", inks)):
        v = arr[..., i:i + 1]
        plate = 255 * (1 - v) + np.array(ink_) * v
        plates.append(save(PILImage.fromarray(plate.astype(np.uint8)), f"plate-{name}"))
    return save(img, "plate-full"), plates


def halftone() -> Drawing:
    W = g.TEXT_W
    d = Drawing(W, 96)
    steps_ = [10, 25, 50, 75, 100]
    w = W / len(steps_)
    for i, pct in enumerate(steps_):
        x0 = i * w + 10
        d.add(Rect(x0, 24, 64, 64, fillColor=colors.white, strokeColor=EDGE, strokeWidth=0.5))
        if pct == 100:
            d.add(Rect(x0, 24, 64, 64, fillColor=hc("#00AEEF"), strokeColor=None))
        else:
            r = 16 * math.sqrt(pct / 100 / math.pi)
            for gx in range(4):
                for gy in range(4):
                    d.add(Circle(x0 + 8 + gx * 16, 32 + gy * 16, r, fillColor=hc("#00AEEF"), strokeColor=None))
        text(d, x0 + 32, 8, f"cyan {pct}%", 8.5, "Sans-Semi", anchor="middle")
    return d


def blacks() -> Drawing | None:
    rows = [("100 K saja", (0, 0, 0, 100)), ("Rich black", (60, 40, 40, 100)), ("Hitam berlebihan", (100, 100, 100, 100))]
    looks = [cmyk_to_hex(*v) for _, v in rows]
    if None in looks:
        return None
    W = g.TEXT_W
    d = Drawing(W, 120)
    w = (W - 2 * 14) / 3
    for i, ((name, v), look) in enumerate(zip(rows, looks)):
        x = i * (w + 14)
        d.add(Rect(x, 40, w, 72, fillColor=hc(look), strokeColor=None))
        text(d, x, 26, name, 10, "Sans-Bold")
        text(d, x, 12, f"C{v[0]} M{v[1]} Y{v[2]} K{v[3]} · total tinta {sum(v)}%", 8, color=MUTED)
    return d


def bleed() -> Drawing:
    W = g.TEXT_W
    d = Drawing(W, 230)
    x, y, w, h = 120, 20, 180, 200
    m = 14
    d.add(Rect(x - m, y - m + 10, w + 2 * m, h + 2 * m - 20, fillColor=hc("#FDE7E7"), strokeColor=hc("#E04646"),
               strokeWidth=0.8, strokeDashArray=[3, 2]))
    d.add(Rect(x, y + 10 - 0, w, h - 20, fillColor=hc(ok(0.9, 0.04, 220)), strokeColor=INK, strokeWidth=1))
    d.add(Rect(x + m, y + 10 + m, w - 2 * m, h - 20 - 2 * m, fillColor=None, strokeColor=hc("#2D9D78"), strokeWidth=0.8,
               strokeDashArray=[2, 2]))
    text(d, x + w / 2, y + h / 2, "Isi penting", 10, "Sans-Semi", anchor="middle")
    text(d, x + w / 2, y + h / 2 - 12, "(teks, logo)", 8, color=MUTED, anchor="middle")
    lx = x + w + 30
    for i, (col, name, note) in enumerate((("#E04646", "Bleed (lebihan)", "latar diperpanjang 3 mm keluar garis potong"),
                                           ("#1F1F1F", "Garis potong (trim)", "ukuran akhir setelah dipotong"),
                                           ("#2D9D78", "Area aman", "teks dan logo minimal 3-5 mm di dalam garis potong"))):
        ty = y + h - 40 - i * 46
        d.add(Rect(lx, ty, 14, 14, fillColor=None, strokeColor=hc(col), strokeWidth=1.2))
        text(d, lx + 22, ty + 4, name, 10, "Sans-Bold")
        text(d, lx + 22, ty - 8, note, 8, color=MUTED)
    return d


LOCUS = [(380, 0.1741, 0.0050), (450, 0.1566, 0.0177), (460, 0.1440, 0.0297), (470, 0.1241, 0.0578),
         (475, 0.1096, 0.0868), (480, 0.0913, 0.1327), (485, 0.0687, 0.2007), (490, 0.0454, 0.2950),
         (495, 0.0235, 0.4127), (500, 0.0082, 0.5384), (505, 0.0039, 0.6548), (510, 0.0139, 0.7502),
         (515, 0.0389, 0.8120), (520, 0.0743, 0.8338), (525, 0.1142, 0.8262), (530, 0.1547, 0.8059),
         (540, 0.2296, 0.7543), (550, 0.3016, 0.6923), (560, 0.3731, 0.6245), (570, 0.4441, 0.5547),
         (580, 0.5125, 0.4866), (590, 0.5752, 0.4242), (600, 0.6270, 0.3725), (610, 0.6658, 0.3340),
         (620, 0.6915, 0.3083), (640, 0.7190, 0.2809), (660, 0.7300, 0.2700), (700, 0.7347, 0.2653)]
GAMUTS = [("sRGB", [(0.64, 0.33), (0.30, 0.60), (0.15, 0.06)], (255, 255, 255)),
          ("Display P3", [(0.68, 0.32), (0.265, 0.69), (0.15, 0.06)], (40, 40, 40)),
          ("Adobe RGB", [(0.64, 0.33), (0.21, 0.71), (0.15, 0.06)], (20, 90, 200))]


def chromaticity() -> Path:
    W, H = 1000, 1080
    sx, sy, ox, oy = 1150, 1150, 70, 60

    def px(x, y):
        return ox + x * sx, H - oy - y * sy

    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    x = (xx - ox) / sx
    y = (H - oy - yy) / sy
    y_safe = np.where(y > 1e-4, y, 1e-4)
    X, Z = x / y_safe, (1 - x - y) / y_safe
    M = np.array([[3.2406, -1.5372, -0.4986], [-0.9689, 1.8758, 0.0415], [0.0557, -0.2040, 1.0570]])
    lin = np.einsum("ij,hwj->hwi", M, np.stack([X, np.ones_like(X), Z], -1))
    lin = np.clip(lin, 0, None)
    lin = lin / np.maximum(lin.max(-1, keepdims=True), 1e-6)
    rgb = np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * lin ** (1 / 2.4) - 0.055)
    mask = PILImage.new("L", (W, H), 0)
    poly = [px(a, b) for _, a, b in LOCUS]
    ImageDraw.Draw(mask).polygon(poly, fill=255)
    m = np.asarray(mask)[..., None] / 255
    img = PILImage.fromarray((255 * (m * (0.25 + 0.75 * rgb) + (1 - m) * 1)).clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    d.polygon(poly, outline=(90, 90, 90), width=2)
    f, fs = font(30), font(22, bold=False)
    for name, pts, col in GAMUTS:
        d.polygon([px(a, b) for a, b in pts], outline=col, width=5)
    labels = {"sRGB": (0.33, 0.52), "Display P3": (0.27, 0.71), "Adobe RGB": (0.08, 0.72)}
    for name, (a, b) in labels.items():
        col = next(c for n, _, c in GAMUTS if n == name)
        d.text(px(a, b), name, font=f, fill=col, anchor="lm", stroke_width=3 if col == (255, 255, 255) else 0,
               stroke_fill=(60, 60, 60))
    for wl, a, b in LOCUS:
        if wl in (460, 480, 500, 520, 560, 600, 700):
            tx, ty = px(a, b)
            d.text((tx + (12 if a > 0.3 else -12), ty), f"{wl}", font=fs, fill=(80, 80, 80),
                   anchor="lm" if a > 0.3 else "rm")
    wx, wy = px(0.3127, 0.3290)
    d.ellipse((wx - 7, wy - 7, wx + 7, wy + 7), fill=(0, 0, 0))
    d.text((wx + 12, wy + 14), "putih D65", font=fs, fill=(0, 0, 0))
    for t in range(0, 9):
        X0, Y0 = px(t / 10, 0)
        d.line([(X0, Y0), (X0, Y0 + 8)], fill=(120, 120, 120), width=2)
        d.text((X0, Y0 + 12), f"0.{t}" if t else "0", font=fs, fill=(120, 120, 120), anchor="mt")
        X1, Y1 = px(0, t / 10)
        d.line([(X1 - 8, Y1), (X1, Y1)], fill=(120, 120, 120), width=2)
        d.text((X1 - 12, Y1), f"0.{t}" if t else "0", font=fs, fill=(120, 120, 120), anchor="rm")
    return save(img, "chromaticity")


def banding() -> Path:
    w, h = 1200, 220
    t = np.linspace(0, 1, w)
    ramp = np.stack([18 + 50 * t, 24 + 70 * t, 50 + 140 * t], -1)
    smooth = np.broadcast_to(ramp, (h // 2, w, 3))
    steps_ = np.floor(t * 14) / 14
    rough = np.stack([18 + 50 * steps_, 24 + 70 * steps_, 50 + 140 * steps_], -1)
    rough = np.broadcast_to(rough, (h // 2, w, 3))
    img = np.concatenate([smooth, np.full((8, w, 3), 255.0), rough], 0)
    return save(PILImage.fromarray(img.astype(np.uint8)), "banding")


def vibrating() -> Drawing:
    W = g.TEXT_W
    d = Drawing(W, 96)
    w = (W - 12) / 2
    red, blue = ok(0.6, 0.22, 28), ok(0.5, 0.2, 262)
    fixed_bg = ok(0.3, 0.12, 262)
    for i, (bg, fg, label) in enumerate(((blue, red, "Bergetar: merah di atas biru"),
                                         (fixed_bg, ok(0.92, 0.04, 28), "Lebih baik: beda terang yang jelas"))):
        x = i * (w + 12)
        d.add(Rect(x, 26, w, 64, fillColor=hc(bg), strokeColor=None))
        text(d, x + 14, 50, "PROMO SPESIAL", 22, "Sans-Bold", fg)
        text(d, x, 12, f"{label} ({format_ratio(contrast_ratio(fg, bg))})", 8.5, "Sans-Semi",
             "#C9252D" if i == 0 else "#2D9D78")
    return d


def palette_strip(hexes, labels=None, size=None) -> Drawing:
    W = g.TEXT_W
    n = len(hexes)
    size = size or min(70, (W - (n - 1) * 6) / n)
    top = 30 if labels else 18
    d = Drawing(W, size * 0.8 + top + 4)
    for i, h in enumerate(hexes):
        x = i * (size + 6)
        d.add(Rect(x, top, size, size * 0.8, fillColor=hc(h), strokeColor=EDGE, strokeWidth=0.5))
        if labels:
            text(d, x + size / 2, 17, labels[i], 8, "Sans-Semi", anchor="middle")
        text(d, x + size / 2, 5, h, 7, color=MUTED, anchor="middle")
    return d


# ------------------------------------------------------------------ Part II


def write(module) -> None:
    global g
    g = module
    P, section, sub, bullets, steps, box, table = g.P, g.section, g.sub, g.bullets, g.steps, g.box, g.table
    drawing, figure, figures, K, M = g.drawing, g.figure, g.figures, g.K, g.M
    prf = proofer()

    g.part("BAGIAN II", "Ilmu Warna untuk Desainer Grafis",
           "Pengetahuan yang dipakai desainer setiap hari: bagaimana mata melihat warna, cara membicarakannya, kontras, "
           "komposisi, makna, warna merek, warna di layar dan di kertas, grafik, serta manajemen warna. "
           "Setiap bab ditutup dengan cara mempraktikkannya di Colorize.")

    # 15 ---------------------------------------------------------------
    g.chapter("Cahaya, Mata, dan Warna")
    P("Sebelum membahas cara memilih warna, ada baiknya tahu dari mana warna berasal. Pemahaman ini menjelaskan banyak "
      "hal yang nanti terasa aneh: kenapa warna di layar berbeda dengan di kertas, kenapa warna yang sama tampak lain di "
      "latar berbeda, dan kenapa sebagian orang tidak bisa membedakan merah dan hijau.", "lead")
    section("Warna adalah cahaya")
    P("Cahaya adalah gelombang. Mata kita hanya bisa menangkap sebagian kecilnya, kira-kira dari panjang gelombang 380 sampai "
      "700 nanometer. Gelombang yang lebih pendek terlihat ungu dan biru, yang lebih panjang terlihat oranye dan merah. "
      "Cahaya matahari berisi semua panjang gelombang sekaligus, dan kita melihatnya sebagai putih.")
    drawing(spectrum(), fig("Spektrum cahaya tampak"))
    box("term", "<b>Nanometer (nm)</b> adalah satu per satu miliar meter. Satuan ini dipakai untuk panjang gelombang cahaya.")
    P("Benda tidak \"memiliki\" warna. Benda <b>memantulkan</b> sebagian cahaya dan <b>menyerap</b> sisanya. Tomat terlihat merah "
      "karena memantulkan gelombang panjang dan menyerap yang lain. Karena itu warna benda selalu bergantung pada cahaya "
      "yang menyinarinya: kain yang sama tampak berbeda di bawah lampu kuning dan di bawah sinar matahari.")
    section("Bagaimana mata menangkap warna")
    P("Di bagian belakang mata ada dua jenis sel penangkap cahaya:")
    bullets(["<b>Sel batang</b>: sangat peka, bekerja dalam gelap, tetapi tidak membedakan warna. Itu sebabnya di malam hari "
             "semuanya tampak abu-abu.",
             "<b>Sel kerucut</b>: bekerja di tempat terang dan membedakan warna. Ada tiga jenis: S (peka biru), M (peka hijau), "
             "dan L (peka merah). Otak membandingkan sinyal ketiganya untuk menentukan warna."])
    drawing(cone_curves(), fig("Kepekaan tiga jenis sel kerucut dan sel batang (disederhanakan)"))
    P("Karena mata hanya memakai tiga jenis sensor, layar cukup memakai tiga warna cahaya (merah, hijau, biru) untuk meniru "
      "hampir semua warna. Ini juga menjelaskan buta warna: bila salah satu jenis kerucut lemah atau tidak ada, beberapa "
      "warna terlihat sama. Sekitar 8% laki-laki dan 0,5% perempuan mengalaminya.")
    box("term", "<b>Metamerisme</b>: dua warna yang tampak sama di bawah satu jenis lampu, tetapi berbeda di bawah lampu lain. "
        "Contohnya, dua kain hitam yang serasi di toko ternyata satu kebiruan dan satu kecokelatan di luar ruangan. Untuk "
        "pekerjaan cetak dan produk, periksa warna di bawah cahaya siang atau lampu standar.")
    section("Dua cara mencampur warna")
    P("Ada dua cara warna bercampur, dan keduanya bekerja berlawanan:")
    figures([(venn("add"), fig("Aditif (cahaya): merah + hijau + biru = putih")),
             (venn("sub"), fig("Subtraktif (tinta): cyan + magenta + kuning = (hampir) hitam"))], 0.42)
    table([
        ["", "Aditif", "Subtraktif"],
        ["Bahan", "Cahaya", "Tinta, cat, pigmen"],
        ["Warna dasar", "Merah, hijau, biru (RGB)", "Cyan, magenta, kuning (CMY), ditambah hitam (K)"],
        ["Semakin banyak dicampur", "Semakin terang, sampai putih", "Semakin gelap, sampai hampir hitam"],
        ["Dipakai di", "Layar HP, monitor, TV, proyektor", "Mesin cetak, printer, cat"],
    ], [0.26, 0.34, 0.4])
    box("note", "Di sekolah kita diajari warna dasar merah, kuning, biru (RYB). Ini adalah sistem pelukis yang sudah dipakai "
        "berabad-abad dan masih berguna untuk teori komposisi. Mesin cetak memakai cyan, magenta, kuning karena pigmen ini "
        "menghasilkan campuran yang lebih bersih. Colorize menyediakan keduanya: roda Perceptual dan roda Artist (RYB).")
    section("Mata mudah tertipu")
    P("Otak tidak mengukur warna seperti alat ukur. Otak selalu membandingkan warna dengan sekitarnya dan menyesuaikan diri "
      "dengan cahaya ruangan (seperti fitur <i>white balance</i> di kamera). Akibatnya:")
    bullets(["Warna yang sama terlihat berbeda di latar berbeda (dibahas di Bab 17).",
             "Setelah menatap layar lama, mata terbiasa, sehingga penilaian warna bisa bergeser. Istirahatkan mata sebelum "
             "keputusan warna yang penting.",
             "Cahaya ruangan memengaruhi penilaian. Ruang kerja dengan lampu netral dan dinding tidak berwarna mencolok "
             "membantu penilaian yang lebih adil."])
    box("tip", "Di Colorize, tampilan aplikasi sengaja abu-abu netral agar tidak memengaruhi mata Anda. Saat menilai palet, "
        "pakai tema Medium Gray dan hindari wallpaper yang sangat berwarna di sekitar jendela.")

    # 16 ---------------------------------------------------------------
    g.chapter("Bahasa Warna")
    P("Desainer membicarakan warna dengan beberapa istilah tetap. Menguasai istilah ini membuat Anda lebih mudah memberi dan "
      "menerima masukan, misalnya \"warnanya terlalu jenuh\" atau \"butuh value yang lebih gelap\".", "lead")
    section("Tiga sifat warna")
    table([
        ["Sifat", "Pertanyaan yang dijawab", "Nama lain"],
        ["Hue (rona)", "Warna apa? Merah, biru, atau hijau?", "Di Colorize: H pada OKLCH"],
        ["Value (nilai terang)", "Seberapa terang atau gelap?", "Lightness, brightness. Di Colorize: L"],
        ["Saturation (kejenuhan)", "Seberapa murni atau pekat? Seberapa jauh dari abu-abu?", "Chroma, intensitas. Di Colorize: C"],
    ], [0.26, 0.44, 0.3])
    sub("Value: sifat yang paling penting")
    drawing(value_scale(), fig("Skala value dari hitam ke putih"))
    P("Banyak desainer berpengalaman berkata, <i>\"value does all the work, color gets all the credit\"</i>: terang-gelap yang "
      "bekerja keras, warna yang mendapat pujian. Mata membaca bentuk, teks, dan kedalaman terutama dari perbedaan terang. "
      "Bila value-nya sudah benar, hampir semua pilihan rona akan tampak baik.")
    sub("Saturasi")
    drawing(saturation_row(), fig("Hijau yang sama, dari kusam sampai jenuh"))
    P("Warna jenuh menarik perhatian dan terasa energik, tetapi melelahkan bila terlalu banyak. Warna kusam terasa tenang, "
      "dewasa, dan elegan. Kebanyakan desain yang baik memakai banyak warna kusam atau netral dan sedikit warna jenuh.")
    section("Tint, tone, dan shade")
    drawing(tint_tone_shade(), fig("Satu warna merah, dicampur putih, abu-abu, dan hitam"))
    bullets(["<b>Tint</b>: dicampur putih. Lebih terang dan lembut, misalnya warna pastel.",
             "<b>Tone</b>: dicampur abu-abu. Lebih kalem dan canggih, sering dipakai merek mode dan interior.",
             "<b>Shade</b>: dicampur hitam. Lebih dalam dan berat, cocok untuk teks berwarna dan latar gelap."])
    box("tip", "Panel <b>Scale</b> di Colorize membuat tint dan shade sekaligus (50 sampai 950). Untuk tone, turunkan Chroma "
        "di color picker sambil menjaga Lightness.")
    section("Roda warna pelukis: primer, sekunder, tersier")
    drawing(painter_wheel(), fig("Roda 12 warna ala Johannes Itten"))
    bullets(["<b>Primer</b>: merah, kuning, biru. Dalam teori pelukis, warna ini tidak bisa dibuat dari campuran warna lain.",
             "<b>Sekunder</b>: oranye, hijau, ungu. Campuran dua warna primer.",
             "<b>Tersier</b>: enam warna di antaranya, seperti merah-oranye dan biru-hijau. Campuran primer dan sekunder di sebelahnya."])
    section("Warna hangat dan dingin")
    drawing(warm_cool(), fig("Separuh roda yang hangat dan separuh yang dingin"))
    P("Warna hangat terasa maju dan mendekat; warna dingin terasa mundur dan menjauh. Pelukis memakai efek ini untuk "
      "kedalaman: latar belakang pemandangan dibuat lebih dingin dan pudar, objek depan lebih hangat dan jenuh. Di desain, "
      "tombol hangat di atas latar dingin akan langsung menonjol.")
    box("note", "Suhu warna itu relatif. Hijau kekuningan terasa hangat di sebelah biru, tetapi dingin di sebelah oranye. "
        "Bahkan abu-abu bisa hangat (sedikit kekuningan) atau dingin (sedikit kebiruan).")
    section("Warna netral")
    P("Hitam, putih, abu-abu, krem, dan cokelat muda disebut <b>netral</b>. Warna netral adalah tulang punggung sebuah desain: "
      "latar, teks, garis, dan ruang kosong. Netral murni (tanpa warna sama sekali) sering terasa dingin dan kaku. Netral "
      "yang diberi sedikit rona terasa lebih hidup dan menyatu dengan warna merek.")
    drawing(tinted_neutrals(), fig("Netral murni, netral hangat, dan netral dingin"))
    box("tip", "Membuat netral bernuansa di Colorize: buka color picker, isi H dengan rona warna merek Anda, lalu isi C sangat "
        "kecil (0,01 sampai 0,02) dan atur L sesuai kebutuhan. Simpan beberapa langkah L sebagai skala abu-abu merek.")

    # 17 ---------------------------------------------------------------
    g.chapter("Kontras dan Ilusi Warna")
    P("Kontras adalah perbedaan. Tanpa kontras tidak ada yang menonjol; dengan terlalu banyak kontras semuanya berteriak. "
      "Johannes Itten, guru di sekolah desain Bauhaus, merumuskan tujuh jenis kontras warna yang sampai sekarang dipakai "
      "desainer untuk menganalisis karya.", "lead")
    section("Tujuh kontras warna")
    drawing(itten_contrasts(), fig("Tujuh kontras warna menurut Itten"))
    table([
        ["Kontras", "Penjelasan", "Contoh pemakaian"],
        ["Rona", "Warna murni yang berbeda berdampingan.", "Poster anak-anak, mainan, tampilan festival."],
        ["Terang-gelap", "Perbedaan value. Kontras paling kuat untuk keterbacaan.", "Teks, ikon, foto hitam-putih."],
        ["Panas-dingin", "Warna hangat di samping warna dingin dengan terang mirip.", "Memberi kedalaman, membuat tombol menonjol."],
        ["Komplementer", "Warna yang berseberangan di roda saling menguatkan.", "Logo olahraga, label diskon, sorotan."],
        ["Simultan", "Mata \"mewarnai\" warna netral dengan lawan dari latarnya.", "Waspadai saat memilih abu-abu di atas latar berwarna."],
        ["Saturasi", "Warna jenuh di antara warna kusam akan tampak lebih jenuh.", "Menonjolkan satu produk di foto katalog."],
        ["Luas (proporsi)", "Warna terang perlu area lebih kecil agar seimbang dengan warna gelap.", "Aksen kuning kecil di desain ungu."],
    ], [0.18, 0.44, 0.38])
    section("Warna yang sama, terlihat berbeda")
    drawing(simultaneous(), fig("Kontras simultan: satu abu-abu, empat kesan"))
    P("Abu-abu di atas hitam tampak lebih terang; di atas putih tampak lebih gelap. Di atas kuning ia tampak sedikit kebiruan, "
      "di atas biru sedikit kekuningan. Josef Albers menulis satu buku penuh tentang efek ini, <i>Interaction of Color</i> (1963), "
      "dengan kesimpulan: warna hampir tidak pernah terlihat seperti aslinya.")
    bullets(["Selalu nilai warna <b>di tempat ia akan dipakai</b>, bukan sebagai kotak tunggal di latar putih.",
             "Logo yang sama bisa perlu sedikit penyesuaian di latar gelap dan latar terang.",
             f"Di Colorize, pakai {M('Palette › Preview Mockup')} untuk melihat warna bersama warna lainnya."])
    section("Uji abu-abu: periksa value tanpa warna")
    P("Cara cepat memeriksa apakah sebuah desain punya kontras value yang cukup: lihat versi hitam-putihnya. Bila elemen "
      "penting menyatu dengan latarnya saat tanpa warna, desain itu akan sulit dibaca, terutama bagi penderita buta warna.")
    drawing(grayscale_test(), fig("Dua palet dengan rona sama, tetapi value berbeda"))
    box("tip", f"Di Colorize: buka panel Color Blindness, pilih <b>Achromatopsia</b>, lalu tekan {K('Ctrl+Y')} (Proof Colors). "
        "Seluruh kanvas tampil tanpa warna. Tekan lagi untuk kembali.")

    # 18 ---------------------------------------------------------------
    g.chapter("Komposisi: Menata Warna dalam Desain")
    P("Memilih warna yang bagus baru separuh pekerjaan. Separuh lainnya adalah menentukan <b>di mana</b> dan <b>seberapa "
      "banyak</b> setiap warna dipakai.", "lead")
    section("Aturan 60-30-10")
    P("Aturan sederhana dari dunia desain interior ini juga berlaku untuk desain grafis dan tampilan digital:")
    drawing(proportion_603010(), fig("Pembagian 60-30-10 dan contohnya di sebuah halaman"))
    bullets(["<b>60% warna dominan</b>: biasanya netral, untuk latar dan ruang kosong.",
             "<b>30% warna pendukung</b>: memberi karakter, misalnya header, bidang, dan judul.",
             "<b>10% warna aksen</b>: untuk hal yang harus dilihat atau diklik, seperti tombol utama dan harga promo."])
    box("note", "Angka ini panduan, bukan hukum. Intinya: ada satu warna yang jelas memimpin, satu yang menemani, dan satu "
        "yang muncul sedikit sebagai kejutan. Palet berisi lima warna dengan porsi sama hampir selalu terasa ramai.")
    section("Warna mengarahkan mata")
    P("Mata manusia otomatis tertarik pada bagian yang paling berbeda dari sekitarnya. Gunakan ini untuk menyusun "
      "<b>hierarki visual</b>: urutan apa yang dilihat pertama, kedua, dan seterusnya.")
    drawing(hierarchy(), fig("Banyak warna jenuh membuat semua sama penting; satu aksen membuat pilihan jelas"))
    bullets(["Simpan warna paling jenuh untuk satu hal yang paling penting di setiap layar atau halaman.",
             "Elemen sekunder memakai versi lebih kusam, lebih terang, atau netral.",
             "Konsisten: bila biru berarti \"bisa diklik\", jangan pakai biru untuk hiasan."])
    section("Berapa banyak warna?")
    table([
        ["Jumlah", "Kesan", "Cocok untuk"],
        ["1 warna + netral", "Bersih, tegas, mudah dikenali", "Merek modern, desain minimalis, laporan"],
        ["2 warna + netral", "Seimbang, punya karakter", "Sebagian besar merek dan website"],
        ["3 warna + netral", "Kaya, perlu pengaturan porsi", "Merek ritel, acara, produk anak"],
        ["4 warna atau lebih", "Meriah, mudah berantakan", "Festival, mainan, grafik data dengan banyak kategori"],
    ], [0.24, 0.36, 0.4])
    section("Langkah membuat palet dari nol")
    steps(["<b>Tentukan suasana.</b> Tulis tiga kata sifat, misalnya: hangat, tradisional, terpercaya.",
           "<b>Pilih satu warna utama</b> yang mewakili suasana itu. Kumpulkan referensi: foto, karya lain, bahan produk.",
           "<b>Tambah pendamping</b> dengan aturan harmoni (Bab 7): analogous untuk tenang, complementary untuk tegas.",
           "<b>Siapkan netral</b>: satu terang untuk latar, satu gelap untuk teks. Beri sedikit rona warna utama.",
           "<b>Atur value</b>: pastikan ada warna terang, sedang, dan gelap. Lakukan uji abu-abu.",
           "<b>Uji di konteks nyata</b>: mockup, materi cetak, foto produk.",
           "<b>Periksa aksesibilitas dan cetak</b>: kontras teks, buta warna, dan hasil CMYK.",
           "<b>Dokumentasikan</b>: nama warna, kode HEX, RGB, CMYK, dan aturan pemakaiannya."])
    box("tip", "Mulai dalam hitam-putih. Banyak desainer menyusun tata letak dalam abu-abu lebih dulu, lalu menambahkan warna. "
        "Dengan cara ini hierarki sudah benar sebelum warna masuk.")

    # 19 ---------------------------------------------------------------
    g.chapter("Psikologi dan Makna Warna")
    P("Warna memengaruhi perasaan dan membawa makna. Namun makna ini <b>bukan rumus pasti</b>: ia dibentuk oleh budaya, "
      "pengalaman pribadi, dan konteks. Merah bisa berarti cinta, bahaya, atau diskon, tergantung di mana ia muncul.", "lead")
    section("Asosiasi umum")
    meanings = [
        ("Merah", ok(0.58, 0.2, 27), "Energi, berani, cinta, semangat, nafsu makan", "Bahaya, marah, larangan",
         "Makanan cepat saji, promo, olahraga"),
        ("Oranye", ok(0.72, 0.17, 55), "Ramah, ceria, terjangkau, kreatif", "Murahan bila berlebihan",
         "Produk anak, e-commerce, komunitas"),
        ("Kuning", ok(0.88, 0.16, 95), "Optimis, hangat, perhatian, muda", "Peringatan, cemas", "Promo, rambu, sarapan"),
        ("Hijau", ok(0.6, 0.14, 150), "Alam, sehat, tumbuh, aman, uang", "Iri, tidak matang", "Pertanian, kesehatan, keuangan"),
        ("Biru", ok(0.5, 0.15, 255), "Percaya, tenang, profesional, teknologi", "Dingin, berjarak",
         "Bank, asuransi, teknologi, rumah sakit"),
        ("Ungu", ok(0.48, 0.15, 305), "Mewah, kreatif, spiritual, misterius", "Berlebihan, tidak nyata",
         "Kecantikan, produk premium, seni"),
        ("Merah muda", ok(0.78, 0.11, 350), "Lembut, manis, romantis, peduli", "Kekanakan", "Kecantikan, kue, produk bayi"),
        ("Cokelat", ok(0.45, 0.07, 55), "Hangat, alami, kokoh, tradisional", "Kusam, kotor", "Kopi, kayu, kerajinan"),
        ("Hitam", "#111111", "Elegan, kuat, formal, mewah", "Duka, berat", "Mode, otomotif, produk premium"),
        ("Putih", "#F7F7F7", "Bersih, suci, sederhana, lega", "Kosong, steril", "Kesehatan, teknologi, pernikahan"),
        ("Abu-abu", "#8A8A8A", "Netral, seimbang, serius", "Membosankan", "Teknologi, korporat, latar"),
    ]
    rows = [["", "Warna", "Kesan positif", "Kesan negatif", "Sering dipakai"]]
    for name, h, pos, neg, use in meanings:
        rows.append([chip(h, 26, 16), f"<b>{name}</b>", pos, neg, use])
    table(rows, [0.07, 0.13, 0.3, 0.2, 0.3])
    section("Konteks budaya di Indonesia dan sekitarnya")
    bullets(["<b>Merah dan putih</b> sangat lekat dengan kebangsaan. Kombinasi ini kuat untuk tema Agustusan dan nasionalisme, "
             "tetapi perlu hati-hati agar merek tidak terkesan seperti materi resmi.",
             "<b>Hijau</b> sering dikaitkan dengan nuansa Islami dan religius, selain alam dan kesehatan. Banyak dipakai untuk "
             "materi Ramadan dan Idulfitri, sering dipadukan dengan emas.",
             "<b>Kuning</b>: di sebagian daerah, misalnya Jakarta dan sekitarnya, bendera kuning menandakan ada yang meninggal "
             "dunia. Di sisi lain, kuning keemasan berarti kemuliaan dan sering muncul di budaya Melayu dan Jawa.",
             "<b>Merah dan emas</b> berarti keberuntungan dan kemakmuran dalam budaya Tionghoa, sangat umum saat Imlek.",
             "<b>Putih</b> berarti suci dan dipakai di banyak acara keagamaan, tetapi juga warna duka dalam tradisi Tionghoa.",
             "<b>Hitam</b> identik dengan duka di banyak budaya, tetapi juga elegan dan formal di dunia mode."])
    box("warn", "Untuk materi yang ditujukan ke daerah atau komunitas tertentu, tanyakan langsung ke orang setempat. Satu "
        "obrolan singkat bisa mencegah salah makna yang memalukan.")
    section("Warna menurut industri")
    P("Setiap industri punya \"warna kebiasaan\". Mengikutinya membuat merek cepat dipahami; melawannya membuat merek mudah "
      "diingat, tetapi berisiko terlihat tidak cocok. Keduanya sah, asalkan disengaja.")
    table([
        ["Industri", "Warna yang umum", "Alasan"],
        ["Keuangan dan asuransi", "Biru tua, hijau, emas", "Percaya, stabil, uang"],
        ["Kesehatan", "Biru muda, hijau, putih", "Bersih, tenang, sembuh"],
        ["Makanan dan minuman", "Merah, oranye, kuning, cokelat", "Nafsu makan, hangat, ramah"],
        ["Teknologi", "Biru, ungu, hitam, gradien cerah", "Modern, cerdas, inovatif"],
        ["Pendidikan anak", "Warna primer cerah", "Ceria, mudah dikenali"],
        ["Kecantikan dan mode", "Hitam, merah muda, nude, emas", "Elegan, lembut, mewah"],
        ["Lingkungan dan pertanian", "Hijau, cokelat, krem", "Alam, tanah, organik"],
    ], [0.3, 0.34, 0.36])

    # 20 ---------------------------------------------------------------
    g.chapter("Warna untuk Identitas Merek")
    P("Warna adalah salah satu hal pertama yang diingat orang dari sebuah merek. Agar mudah dikenali, warna merek harus "
      "<b>konsisten</b> di semua tempat: logo, kemasan, website, media sosial, seragam, dan papan nama.", "lead")
    section("Bagian-bagian sistem warna merek")
    table([
        ["Bagian", "Isi", "Contoh"],
        ["Warna utama (primary)", "1 warna yang paling mewakili merek", "Merah pada merek minuman, biru pada bank"],
        ["Warna pendukung (secondary)", "1-2 warna pendamping", "Krem, hijau tua"],
        ["Aksen", "Warna kecil untuk sorotan", "Kuning emas untuk label promo"],
        ["Netral", "Latar, teks, garis", "Putih tulang, abu-abu hangat, hitam kecokelatan"],
        ["Warna semantik", "Arti tetap: berhasil, peringatan, galat, info", "Hijau, kuning, merah, biru"],
        ["Skala", "Versi terang dan gelap tiap warna (50-950)", "Untuk latar lembut, hover, teks berwarna"],
    ], [0.26, 0.38, 0.36])
    section("Lembar spesifikasi warna")
    P("Setiap warna merek perlu dicatat dalam beberapa format, karena tiap media butuh kode yang berbeda. Contoh berikut "
      "dihitung dengan Colorize" + (" memakai profil SWOP bawaan Windows." if prf else " (CMYK perkiraan tanpa profil)."))
    kopi = [("Kopi", "#4B2E1F"), ("Karamel", "#C8763B"), ("Susu", "#F3E6D3"), ("Daun", "#1F3B36"), ("Madu", "#E9B949")]
    drawing(brand_cards(kopi, prf), fig("Contoh lembar warna merek \"Kopi Senja\""))
    table([
        ["Format", "Dipakai untuk", "Catatan"],
        ["HEX", "Website, aplikasi, Canva, Figma", "Paling umum untuk layar"],
        ["RGB", "Video, presentasi, software lama", "Sama dengan HEX, hanya cara tulis berbeda"],
        ["CMYK", "Brosur, kemasan, kartu nama", "Tergantung mesin cetak dan kertas, tanyakan profilnya ke percetakan"],
        ["Pantone (spot)", "Logo di kemasan, kaus, papan nama", "Tinta khusus, paling konsisten antar-percetakan"],
        ["OKLCH", "Sistem desain modern, CSS", "Mudah dibuat versi terang-gelapnya"],
    ], [0.18, 0.4, 0.42])
    section("Warna semantik")
    P("Warna semantik memberi arti tetap pada pesan. Pengguna sudah terbiasa: hijau berarti berhasil, kuning berarti hati-hati, "
      "merah berarti ada masalah, biru berarti informasi. Jangan dibalik.")
    drawing(semantic(), fig("Pesan semantik: latar lembut, garis tegas, teks gelap dengan rona yang sama"))
    box("tip", "Bila warna utama merek Anda merah, pilih merah galat yang sedikit berbeda (lebih gelap atau bergeser rona) agar "
        "pesan galat tidak tertukar dengan elemen merek. Jangan pernah mengandalkan warna saja: sertakan ikon dan teks.")
    section("Menjaga konsistensi")
    bullets(["Simpan palet resmi di <b>Library</b> Colorize dan beri tag, misalnya <i>merek</i>.",
             "Bagikan file <b>.ase</b> ke desainer lain (Photoshop, Illustrator, InDesign) dan <b>CSS Variables</b> atau "
             "<b>Design Tokens</b> ke tim website.",
             "Buat <b>brand guideline</b> berisi kode semua format, contoh pemakaian yang benar dan salah, serta proporsinya.",
             "Untuk cetak penting seperti kemasan, minta <b>proof cetak</b> dan simpan sebagai acuan."])

    # 21 ---------------------------------------------------------------
    g.chapter("Warna untuk Layar: Web, Aplikasi, dan Media Sosial")
    P("Layar memancarkan cahaya sendiri, dipakai di berbagai kondisi (terik matahari sampai kamar gelap), dan berinteraksi "
      "dengan pengguna. Karena itu warna di layar punya aturan tambahan.", "lead")
    section("Warna untuk setiap keadaan (state)")
    P("Elemen interaktif seperti tombol butuh beberapa versi warna agar pengguna tahu apa yang terjadi:")
    drawing(ui_states(), fig("Satu tombol dalam lima keadaan, beserta kontras teksnya"))
    bullets(["<b>Hover</b> (kursor di atasnya): sedikit lebih gelap atau terang, sekitar 5-8% lightness.",
             "<b>Ditekan</b>: lebih gelap lagi.",
             "<b>Nonaktif</b>: kusam dan pucat, tanpa kesan bisa diklik. Tidak wajib lulus kontras, tetapi tetap harus bisa dibaca.",
             "<b>Fokus</b>: garis tepi yang jelas untuk pengguna keyboard, dengan kontras minimal 3:1 terhadap sekitarnya."])
    box("tip", "Di Colorize, buka color picker dan ubah <b>L</b> saja (misalnya dari 55 ke 49) untuk membuat versi hover yang "
        "ronanya tetap sama. Panel Scale juga bisa dipakai: 600 untuk hover, 700 untuk ditekan.")
    section("Mode gelap (dark mode)")
    drawing(dark_mode(), fig("Mode gelap yang nyaman memakai abu-abu tua dan warna yang dilunakkan"))
    bullets(["Jangan pakai hitam pekat #000000 untuk latar besar. Abu-abu sangat tua (misalnya sekitar #121212) lebih nyaman dan "
             "memberi ruang untuk bayangan.",
             "Permukaan yang \"lebih dekat\" ke pengguna dibuat sedikit lebih terang, menggantikan bayangan di mode terang.",
             "Warna jenuh tampak menyala dan bergetar di latar gelap. Naikkan lightness-nya dan turunkan chroma-nya.",
             "Teks putih murni di atas hitam bisa menyilaukan. Putih yang sedikit diredam lebih nyaman untuk bacaan panjang.",
             "Periksa ulang kontras: pasangan yang lulus di mode terang belum tentu lulus di mode gelap."])
    box("tip", "Di jendela Mockup Colorize, centang <b>Dark</b> untuk melihat palet Anda dalam mode gelap beserta pemeriksaan "
        "kontrasnya.")
    section("Media sosial")
    bullets(["Foto dan konten di media sosial dikompres dan dilihat di layar HP dengan kecerahan berbeda-beda. Hindari detail "
             "warna yang terlalu halus.",
             "Feed yang tampak rapi biasanya memakai palet terbatas: 2-3 warna merek dan filter foto yang konsisten.",
             "Ekspor gambar untuk media sosial dalam ruang warna <b>sRGB</b>. Gambar dengan profil lain bisa berubah warna saat diunggah.",
             "Teks di atas gambar harus tetap terbaca di layar kecil (lihat Bab 22)."])
    section("Ruang warna lebar di layar modern")
    P("HP dan laptop baru banyak yang mendukung <b>Display P3</b>, ruang warna yang lebih lebar dari sRGB (lihat Bab 25). "
      "Warna di luar sRGB bisa tampil lebih menyala di layar tersebut, tetapi akan dipotong di layar biasa. Untuk sebagian "
      "besar pekerjaan, tetap rancang di sRGB agar hasilnya sama di semua layar.")

    # 22 ---------------------------------------------------------------
    g.chapter("Teks, Foto, dan Warna")
    P("Teks adalah elemen paling penting di kebanyakan desain. Warna yang salah bisa membuat pesan terbaik pun tidak terbaca.", "lead")
    section("Ukuran dan ketebalan memengaruhi kontras")
    drawing(text_sizes(), fig("Warna yang sama: cukup untuk judul besar, kurang untuk teks kecil"))
    P("Itu sebabnya standar WCAG punya dua batas: 3:1 untuk teks besar dan 4.5:1 untuk teks biasa (Bab 10). Huruf tipis "
      "(light, thin) juga butuh kontras lebih tinggi daripada huruf tebal pada ukuran yang sama.")
    bullets(["Teks isi: gunakan warna sangat gelap di latar terang, misalnya abu-abu kehitaman bernuansa merek.",
             "Teks keterangan atau abu-abu sekunder: tetap minimal 4.5:1.",
             "Hindari teks berwarna jenuh untuk paragraf panjang; simpan untuk judul atau tautan."])
    section("Teks di atas foto")
    p1, p2 = text_on_photo()
    figures([(p1, fig("Teks putih langsung di atas langit terang: sulit dibaca")),
             (p2, fig("Lapisan gelap transparan (scrim) di belakang teks: jelas terbaca"))], 0.47)
    P("Foto punya bagian terang dan gelap sekaligus, sehingga tidak ada satu warna teks yang aman di semua bagian. Beberapa "
      "cara mengatasinya:")
    bullets(["<b>Scrim</b>: gradien gelap atau terang transparan di belakang teks, seperti contoh di atas.",
             "<b>Kotak latar</b>: teks diletakkan di kotak berwarna solid atau semi-transparan.",
             "<b>Pilih area tenang</b>: letakkan teks di bagian foto yang polos, seperti langit atau dinding.",
             "<b>Bayangan halus</b> di belakang huruf, untuk judul besar.",
             "<b>Kaburkan atau gelapkan</b> seluruh foto bila foto hanya berfungsi sebagai suasana."])
    box("tip", "Di Colorize, buka foto (Ctrl+Shift+O), lalu pakai Eyedropper dengan ukuran sampel 5×5 di area tempat teks akan "
        f"diletakkan. Jadikan warna itu warna belakang ({K('X')} untuk menukar), lalu periksa kontrasnya di panel Contrast.")
    section("Warna yang bergetar")
    drawing(vibrating(), fig("Merah dan biru jenuh dengan terang yang mirip tampak bergetar"))
    P("Dua warna jenuh dengan terang yang hampir sama, terutama merah dan biru atau merah dan hijau, membuat tepi huruf "
      "tampak bergetar dan melelahkan mata. Perbaiki dengan membuat salah satunya jauh lebih terang atau lebih gelap, atau "
      "menurunkan kejenuhan salah satunya.")
    section("Tautan dan teks interaktif")
    bullets(["Tautan di dalam paragraf sebaiknya diberi garis bawah, bukan hanya warna, karena penderita buta warna mungkin "
             "tidak melihat perbedaannya.",
             "Bila hanya memakai warna, tautan perlu kontras minimal 3:1 terhadap teks di sekitarnya, dan tetap 4.5:1 terhadap latar.",
             "Gunakan satu warna tautan di seluruh desain."])

    # 23 ---------------------------------------------------------------
    g.chapter("Warna dalam Infografis dan Grafik")
    P("Di grafik, warna bukan hiasan: warna membawa data. Pemilihan yang salah bisa membuat pembaca salah paham.", "lead")
    section("Tiga jenis palet data")
    drawing(dataviz_palettes(), fig("Kategorikal, sekuensial, dan divergen"))
    table([
        ["Jenis", "Untuk data", "Contoh"],
        ["Kategorikal", "Kelompok yang tidak berurutan", "Pangsa pasar per merek, jenis produk, provinsi"],
        ["Sekuensial", "Angka dari kecil ke besar", "Kepadatan penduduk, suhu, jumlah penjualan"],
        ["Divergen", "Angka dengan titik tengah yang bermakna", "Untung-rugi, di atas-di bawah rata-rata, setuju-tidak setuju"],
    ], [0.2, 0.38, 0.42])
    bullets(["Palet <b>kategorikal</b>: maksimal sekitar 6-8 warna. Lebih dari itu, gabungkan kategori kecil menjadi \"Lainnya\".",
             "Palet <b>sekuensial</b>: ubah terang secara bertahap. Nilai besar = lebih gelap (di latar terang).",
             "Palet <b>divergen</b>: dua rona berbeda di kedua ujung, netral terang di tengah."])
    section("Sorot pesan utamanya")
    drawing(highlight_charts(), fig("Grafik pelangi vs grafik dengan satu sorotan"))
    P("Bila grafik punya satu pesan (misalnya \"bulan April penjualan tertinggi\"), warnai hanya bagian itu dan biarkan sisanya "
      "abu-abu. Pembaca langsung menangkap pesannya tanpa perlu membaca legenda.")
    section("Palet yang ramah buta warna")
    drawing(cvd_compare(), fig("Palet pelangi biasa dan palet Okabe-Ito, dilihat penderita deuteranopia"))
    P("Palet <b>Okabe-Ito</b> (2008) dirancang khusus agar tetap bisa dibedakan oleh penderita buta warna, dan banyak dipakai di "
      "jurnal ilmiah. Kodenya: " + ", ".join(OKABE_ITO) + ".")
    bullets(["Hindari pasangan merah-hijau sebagai satu-satunya pembeda, misalnya untuk naik-turun atau untung-rugi.",
             "Tambahkan pembeda lain: label langsung, pola garis, bentuk penanda, atau posisi.",
             "Hindari palet pelangi untuk data berurutan. Terangnya tidak urut, sehingga menimbulkan batas palsu."])
    box("tip", "Di Colorize: masukkan palet grafik ke dokumen, lalu buka panel <b>Color Blindness</b>. Bila muncul tulisan "
        "<i>pairs hard to tell apart</i>, arahkan kursor ke sana untuk melihat pasangan yang bermasalah dan ganti salah satunya.")

    # 24 ---------------------------------------------------------------
    g.chapter("Warna untuk Cetak: Dari Layar ke Kertas")
    P("Bab 11 sudah membahas dasar CMYK dan panel Print. Bab ini membahas hal yang perlu diketahui desainer sebelum mengirim "
      "file ke percetakan.", "lead")
    section("Bagaimana mesin cetak membuat warna")
    P("Mesin cetak offset dan sebagian besar printer digital mencetak empat lapis tinta: cyan, magenta, kuning, dan hitam. "
      "Setiap lapis dicetak dari satu <b>pelat</b> (plate) yang hanya berisi satu warna tinta.")
    full, plates = separations()
    figures([(full, fig("Gambar asli"))], 0.45)
    figures([(plates[0], "Pelat cyan"), (plates[1], "Pelat magenta"), (plates[2], "Pelat kuning"), (plates[3], "Pelat hitam (K)")], 0.23)
    P("Tinta tidak dicetak dengan ketebalan berbeda. Untuk membuat warna lebih muda, mesin cetak memakai <b>titik-titik halftone</b> "
      "yang lebih kecil. Dari jarak baca, mata mencampur titik-titik ini menjadi warna yang halus.")
    drawing(halftone(), fig("Persentase tinta dibuat dari ukuran titik, bukan ketebalan tinta"))
    section("Warna proses dan warna spot")
    table([
        ["", "Warna proses (CMYK)", "Warna spot (Pantone)"],
        ["Cara kerja", "Campuran titik 4 tinta", "Tinta khusus yang sudah dicampur sebelumnya"],
        ["Kelebihan", "Murah untuk gambar berwarna penuh", "Sangat konsisten, bisa warna yang tidak bisa dicapai CMYK"],
        ["Kekurangan", "Warna bisa bergeser antar-percetakan", "Biaya tambahan per warna tinta"],
        ["Cocok untuk", "Foto, brosur, majalah", "Logo, kemasan, warna merek penting, tinta metalik dan neon"],
    ], [0.18, 0.4, 0.42])
    section("Hitam di dunia cetak")
    d = blacks()
    if d is not None:
        drawing(d, fig("Tiga resep hitam, ditampilkan lewat profil SWOP"))
    bullets(["<b>100 K saja</b>: hitam standar untuk teks. Tampak sedikit keabu-abuan pada area luas.",
             "<b>Rich black</b> (misalnya C60 M40 Y40 K100): hitam pekat untuk latar atau bidang luas. Jangan dipakai untuk teks "
             "kecil, karena keempat pelat jarang menempel dengan presisi sempurna (disebut <i>registrasi</i>), sehingga tepi "
             "huruf tampak berbayang.",
             "<b>Hitam 400%</b> (semua tinta 100%): terlalu banyak tinta, lama kering, dan bisa menempel ke lembar berikutnya."])
    section("Batas total tinta")
    P("<b>Total tinta</b> (Total Area Coverage, TAC) adalah jumlah persentase C+M+Y+K di satu titik. Setiap jenis kertas punya "
      "batas. Perkiraan umum: sekitar 300% untuk kertas coated (art paper), 260-280% untuk uncoated (HVS), dan sekitar 240% "
      "untuk kertas koran. Selalu tanyakan angka pasti ke percetakan. Profil ICC dari percetakan biasanya sudah mengatur batas ini.")
    section("Jenis kertas mengubah warna")
    table([
        ["Kertas", "Contoh", "Pengaruh pada warna"],
        ["Coated (berlapis)", "Art paper, art carton, ivory", "Tinta tetap di permukaan: warna cerah dan tajam"],
        ["Uncoated (tanpa lapisan)", "HVS, kertas daur ulang, kraft", "Tinta meresap: warna lebih kusam dan gelap, detail melebar"],
        ["Berwarna", "Kraft cokelat, kertas warna", "Tinta CMYK transparan, sehingga ikut terwarnai kertasnya"],
    ], [0.24, 0.32, 0.44])
    box("note", "Warna yang sama dicetak di art paper dan di HVS akan tampak berbeda. Itu sebabnya buku warna Pantone dijual "
        "dalam versi coated (C) dan uncoated (U).")
    section("Menyiapkan file cetak")
    drawing(bleed(), fig("Bleed, garis potong, dan area aman"))
    table([
        ["Periksa", "Standar umum"],
        ["Mode warna", "CMYK dengan profil dari percetakan (atau minta mereka yang mengonversi)"],
        ["Resolusi gambar", "300 ppi pada ukuran cetak sebenarnya"],
        ["Bleed", "3 mm di setiap sisi untuk desain yang warnanya sampai ke tepi"],
        ["Area aman", "Teks dan logo minimal 3-5 mm di dalam garis potong"],
        ["Teks hitam kecil", "100 K saja, bukan rich black, bukan hitam RGB"],
        ["Huruf", "Disertakan (embedded) atau diubah menjadi outline"],
        ["Format", "PDF/X-1a atau PDF/X-4 bila percetakan menerimanya"],
        ["Proof", "Minta contoh cetak untuk pekerjaan penting sebelum cetak massal"],
    ], [0.26, 0.74])
    box("tip", "Alur di Colorize: muat profil dari percetakan di panel <b>Print</b>, periksa warna bertanda segitiga, lalu klik "
        "<b>Use Print Colors</b> untuk palet versi cetak. Ekspor sebagai <b>.ase</b> agar bisa dipakai di Illustrator atau InDesign.")

    # 25 ---------------------------------------------------------------
    g.chapter("Manajemen Warna")
    P("Kenapa desain yang sama tampak berbeda di laptop Anda, di HP klien, dan di hasil cetak? Karena setiap perangkat "
      "menghasilkan warna dengan caranya sendiri. <b>Manajemen warna</b> adalah upaya agar warna tetap sama di mana pun.", "lead")
    section("Ruang warna")
    P("Ruang warna (color space) adalah batas warna yang bisa dihasilkan suatu sistem. Diagram di bawah menampilkan semua "
      "warna yang bisa dilihat mata manusia. Segitiga di dalamnya menunjukkan jangkauan ruang warna yang umum.")
    figure(chromaticity(), fig("Diagram kromatisitas CIE 1931 dengan tiga ruang warna RGB"), 0.72)
    table([
        ["Ruang warna", "Jangkauan", "Dipakai untuk"],
        ["sRGB", "Standar, paling sempit", "Web, media sosial, sebagian besar monitor. Pilihan paling aman."],
        ["Display P3", "Sekitar 25% lebih luas dari sRGB", "iPhone, Mac, HP dan laptop kelas atas, video HDR"],
        ["Adobe RGB", "Lebih luas di hijau dan cyan", "Fotografi dan pekerjaan cetak kelas atas"],
        ["CMYK", "Bergantung mesin dan kertas, sering lebih sempit dari sRGB", "Cetak"],
    ], [0.18, 0.34, 0.48])
    section("Profil ICC")
    P("<b>Profil ICC</b> adalah file yang menjelaskan cara satu perangkat menghasilkan warna. Dengan profil, program bisa "
      "menerjemahkan warna dari satu perangkat ke perangkat lain. Ada profil untuk monitor, kamera, printer, dan kondisi cetak.")
    bullets(["<b>Sematkan (embed) profil</b> saat menyimpan gambar, agar program lain tahu cara membacanya.",
             "<b>Konversi ke sRGB</b> sebelum mengunggah ke web atau media sosial.",
             "Colorize membaca profil di gambar saat mengekstrak warna (Bab 9), sehingga foto Display P3 tidak melenceng."])
    section("Kalibrasi monitor")
    P("Monitor yang tidak dikalibrasi bisa terlalu biru, terlalu terang, atau terlalu jenuh. Akibatnya Anda mengoreksi warna "
      "yang sebenarnya sudah benar.")
    table([
        ["Pengaturan", "Nilai umum", "Keterangan"],
        ["Titik putih", "D65 (6500 K)", "Putih seperti cahaya siang hari"],
        ["Gamma", "2.2 (atau sRGB)", "Kurva terang-gelap standar"],
        ["Kecerahan", "80-120 cd/m²", "Untuk pekerjaan cetak; layar yang terlalu terang membuat hasil cetak tampak gelap"],
    ], [0.22, 0.26, 0.52])
    bullets(["Cara terbaik: pakai alat kalibrasi (colorimeter) beserta software-nya.",
             "Tanpa alat: pakai mode <b>sRGB</b> di menu monitor bila ada, matikan mode \"vivid\" atau \"dinamis\", dan atur "
             "kecerahan agar putih di layar mirip kertas putih di samping monitor.",
             "Ulangi kalibrasi setiap beberapa bulan, karena monitor berubah seiring umur."])
    section("Soft proofing")
    P("<b>Soft proofing</b> adalah melihat perkiraan hasil akhir di layar sebelum mencetak. Panel Print di Colorize "
      "melakukannya untuk palet: kotak kanan menunjukkan perkiraan warna setelah dicetak. Program seperti Photoshop dan "
      "InDesign punya fitur serupa untuk seluruh desain.")
    section("Alur kerja yang disarankan")
    table([
        ["Tujuan akhir", "Rancang di", "Kirim sebagai"],
        ["Web dan media sosial", "sRGB", "PNG, JPG, WebP, atau SVG dalam sRGB"],
        ["Cetak", "RGB lebar atau CMYK dengan profil percetakan", "PDF/X dengan CMYK, dicek lewat soft proof"],
        ["Keduanya", "RGB, lalu buat versi CMYK terpisah", "Satu file per media; jangan memakai satu file untuk semuanya"],
    ], [0.24, 0.38, 0.38])

    # 26 ---------------------------------------------------------------
    g.chapter("File, Mode Warna, dan Kesalahan yang Sering Terjadi")
    section("Mode warna di software desain")
    table([
        ["Mode", "Isi", "Kapan dipakai"],
        ["RGB", "Merah, hijau, biru", "Semua desain untuk layar; foto sebelum dikonversi untuk cetak"],
        ["CMYK", "Empat tinta cetak", "Desain siap cetak sesuai profil percetakan"],
        ["Grayscale", "Abu-abu saja", "Cetak hitam-putih, koran"],
        ["Indexed", "Maksimal 256 warna", "GIF, ikon kecil, pixel art"],
        ["Lab", "Terang + dua sumbu warna, tidak bergantung perangkat", "Koreksi warna lanjutan, perantara konversi"],
    ], [0.16, 0.4, 0.44])
    section("Kedalaman bit dan banding")
    P("<b>Kedalaman bit</b> menentukan berapa banyak tingkat warna yang bisa disimpan. Gambar 8-bit punya 256 tingkat per "
      "kanal; 16-bit punya 65.536 tingkat. Gradien gelap yang halus bisa tampak berundak (disebut <b>banding</b>) bila "
      "tingkatnya kurang atau setelah dikompres berkali-kali.")
    figure(banding(), fig("Atas: gradien halus. Bawah: simulasi banding."), 0.9)
    bullets(["Edit foto dan gradien penting dalam 16-bit, lalu simpan hasil akhir dalam 8-bit.",
             "Tambahkan sedikit noise (bintik halus) pada gradien besar agar banding tidak terlihat.",
             "Di CSS, gradien yang dicampur dalam OKLab biasanya tampak lebih halus (lihat Bab 8)."])
    section("Format file")
    table([
        ["Format", "Warna", "Cocok untuk"],
        ["JPG", "RGB atau CMYK, 8-bit, terkompres (kualitas turun)", "Foto di web dan media sosial"],
        ["PNG", "RGB, bisa transparan, tanpa kehilangan kualitas", "Logo, ilustrasi, tangkapan layar"],
        ["WebP / AVIF", "RGB, ukuran kecil", "Website modern"],
        ["SVG", "Vektor, warna ditulis sebagai kode", "Logo dan ikon di web, bisa diperbesar tanpa pecah"],
        ["PDF", "RGB atau CMYK, vektor dan gambar", "Dokumen, file siap cetak (PDF/X)"],
        ["TIFF", "RGB atau CMYK, 8/16-bit, tanpa kompresi rusak", "Arsip foto, cetak kualitas tinggi"],
        ["AI, PSD, INDD", "File kerja Adobe", "Disimpan sebagai sumber, bukan dikirim sebagai hasil akhir"],
    ], [0.18, 0.44, 0.38])
    section("Kesalahan umum dan cara menghindarinya")
    drawing(vibrating(), fig("Contoh kesalahan: warna bergetar"))
    table([
        ["Kesalahan", "Akibatnya", "Lebih baik"],
        ["Terlalu banyak warna jenuh", "Ramai, tidak ada fokus", "Satu aksen jenuh, sisanya netral atau kusam"],
        ["Teks abu-abu muda di atas putih", "Sulit dibaca, terutama di HP", "Minimal 4.5:1, cek di panel Contrast"],
        ["Mengandalkan merah-hijau", "Tidak terlihat bagi penderita buta warna", "Tambah ikon, label, atau beda terang"],
        ["Hitam #000 dan putih #FFF di mode gelap", "Menyilaukan dan melelahkan", "Abu-abu tua dan putih yang diredam"],
        ["Mengirim file RGB untuk cetak tanpa dicek", "Biru dan hijau cerah menjadi kusam", "Soft proof di panel Print"],
        ["Rich black untuk teks kecil", "Huruf berbayang", "Teks kecil 100 K"],
        ["Menilai warna di layar terlalu terang", "Hasil cetak tampak gelap", "Kalibrasi monitor, kecerahan sedang"],
        ["Warna merek berbeda di setiap materi", "Merek sulit dikenali", "Simpan di Library, bagikan .ase dan CSS"],
        ["Memilih warna dari satu kotak kecil", "Terlihat lain saat dipakai", "Uji di mockup dan konteks nyata"],
        ["Mengikuti tren tanpa alasan", "Cepat terasa ketinggalan", "Mulai dari karakter merek, tren sebagai bumbu"],
    ], [0.3, 0.32, 0.38])

    write_recipes(prf)


# ----------------------------------------------------------------- Part III


def contrast_rows(pairs):
    rows = [["Pasangan", "Rasio", "Hasil"]]
    for label, fg, bg in pairs:
        r = contrast_ratio(fg, bg)
        verdict = "lulus AAA" if r >= 7 else ("lulus AA" if r >= 4.5 else ("teks besar saja" if r >= 3 else "tidak lulus"))
        rows.append([f"{label} ({fg} di atas {bg})", format_ratio(r), verdict])
    return rows


def write_recipes(prf) -> None:
    P, section, bullets, steps, box, table = g.P, g.section, g.bullets, g.steps, g.box, g.table
    drawing, figure, figures, K, M = g.drawing, g.figure, g.figures, g.K, g.M

    g.part("BAGIAN III", "Resep Proyek",
           "Empat contoh pekerjaan nyata, dari awal sampai file siap dikirim. Ikuti langkahnya di Colorize untuk "
           "mempraktikkan semua yang sudah dipelajari.")

    # 27 ---------------------------------------------------------------
    g.chapter("Resep 1: Warna Merek untuk Usaha Kopi")
    P("Sebuah kedai kopi kecil ingin identitas yang <b>hangat, akrab, dan lokal</b>. Hasil akhirnya: palet merek, skala warna "
      "untuk website, dan file untuk percetakan.", "lead")
    base = "#6F4E37"
    L, C, H = to_oklch(base)
    comp = harmony("complementary", L, C, H)
    acc_h = comp.colors[1 - comp.base_index][2] if len(comp.colors) > 1 else (H + 180) % 360
    palette = [("Kopi", base), ("Krim", ok(0.95, 0.025, H)), ("Espresso", ok(0.26, 0.03, H)),
               ("Daun", ok(0.42, 0.06, acc_h)), ("Gula aren", ok(0.72, 0.13, 70))]
    section("1. Warna utama")
    steps([f"Buat palet baru ({K('Ctrl+N')}) dan beri nama <i>Kopi Senja</i> lewat {M('Palette › Rename Palette…')}.",
           f"Ketik <b>{base}</b> (cokelat kopi) di kotak Hex panel Color, lalu klik <b>Add to Swatches</b>.",
           "Lihat nilai OKLCH-nya: " + f"L {L * 100:.0f}%, C {C:.3f}, H {H:.0f}. Ini cokelat sedang dengan kejenuhan rendah: "
           "hangat dan tidak mencolok."])
    section("2. Netral bernuansa merek")
    steps([f"Buka color picker. Isi H = {H:.0f} (rona kopi), C = 0,025, L = 95. Hasilnya krim hangat untuk latar. Tambahkan ke palet.",
           "Ulangi dengan L = 26 dan C = 0,03 untuk warna teks <i>espresso</i>. Teks hitam murni akan terasa terlalu keras."])
    section("3. Warna pendamping dari harmoni")
    steps([f"Tekan {K('W')} untuk membuka Harmony, pilih <b>Complementary</b>, lalu klik tombol bulat untuk memakai warna kopi.",
           f"Lawan cokelat adalah rona hijau kebiruan (sekitar H {acc_h:.0f}). Klik kotak itu, lalu turunkan L ke 42 dan C ke 0,06 "
           "di color picker agar menjadi hijau daun yang kalem.",
           "Tambahkan satu aksen hangat: gula aren (L 72, C 0,13, H 70) untuk label promo dan tombol."])
    drawing(brand_cards(palette, prf), fig("Palet akhir \"Kopi Senja\""))
    section("4. Periksa kontras")
    table(contrast_rows([("Teks espresso di latar krim", palette[2][1], palette[1][1]),
                         ("Teks krim di latar kopi", palette[1][1], base),
                         ("Teks espresso di tombol gula aren", palette[2][1], palette[4][1]),
                         ("Teks putih di tombol gula aren", "#FFFFFF", palette[4][1])]), [0.6, 0.15, 0.25])
    P("Hasilnya menunjukkan bahwa tombol gula aren harus memakai teks gelap, bukan putih. Hal seperti ini mudah terlewat "
      "tanpa pemeriksaan.")
    section("5. Skala untuk website")
    sc = tint_shade_scale(base)
    drawing(palette_strip([s.hex for s in sc], [str(s.step) for s in sc], size=38), fig("Skala warna kopi 50 sampai 950"))
    steps(["Buka panel <b>Scale</b>, klik tombol bulat untuk memakai warna kopi, lalu klik <b>New Palette</b>.",
           "Ekspor palet skala dengan format <b>Tailwind CSS v4</b>, prefix <i>kopi</i>, dan <b>Names: Scale (50 – 950)</b>."])
    section("6. Uji di mockup")
    steps([f"Kembali ke palet <i>Kopi Senja</i>, lalu {M('Palette › Preview Mockup')} ({K('Ctrl+Shift+M')}).",
           "Klik <b>Shuffle</b> beberapa kali. Pilih susunan yang terasa paling \"kopi\", atau atur sendiri lewat tombol peran.",
           "Pastikan baris pemeriksaan kontras di bawah mockup tidak ada yang merah. Ekspor PNG untuk presentasi ke pemilik usaha."])
    section("7. Siapkan untuk cetak")
    if prf:
        matches = prf.match([h for _, h in palette])
        rows = [["Warna", "CMYK (SWOP)", "ΔE", "Status"]]
        for (name, _), m in zip(palette, matches):
            status = {"match": "aman", "slight": "sedikit bergeser", "noticeable": "bergeser jelas"}[m.shift]
            rows.append([name, " / ".join(f"{v:.0f}" for v in m.cmyk), f"{m.delta_e:.1f}", status])
        table(rows, [0.25, 0.35, 0.15, 0.25])
    steps(["Buka panel <b>Print</b>. Warna-warna kalem seperti ini umumnya aman dicetak.",
           "Untuk logo di gelas dan kemasan, cari padanan Pantone di panel <b>Match</b> (bila Anda punya bukunya dalam .ase).",
           "Simpan ke Library dengan tag <i>merek, kopi</i>, lalu ekspor <b>.ase</b> untuk desainer kemasan."])

    # 28 ---------------------------------------------------------------
    g.chapter("Resep 2: Palet Feed Instagram dari Foto Produk")
    P("Sebuah toko daring ingin feed Instagram yang terasa satu kesatuan. Warnanya diambil dari foto produk andalan.", "lead")
    figure("image-extract", fig("Mengambil warna dari foto"), 1.0)
    steps([f"Buka foto produk terbaik lewat {M('File › Open Image…')} ({K('Ctrl+Shift+O')}).",
           "Atur <b>Colors</b> ke 6. Geser penanda bila ada warna penting yang terlewat, misalnya warna kemasan.",
           "Klik <b>Sort › Lightness</b> agar urutannya dari terang ke gelap, lalu <b>New Palette</b>.",
           "Hapus warna yang terlalu mirip. Sisakan 1 terang (latar), 1 gelap (teks), dan 2-3 warna karakter.",
           "Uji abu-abu: buka panel Color Blindness, pilih Achromatopsia, tekan Ctrl+Y. Pastikan latar dan teks berbeda jelas.",
           "Periksa kontras teks untuk caption di atas latar warna di panel Contrast.",
           "Ekspor dengan format <b>Color List</b> dan HEX, lalu salin ke Brand Kit di aplikasi desain yang Anda pakai (misalnya Canva)."])
    box("tip", "Agar feed konsisten: pakai latar yang sama untuk semua konten teks, batasi warna aksen ke satu per unggahan, dan "
        "gunakan filter foto yang sama. Simpan palet ke Library dengan tag <i>sosmed</i>.")
    section("Aturan sederhana untuk konten")
    table([
        ["Jenis konten", "Latar", "Teks", "Aksen"],
        ["Foto produk", "Foto asli", "Tanpa teks atau teks kecil di scrim", "Stiker harga warna aksen"],
        ["Kutipan / info", "Warna terang dari palet", "Warna gelap dari palet", "Garis atau ikon kecil"],
        ["Promo", "Warna karakter", "Putih atau terang (cek kontras)", "Warna aksen untuk angka diskon"],
    ], [0.22, 0.24, 0.3, 0.24])

    # 29 ---------------------------------------------------------------
    g.chapter("Resep 3: Undangan dan Brosur Cetak")
    P("Undangan pernikahan dengan nuansa <b>hijau sage dan emas</b>, dicetak di kertas art carton. Tantangannya: warna lembut "
      "di layar sering tampak kusam atau bergeser saat dicetak.", "lead")
    inv = [ok(0.97, 0.012, 95), ok(0.72, 0.05, 140), ok(0.5, 0.05, 150), ok(0.74, 0.11, 85), ok(0.3, 0.03, 150)]
    drawing(palette_strip(inv, ["Kertas", "Sage", "Sage tua", "Emas", "Teks"], size=60), fig("Palet undangan"))
    steps(["Susun palet di Colorize. Pilih warna dengan chroma rendah sampai sedang; warna lembut seperti ini mudah dicetak.",
           "Minta profil ICC dari percetakan. Muat lewat <b>Load Profile…</b> di panel Print.",
           "Periksa tanda di panel Print. Warna bertanda segitiga perlu diganti dengan <b>Use Print Colors</b> atau disesuaikan manual.",
           "Emas di layar hanyalah kuning kecokelatan. Untuk kilau emas sungguhan, diskusikan dengan percetakan: tinta emas metalik "
           "(warna spot) atau hot print/foil.",
           "Teks kecil memakai warna gelap yang cukup kontras dengan kertas (cek di panel Contrast, minimal 4.5:1).",
           "Ekspor <b>.ase</b> dan gunakan di Illustrator atau InDesign. Siapkan bleed 3 mm dan area aman.",
           "Minta proof cetak di kertas yang sama sebelum mencetak ratusan lembar."])
    if prf:
        rows = [["Warna", "Layar", "Perkiraan cetak", "ΔE"]]
        for name, m in zip(["Kertas", "Sage", "Sage tua", "Emas", "Teks"], prf.match(inv)):
            rows.append([name, chip(m.hex), chip(m.print_hex), f"{m.delta_e:.1f}"])
        table(rows, [0.3, 0.25, 0.25, 0.2])
    box("note", "Warna kertas ikut menentukan hasil. Kertas krem atau ivory membuat semua warna sedikit lebih hangat. Di layar, "
        "warna pertama palet (Kertas) mewakili warna kertas sebagai latar saat menilai.")

    # 30 ---------------------------------------------------------------
    g.chapter("Resep 4: Dashboard dan Infografis Ramah Buta Warna")
    P("Laporan penjualan bulanan untuk rapat direksi, ditampilkan di proyektor dan dibagikan sebagai PDF. Semua orang harus "
      "bisa membacanya, termasuk peserta yang buta warna.", "lead")
    steps(["Buat palet baru berisi warna Okabe-Ito: " + ", ".join(OKABE_ITO[:7]) + ". Ketik satu per satu di kotak Hex lalu "
           "tambahkan, atau impor dari file .gpl.",
           "Buka panel <b>Color Blindness</b>. Coba Protan, Deutan, dan Tritan, lalu pastikan tidak ada peringatan "
           "<i>pairs hard to tell apart</i> untuk warna yang benar-benar dipakai.",
           f"Buka mockup ({K('Ctrl+Shift+M')}) dan pilih template <b>Dashboard</b>. Tekan {K('Ctrl+Y')} untuk melihat seluruh "
           "dashboard dengan simulasi buta warna.",
           "Untuk angka naik-turun, jangan hanya merah dan hijau. Pakai biru dan oranye, ditambah panah atau tanda + dan -.",
           "Pakai abu-abu untuk data pembanding dan satu warna untuk data utama (Bab 23).",
           "Periksa kontras teks label dan angka di panel Contrast. Proyektor menurunkan kontras, jadi targetkan AAA (7:1) "
           "untuk teks penting."])
    figure("mockup-dashboard", fig("Template Dashboard di jendela Mockup"), 0.85)
    box("tip", "Simpan palet ini ke Library dengan tag <i>grafik</i>. Untuk laporan berikutnya cukup klik dua kali palet di "
        "Library, tanpa menyusun ulang.")


# ------------------------------------------------------------------ appendix

NAMED = [
    ("Merah cabai", ok(0.55, 0.21, 27)), ("Merah marun", ok(0.36, 0.12, 15)), ("Merah bata", ok(0.52, 0.13, 35)),
    ("Salem", ok(0.76, 0.11, 35)), ("Merah muda", ok(0.82, 0.09, 355)), ("Fuchsia", ok(0.6, 0.24, 345)),
    ("Oranye", ok(0.72, 0.18, 55)), ("Kuning kunyit", ok(0.78, 0.16, 80)), ("Kuning gading", ok(0.95, 0.04, 95)),
    ("Krem", ok(0.92, 0.04, 85)), ("Cokelat susu", ok(0.62, 0.07, 60)), ("Cokelat tua", ok(0.38, 0.06, 50)),
    ("Hijau daun", ok(0.6, 0.15, 140)), ("Hijau botol", ok(0.4, 0.08, 155)), ("Hijau sage", ok(0.72, 0.05, 140)),
    ("Hijau toska", ok(0.7, 0.12, 185)), ("Hijau army", ok(0.48, 0.06, 120)), ("Biru langit", ok(0.8, 0.08, 230)),
    ("Biru benhur", ok(0.55, 0.17, 255)), ("Biru dongker", ok(0.3, 0.09, 265)), ("Ungu lavender", ok(0.78, 0.07, 300)),
    ("Ungu terong", ok(0.38, 0.12, 320)), ("Abu-abu", ok(0.65, 0, 0)), ("Hitam arang", ok(0.25, 0.005, 260)),
]


def write_appendix(module) -> None:
    P, section, bullets, table = g.P, g.section, g.bullets, g.table

    g.chapter("Daftar Periksa dan Angka Penting")
    section("Sebelum desain untuk layar diserahkan")
    bullets(["Teks isi minimal 4.5:1, teks besar minimal 3:1, ikon dan garis kotak isian minimal 3:1.",
             "Palet diuji dengan simulasi protan, deutan, dan tritan. Informasi tidak hanya dibedakan dengan warna.",
             "Tombol punya warna untuk hover, ditekan, nonaktif, dan fokus.",
             "Mode gelap (bila ada) diperiksa ulang kontrasnya.",
             "Gambar diekspor dalam sRGB.",
             "Kode warna dibagikan sebagai CSS Variables, Tailwind, atau Design Tokens."], "body")
    section("Sebelum file dikirim ke percetakan")
    bullets(["Mode CMYK dengan profil dari percetakan, atau sudah disepakati siapa yang mengonversi.",
             "Warna diperiksa di panel Print; warna yang bergeser jelas sudah diganti atau disetujui.",
             "Gambar 300 ppi, bleed 3 mm, teks di area aman.",
             "Teks hitam kecil memakai 100 K. Total tinta tidak melebihi batas kertas.",
             "Warna spot (Pantone) diberi nama yang sama persis dengan buku warnanya.",
             "Huruf disertakan atau diubah menjadi outline, file disimpan sebagai PDF/X.",
             "Proof cetak disetujui untuk pekerjaan penting."], "body")
    section("Angka-angka penting")
    table([
        ["Hal", "Angka", "Bab"],
        ["Kontras teks biasa (AA / AAA)", "4.5:1 / 7:1", "10"],
        ["Kontras teks besar dan elemen UI", "3:1", "10"],
        ["ΔE: hampir sama / sedikit beda / beda jelas", "di bawah 2 / 2-5 / di atas 5", "11"],
        ["Proporsi warna", "60-30-10", "18"],
        ["Jumlah warna kategori di grafik", "maksimal sekitar 6-8", "23"],
        ["Resolusi gambar cetak", "300 ppi", "24"],
        ["Bleed / area aman", "3 mm / 3-5 mm", "24"],
        ["Rich black", "C60 M40 Y40 K100", "24"],
        ["Total tinta coated / uncoated / koran", "sekitar 300% / 260-280% / 240%", "24"],
        ["Kalibrasi monitor", "D65, gamma 2.2, 80-120 cd/m²", "25"],
        ["Hover / ditekan", "lightness turun sekitar 5-8% / 10-15%", "21"],
    ], [0.5, 0.36, 0.14])

    g.chapter("Tabel Nama Warna Sehari-hari")
    P("Nama warna sehari-hari tidak punya standar resmi, sehingga \"biru dongker\" bisa berbeda di benak setiap orang. Tabel ini "
      "memberi contoh kode untuk memudahkan komunikasi dengan klien. Saat bekerja, selalu sepakati kode HEX atau Pantone-nya.", "lead")
    rows = [["", "Nama", "HEX", "", "Nama", "HEX"]]
    half = (len(NAMED) + 1) // 2
    for i in range(half):
        row = []
        for name, h in (NAMED[i], NAMED[i + half] if i + half < len(NAMED) else ("", None)):
            row += [chip(h, 30, 16), name, h] if h else ["", "", ""]
        rows.append(row)
    table(rows, [0.08, 0.24, 0.16, 0.08, 0.26, 0.18])

    g.chapter("Bacaan Lanjutan")
    P("Untuk Anda yang ingin mendalami warna lebih jauh:", "lead")
    table([
        ["Judul", "Isi"],
        ["Josef Albers, <i>Interaction of Color</i> (1963)", "Latihan klasik tentang bagaimana warna saling memengaruhi."],
        ["Johannes Itten, <i>The Art of Color</i> (1961)", "Roda warna 12 dan tujuh kontras warna."],
        ["W3C, <i>Web Content Accessibility Guidelines (WCAG) 2.2</i>", "Standar resmi aksesibilitas web, termasuk kontras."],
        ["Masataka Okabe dan Kei Ito, <i>Color Universal Design</i> (2008)", "Palet yang ramah buta warna."],
        ["Björn Ottosson, <i>A perceptual color space for image processing</i> (2020)", "Penjelasan OKLab, dasar OKLCH yang dipakai Colorize."],
        ["Pantone dan RAL", "Situs resmi masing-masing untuk buku warna dan panduan cetak."],
    ], [0.5, 0.5])


GLOSSARY = [
    ("Adobe RGB", "Ruang warna RGB yang lebih luas dari sRGB, terutama di hijau dan cyan. Dipakai di fotografi dan cetak."),
    ("Aditif", "Pencampuran warna dengan cahaya. Semakin banyak dicampur, semakin terang."),
    ("Aksen", "Warna yang dipakai sedikit untuk menarik perhatian, misalnya pada tombol utama."),
    ("Banding", "Gradien yang tampak berundak, bukan halus, karena tingkat warnanya kurang."),
    ("Bleed", "Bagian desain yang dilebihkan sekitar 3 mm di luar garis potong, agar tidak ada tepi putih setelah dipotong."),
    ("Coated", "Kertas berlapis seperti art paper. Warna tercetak lebih cerah dan tajam."),
    ("Dark mode", "Tampilan dengan latar gelap dan teks terang."),
    ("Display P3", "Ruang warna sekitar 25% lebih luas dari sRGB, dipakai di banyak HP dan laptop modern."),
    ("Halftone", "Titik-titik kecil berukuran berbeda yang dipakai mesin cetak untuk membuat warna lebih muda."),
    ("Hierarki visual", "Urutan elemen yang dilihat pembaca, dari yang paling penting."),
    ("Kalibrasi", "Menyetel monitor atau printer agar menampilkan warna sesuai standar."),
    ("Kedalaman bit", "Jumlah tingkat warna per kanal: 8-bit punya 256 tingkat, 16-bit punya 65.536."),
    ("Kontras simultan", "Warna tampak berubah karena pengaruh warna di sekitarnya."),
    ("Metamerisme", "Dua warna tampak sama di bawah satu jenis cahaya tetapi berbeda di bawah cahaya lain."),
    ("Netral", "Warna tanpa atau dengan sangat sedikit rona: putih, abu-abu, hitam, krem."),
    ("Okabe-Ito", "Palet delapan warna yang tetap bisa dibedakan oleh penderita buta warna."),
    ("PDF/X", "Jenis PDF khusus untuk cetak, dengan aturan warna dan huruf yang ketat."),
    ("Ppi", "Pixels per inch: kerapatan piksel gambar. Untuk cetak umumnya 300 ppi."),
    ("Registrasi", "Ketepatan posisi antar-pelat tinta saat dicetak. Bila meleset, tepi tampak berbayang."),
    ("Rich black", "Hitam cetak yang dicampur tinta lain (misalnya C60 M40 Y40 K100) agar lebih pekat."),
    ("Ruang warna", "Batas warna yang bisa dihasilkan sebuah sistem, seperti sRGB atau CMYK."),
    ("Saturasi", "Kejenuhan warna: seberapa jauh warna dari abu-abu. Mirip chroma."),
    ("Scrim", "Lapisan gelap atau terang transparan di belakang teks agar teks terbaca di atas foto."),
    ("Soft proofing", "Melihat perkiraan hasil cetak di layar sebelum mencetak."),
    ("Spot color", "Tinta khusus yang sudah dicampur, seperti Pantone. Lawan dari warna proses CMYK."),
    ("Subtraktif", "Pencampuran warna dengan tinta atau cat. Semakin banyak dicampur, semakin gelap."),
    ("TAC", "Total Area Coverage: jumlah persentase semua tinta di satu titik."),
    ("Tone", "Versi warna yang dicampur abu-abu, sehingga lebih kalem."),
    ("Uncoated", "Kertas tanpa lapisan seperti HVS. Warna tercetak lebih kusam."),
    ("Value", "Tingkat terang-gelap sebuah warna."),
    ("Warna hangat / dingin", "Kelompok warna yang terasa hangat (merah, oranye, kuning) atau sejuk (hijau, biru, ungu)."),
    ("Warna primer / sekunder / tersier", "Warna dasar, campuran dua warna dasar, dan campuran primer dengan sekunder."),
    ("Warna proses", "Warna cetak yang dibuat dari campuran titik CMYK."),
    ("Warna semantik", "Warna dengan arti tetap: hijau berhasil, kuning peringatan, merah galat, biru info."),
    ("White point", "Titik putih: warna yang dianggap putih oleh sebuah sistem. Standar umum D65."),
]

FAQ = [
    ("Berapa jumlah warna ideal untuk sebuah merek?",
     "Umumnya satu warna utama, satu atau dua pendukung, satu aksen, ditambah warna netral. Lebih sedikit lebih mudah dijaga "
     "konsistensinya."),
    ("Apakah saya harus membeli buku Pantone?",
     "Tidak wajib. Pantone berguna bila warna merek harus sama persis di kemasan, kaus, atau papan nama dari percetakan berbeda. "
     "Untuk brosur biasa, CMYK dengan proof cetak sudah cukup."),
    ("Kenapa warna logo saya berbeda di Instagram?",
     "Biasanya karena gambar disimpan dengan profil warna selain sRGB, atau dikompres ulang. Ekspor ulang dalam sRGB dari "
     "software desain Anda."),
    ("Klien ingin warna \"yang lebih ngejreng\". Apa yang harus diubah?",
     "Naikkan chroma (kejenuhan), bukan lightness. Di Colorize, geser titik di bidang color picker ke kanan. Perhatikan tanda "
     "di luar gamut dan periksa ulang kontras serta hasil cetaknya."),
]
