# SPDX-License-Identifier: MIT
"""Image-space operations used by UV Pixel Sync.

This module has no Blender dependency so the pixel-preservation behavior can
be tested independently from Blender UI state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np


@dataclass(frozen=True)
class PixelSelection:
    mask: np.ndarray
    left: int
    bottom: int

    @property
    def width(self) -> int:
        return int(self.mask.shape[1])

    @property
    def height(self) -> int:
        return int(self.mask.shape[0])

    @property
    def right(self) -> int:
        return self.left + self.width - 1

    @property
    def top(self) -> int:
        return self.bottom + self.height - 1


def _fill_polygon(mask: np.ndarray, points: np.ndarray, left: int, bottom: int) -> None:
    """Fill a polygon by intersecting each pixel-center scanline."""
    if len(points) < 3:
        return

    local = points - np.array((left, bottom), dtype=np.float64)
    first_row = max(0, int(np.ceil(np.min(local[:, 1]) - 0.5)))
    last_row = min(mask.shape[0] - 1, int(np.floor(np.max(local[:, 1]) - 0.5)))

    for row in range(first_row, last_row + 1):
        y = row + 0.5
        hits: list[float] = []
        for index, start in enumerate(local):
            end = local[(index + 1) % len(local)]
            y1, y2 = start[1], end[1]
            if y1 == y2:
                continue
            if (y1 <= y < y2) or (y2 <= y < y1):
                ratio = (y - y1) / (y2 - y1)
                hits.append(float(start[0] + ratio * (end[0] - start[0])))

        hits.sort()
        for index in range(0, len(hits) - 1, 2):
            first_col = max(0, int(np.ceil(hits[index] - 0.5)))
            last_col = min(mask.shape[1] - 1, int(np.floor(hits[index + 1] - 0.5)))
            if first_col <= last_col:
                mask[row, first_col : last_col + 1] = True


def _expand_mask(mask: np.ndarray, amount: int) -> np.ndarray:
    expanded = np.asarray(mask, dtype=bool).copy()
    for _ in range(max(0, int(amount))):
        source = expanded
        result = source.copy()
        result[1:, :] |= source[:-1, :]
        result[:-1, :] |= source[1:, :]
        result[:, 1:] |= source[:, :-1]
        result[:, :-1] |= source[:, 1:]
        result[1:, 1:] |= source[:-1, :-1]
        result[1:, :-1] |= source[:-1, 1:]
        result[:-1, 1:] |= source[1:, :-1]
        result[:-1, :-1] |= source[1:, 1:]
        expanded = result
    return expanded


def rasterize_uv_selection(
    polygons: Iterable[Sequence[Sequence[float]]],
    image_width: int,
    image_height: int,
    padding: int = 0,
) -> PixelSelection:
    """Convert 0-1 UV polygons to a compact pixel-center mask."""
    width = int(image_width)
    height = int(image_height)
    if width <= 0 or height <= 0:
        raise ValueError("Image dimensions must be positive")

    valid = [np.asarray(polygon, dtype=np.float64) for polygon in polygons]
    valid = [polygon for polygon in valid if polygon.ndim == 2 and polygon.shape[0] >= 3 and polygon.shape[1] == 2]
    if not valid:
        raise ValueError("No valid UV polygons")

    all_uvs = np.concatenate(valid, axis=0)
    tolerance = 1e-7
    if float(np.min(all_uvs)) < -tolerance or float(np.max(all_uvs)) > 1.0 + tolerance:
        raise ValueError("Selected UVs must stay inside the 0-1 image tile")

    scale = np.array((width, height), dtype=np.float64)
    pixel_polygons = [np.clip(polygon, 0.0, 1.0) * scale for polygon in valid]
    all_points = np.concatenate(pixel_polygons, axis=0)
    pad = max(0, int(padding))

    left = max(0, int(np.floor(np.min(all_points[:, 0]))) - pad)
    bottom = max(0, int(np.floor(np.min(all_points[:, 1]))) - pad)
    right_exclusive = min(width, int(np.ceil(np.max(all_points[:, 0]))) + pad)
    top_exclusive = min(height, int(np.ceil(np.max(all_points[:, 1]))) + pad)
    if right_exclusive <= left or top_exclusive <= bottom:
        raise ValueError("The selected UV area contains no pixels")

    mask = np.zeros((top_exclusive - bottom, right_exclusive - left), dtype=bool)
    for polygon in pixel_polygons:
        _fill_polygon(mask, polygon, left, bottom)
    if not np.any(mask):
        raise ValueError("The selected UV area is smaller than one pixel")

    if pad:
        mask = _expand_mask(mask, pad)
    return PixelSelection(mask=mask, left=left, bottom=bottom)


def clamp_translation(
    selection: PixelSelection,
    dx: int,
    dy: int,
    image_width: int,
    image_height: int,
) -> tuple[int, int, bool]:
    """Keep a translated pixel selection fully inside the image."""
    min_dx = -selection.left
    max_dx = int(image_width) - 1 - selection.right
    min_dy = -selection.bottom
    max_dy = int(image_height) - 1 - selection.top
    result_x = min(max(int(dx), min_dx), max_dx)
    result_y = min(max(int(dy), min_dy), max_dy)
    return result_x, result_y, (result_x != int(dx) or result_y != int(dy))


def _fill_value(mode: str, color: Sequence[float], channels: int) -> np.ndarray:
    rgba = np.asarray(tuple(color), dtype=np.float32)
    if rgba.shape != (4,):
        raise ValueError("Fill color must be RGBA")
    if mode == "TRANSPARENT":
        rgba = np.zeros(4, dtype=np.float32)
    elif mode == "BLACK":
        rgba = np.array((0.0, 0.0, 0.0, 1.0), dtype=np.float32)

    if channels == 1:
        return np.array((float(np.mean(rgba[:3])),), dtype=np.float32)
    if channels == 2:
        return np.array((float(np.mean(rgba[:3])), rgba[3]), dtype=np.float32)
    return rgba[:channels].copy()


def translate_pixels(
    source: np.ndarray,
    selection: PixelSelection,
    dx: int,
    dy: int,
    *,
    fill_mode: str = "TRANSPARENT",
    fill_color: Sequence[float] = (0.0, 0.0, 0.0, 0.0),
) -> np.ndarray:
    """Move selected raw pixel values without interpolation."""
    pixels = np.asarray(source)
    if pixels.ndim != 3 or not 1 <= pixels.shape[2] <= 4:
        raise ValueError("Source must have shape (height, width, 1-4 channels)")

    height, width, channels = pixels.shape
    dx = int(dx)
    dy = int(dy)
    if (
        selection.left + dx < 0
        or selection.bottom + dy < 0
        or selection.right + dx >= width
        or selection.top + dy >= height
    ):
        raise ValueError("Pixel destination is outside the image")

    local_y, local_x = np.nonzero(selection.mask)
    source_x = selection.left + local_x
    source_y = selection.bottom + local_y
    destination_x = source_x + dx
    destination_y = source_y + dy

    result = pixels.copy()
    if fill_mode != "KEEP":
        result[source_y, source_x, :] = _fill_value(fill_mode, fill_color, channels)
    result[destination_y, destination_x, :] = pixels[source_y, source_x, :]
    return result


def as_rgba(source: np.ndarray) -> np.ndarray:
    """Return a four-channel view/copy suitable for a Blender preview image."""
    pixels = np.asarray(source, dtype=np.float32)
    if pixels.ndim != 3 or not 1 <= pixels.shape[2] <= 4:
        raise ValueError("Source must have shape (height, width, 1-4 channels)")
    if pixels.shape[2] == 4:
        return pixels

    result = np.ones((*pixels.shape[:2], 4), dtype=np.float32)
    if pixels.shape[2] == 1:
        result[:, :, :3] = pixels
    elif pixels.shape[2] == 2:
        result[:, :, :3] = pixels[:, :, :1]
        result[:, :, 3] = pixels[:, :, 1]
    else:
        result[:, :, :3] = pixels
    return result
