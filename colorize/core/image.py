"""Image loading for extraction: embedded ICC profile -> sRGB, alpha kept separately.

Without the conversion, a Display P3 photo (every recent iPhone) would be read as if
its numbers were sRGB and every extracted color would be off.
"""

import io
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageCms, ImageOps

SAMPLE_MAX_SIDE = 200  # plan: shrink to ~200 px before clustering
OPAQUE_THRESHOLD = 128  # pixels with alpha below this are ignored
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp", ".gif")

_SRGB = ImageCms.createProfile("sRGB")


class ImageLoadError(ValueError):
    pass


@dataclass(frozen=True)
class LoadedImage:
    rgb: np.ndarray  # (H, W, 3) uint8, sRGB
    alpha: np.ndarray | None  # (H, W) uint8, or None when fully opaque
    profile: str | None  # embedded profile description, None if there was none
    profile_applied: bool  # False if a profile was present but could not be used

    @property
    def width(self) -> int:
        return self.rgb.shape[1]

    @property
    def height(self) -> int:
        return self.rgb.shape[0]


def _to_srgb(base: Image.Image, icc: bytes | None) -> tuple[Image.Image, str | None, bool]:
    if not icc:
        return base.convert("RGB"), None, True
    try:
        source = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        name = ImageCms.getProfileDescription(source).strip() or "Embedded profile"
        converted = ImageCms.profileToProfile(
            base, source, _SRGB, renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC, outputMode="RGB"
        )
        return converted, name, True
    except (ImageCms.PyCMSError, OSError, ValueError):
        return base.convert("RGB"), "Unreadable profile", False


def load_image(source) -> LoadedImage:
    """``source``: a path or a binary file object."""
    try:
        with Image.open(source) as opened:
            opened.load()
            info = dict(opened.info)
            image = ImageOps.exif_transpose(opened)
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ImageLoadError(str(exc)) from exc

    icc = info.get("icc_profile")
    has_alpha = image.mode in ("RGBA", "LA", "PA") or (image.mode == "P" and "transparency" in info)
    if image.mode not in ("RGB", "RGBA", "L", "LA", "CMYK"):
        image = image.convert("RGBA" if has_alpha else "RGB")
    alpha = None
    if has_alpha:
        alpha = np.asarray(image.getchannel("A"), dtype=np.uint8).copy()
        image = image.convert(image.mode[:-1])  # RGBA -> RGB, LA -> L (keeps the profile's color space)
        if alpha.min() == 255:
            alpha = None
    converted, profile, applied = _to_srgb(image, icc)
    rgb = np.asarray(converted, dtype=np.uint8).copy()
    return LoadedImage(rgb, alpha, profile, applied)


def sample_pixels(image: LoadedImage, max_side: int = SAMPLE_MAX_SIDE) -> tuple[np.ndarray, np.ndarray]:
    """Downscale for clustering. Returns (opaque pixels (N, 3) uint8,
    their positions (N, 2) as fractions of image width/height)."""
    scale = min(1.0, max_side / max(image.width, image.height))
    w, h = max(1, round(image.width * scale)), max(1, round(image.height * scale))
    rgb = image.rgb
    alpha = image.alpha
    if (w, h) != (image.width, image.height):
        rgb = np.asarray(Image.fromarray(image.rgb).resize((w, h), Image.Resampling.BOX))
        if alpha is not None:
            alpha = np.asarray(Image.fromarray(alpha).resize((w, h), Image.Resampling.BOX))
    ys, xs = np.mgrid[0:h, 0:w]
    positions = np.stack([(xs + 0.5) / w, (ys + 0.5) / h], axis=-1).reshape(-1, 2)
    pixels = rgb.reshape(-1, 3)
    if alpha is not None:
        keep = alpha.reshape(-1) >= OPAQUE_THRESHOLD
        pixels, positions = pixels[keep], positions[keep]
    return pixels, positions


def pixel_block(rgb: np.ndarray, x: int, y: int, size: int) -> np.ndarray:
    """``size`` x ``size`` block centered on (x, y), clipped to the image (eyedropper)."""
    half = size // 2
    h, w = rgb.shape[:2]
    return rgb[max(0, y - half) : min(h, y + half + 1), max(0, x - half) : min(w, x + half + 1)].reshape(-1, 3)
