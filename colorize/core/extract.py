"""Palette extraction: weighted k-means++ in OKLab, deterministic for a given seed.

Clustering runs on the image's unique colors weighted by pixel count, which is both
faster and exact for flat-color images (k never exceeds the number of distinct colors).
"""

from dataclasses import dataclass

import numpy as np
from coloraide import Color

from colorize.core.gamut import map_to_srgb
from colorize.core.oklab import decode_srgb8, encode_srgb, srgb8_to_oklab

DEFAULT_SEED = 0
MAX_ITERATIONS = 30
# Stop once no center moves more than this in OKLab: ~200x below a visible difference (JND ~0.02).
CONVERGED = 1e-4


@dataclass(frozen=True)
class ExtractedColor:
    hex: str
    share: float  # fraction of sampled pixels in this cluster (0-1)
    sample_index: int  # a sampled pixel of the color nearest the cluster center, for on-image markers


def _sq_distances(points: np.ndarray, point_norms: np.ndarray, centers: np.ndarray) -> np.ndarray:
    """(N, K) squared distances via |p|^2 - 2 p.c + |c|^2 (one BLAS matmul)."""
    d = point_norms[:, None] - 2 * (points @ centers.T) + (centers * centers).sum(axis=1)[None, :]
    return np.maximum(d, 0)


def kmeans(points: np.ndarray, weights: np.ndarray, k: int, seed: int = DEFAULT_SEED):
    """Weighted Lloyd's k-means with k-means++ seeding. Returns (centers, labels)."""
    rng = np.random.default_rng(seed)
    n = len(points)
    k = min(k, n)
    centers = np.empty((k, points.shape[1]))
    centers[0] = points[rng.choice(n, p=weights / weights.sum())]
    d2 = ((points - centers[0]) ** 2).sum(axis=1)
    for i in range(1, k):
        mass = weights * d2
        centers[i] = points[rng.choice(n, p=mass / mass.sum())]
        d2 = np.minimum(d2, ((points - centers[i]) ** 2).sum(axis=1))

    # Distances in float32 (only used to pick the nearest center); means stay float64
    # so a flat color cluster reproduces its exact hex.
    points32 = points.astype(np.float32)
    norms = (points32 * points32).sum(axis=1)
    labels = np.zeros(n, dtype=np.int64)
    for _ in range(MAX_ITERATIONS):
        distances = _sq_distances(points32, norms, centers.astype(np.float32))
        labels = distances.argmin(axis=1)
        totals = np.bincount(labels, weights=weights, minlength=k)
        new = np.stack([np.bincount(labels, weights=weights * points[:, d], minlength=k) for d in range(3)], axis=1)
        empty = totals == 0
        new[~empty] /= totals[~empty, None]
        if empty.any():  # re-seed empty clusters at the worst-fitting points
            worst = np.argsort(-distances[np.arange(n), labels] * weights)
            new[empty] = points[worst[: empty.sum()]]
        shift = np.abs(new - centers).max()
        centers = new
        if shift < CONVERGED:
            break
    labels = _sq_distances(points32, norms, centers.astype(np.float32)).argmin(axis=1)
    return centers, labels


def _oklab_to_hex(lab) -> str:
    lightness, chroma, hue = Color("oklab", list(lab)).convert("oklch").coords(nans=False)
    return map_to_srgb(lightness, chroma, hue).hex


def extract_palette(pixels: np.ndarray, count: int, seed: int = DEFAULT_SEED) -> list[ExtractedColor]:
    """Dominant colors of ``pixels`` ((N, 3) uint8 sRGB), most common first."""
    pixels = np.asarray(pixels, dtype=np.uint8).reshape(-1, 3)
    if len(pixels) == 0 or count < 1:
        return []
    unique, inverse, counts = np.unique(pixels, axis=0, return_inverse=True, return_counts=True)
    inverse = inverse.reshape(-1)
    weights = counts.astype(np.float64)
    lab = srgb8_to_oklab(unique)
    centers, labels = kmeans(lab, weights, count, seed)

    results = []
    total = weights.sum()
    for cluster in range(len(centers)):
        members = np.flatnonzero(labels == cluster)
        if len(members) == 0:
            continue
        nearest = members[((lab[members] - centers[cluster]) ** 2).sum(axis=1).argmin()]
        # Middle occurrence (in scan order) of that color: lands inside a region more
        # often than the first one, which tends to sit on the image's top/left edge.
        occurrences = np.flatnonzero(inverse == nearest)
        results.append(
            ExtractedColor(
                hex=_oklab_to_hex(centers[cluster]),
                share=float(weights[members].sum() / total),
                sample_index=int(occurrences[len(occurrences) // 2]),
            )
        )
    results.sort(key=lambda c: (-c.share, c.hex))
    return results


def average_color(pixels: np.ndarray) -> str:
    """Mean of sRGB pixels in linear light (what an N x N eyedropper sample should be)."""
    linear = decode_srgb8(np.asarray(pixels, dtype=np.uint8).reshape(-1, 3)).mean(axis=0)
    r, g, b = np.round(encode_srgb(linear) * 255).astype(int)
    return f"#{r:02X}{g:02X}{b:02X}"
