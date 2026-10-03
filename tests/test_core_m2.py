import io

import numpy as np
import pytest
from coloraide import Color
from PIL import Image

from colorize.core.color import hex_to_rgb
from colorize.core.extract import average_color, extract_palette
from colorize.core.image import ImageLoadError, load_image, pixel_block, sample_pixels
from colorize.core.oklab import srgb8_to_oklab
from tests.icc_util import matrix_profile

BLOCKS = ("#E63946", "#F1FAEE", "#457B9D", "#1D3557")


def block_image(colors=BLOCKS, weights=(4, 3, 2, 1), size=(100, 40)) -> np.ndarray:
    """Vertical stripes, widths proportional to ``weights``."""
    w, h = size
    edges = np.cumsum([0] + [round(w * x / sum(weights)) for x in weights])
    edges[-1] = w
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    for color, x0, x1 in zip(colors, edges, edges[1:]):
        rgb[:, x0:x1] = hex_to_rgb(color)
    return rgb


def png_bytes(image: Image.Image, **params) -> io.BytesIO:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", **params)
    buffer.seek(0)
    return buffer


# ------------------------------------------------------------- extraction


def test_flat_colors_come_back_exactly_most_common_first():
    pixels = block_image().reshape(-1, 3)
    result = extract_palette(pixels, 4)
    assert [c.hex for c in result] == list(BLOCKS)
    assert [round(c.share, 2) for c in result] == [0.4, 0.3, 0.2, 0.1]


def test_count_is_capped_at_distinct_colors():
    result = extract_palette(block_image().reshape(-1, 3), 12)
    assert len(result) == 4


def test_same_image_same_palette():
    rng = np.random.default_rng(3)
    photo = rng.integers(0, 256, size=(120, 160, 3), dtype=np.uint8)
    first = extract_palette(photo.reshape(-1, 3), 6)
    for _ in range(3):
        assert extract_palette(photo.reshape(-1, 3), 6) == first
    assert extract_palette(photo.reshape(-1, 3), 6, seed=1) != first  # the seed really drives it


def test_clusters_are_separated_in_oklab():
    rng = np.random.default_rng(5)
    pixels = rng.integers(0, 256, size=(20000, 3), dtype=np.uint8)
    result = extract_palette(pixels, 8)
    assert len(result) == 8
    assert sum(c.share for c in result) == pytest.approx(1.0)
    lab = srgb8_to_oklab(np.array([hex_to_rgb(c.hex) for c in result], dtype=np.uint8))
    distances = np.sqrt(((lab[:, None] - lab[None]) ** 2).sum(-1))
    assert distances[np.triu_indices(8, 1)].min() > 0.05


def test_marker_points_at_a_pixel_of_its_cluster():
    pixels = block_image().reshape(-1, 3)
    for color in extract_palette(pixels, 4):
        assert "#{:02X}{:02X}{:02X}".format(*pixels[color.sample_index]) == color.hex


def test_empty_input():
    assert extract_palette(np.zeros((0, 3), dtype=np.uint8), 5) == []


def test_average_is_in_linear_light():
    black_white = np.array([[0, 0, 0], [255, 255, 255]], dtype=np.uint8)
    assert average_color(black_white) == "#BCBCBC"  # not #808080: 50% light is sRGB 188
    assert average_color(np.array([[10, 20, 30]] * 9, dtype=np.uint8)) == "#0A141E"


def test_pixel_block_clips_at_edges():
    rgb = block_image()
    assert pixel_block(rgb, 0, 0, 5).shape == (9, 3)
    assert pixel_block(rgb, 50, 20, 3).shape == (9, 3)
    assert pixel_block(rgb, 50, 20, 1).shape == (1, 3)


# ----------------------------------------------------------- image loading


def test_plain_png_is_read_as_srgb():
    loaded = load_image(png_bytes(Image.fromarray(block_image())))
    assert loaded.profile is None and loaded.alpha is None
    assert np.array_equal(loaded.rgb, block_image())


def test_display_p3_photo_is_converted_to_srgb():
    p3_values = (150, 110, 80)  # warm skin-like tone, inside sRGB after conversion
    image = Image.new("RGB", (8, 8), p3_values)
    loaded = load_image(png_bytes(image, icc_profile=matrix_profile("display-p3", "Display P3")))
    assert loaded.profile == "Display P3" and loaded.profile_applied

    expected = Color("display-p3", [v / 255 for v in p3_values]).convert("srgb")
    expected = [round(c * 255) for c in expected.coords()]
    got = loaded.rgb[0, 0].tolist()
    assert got == pytest.approx(expected, abs=1)
    assert got != list(p3_values)  # proves the profile changed the numbers


def test_transparent_pixels_are_ignored():
    rgba = np.zeros((20, 20, 4), dtype=np.uint8)
    rgba[..., :3] = (255, 0, 0)
    rgba[:, :10, 3] = 255  # left half opaque red
    rgba[:, 10:, :3] = (0, 0, 255)  # right half blue but fully transparent
    loaded = load_image(png_bytes(Image.fromarray(rgba, "RGBA")))
    pixels, positions = sample_pixels(loaded)
    assert len(pixels) == 200
    assert {tuple(p) for p in pixels} == {(255, 0, 0)}
    assert positions[:, 0].max() < 0.5


def test_large_images_are_sampled_down_to_200px():
    loaded = load_image(png_bytes(Image.fromarray(np.zeros((900, 1600, 3), dtype=np.uint8))))
    pixels, positions = sample_pixels(loaded)
    assert len(pixels) == 200 * 112
    assert positions.min() > 0 and positions.max() < 1


def test_exif_rotation_is_applied():
    image = Image.fromarray(np.zeros((10, 30, 3), dtype=np.uint8))
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90° clockwise on display
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    buffer.seek(0)
    assert load_image(buffer).rgb.shape[:2] == (30, 10)


def test_not_an_image():
    with pytest.raises(ImageLoadError):
        load_image(io.BytesIO(b"definitely not an image"))
