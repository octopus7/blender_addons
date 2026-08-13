import importlib.util
import sys
from pathlib import Path

import numpy as np


MODULE_PATH = Path(__file__).resolve().parents[1] / "pixel_ops.py"
spec = importlib.util.spec_from_file_location("uv_pixel_sync_pixel_ops_test", MODULE_PATH)
pixel_ops = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pixel_ops
spec.loader.exec_module(pixel_ops)


selection = pixel_ops.rasterize_uv_selection(
    [[(0.25, 0.25), (0.50, 0.25), (0.50, 0.50), (0.25, 0.50)]],
    8,
    8,
)
assert (selection.left, selection.bottom, selection.width, selection.height) == (2, 2, 2, 2)
assert np.all(selection.mask)

source = np.zeros((8, 8, 4), dtype=np.float32)
source[2:4, 2:4, :] = (1.0, 0.25, 0.5, 1.0)
moved = pixel_ops.translate_pixels(source, selection, 2, 1, fill_mode="TRANSPARENT")
assert np.allclose(moved[3:5, 4:6], (1.0, 0.25, 0.5, 1.0))
assert np.allclose(moved[2:4, 2:4], 0.0)
assert np.allclose(source[2:4, 2:4], (1.0, 0.25, 0.5, 1.0))

copied = pixel_ops.translate_pixels(source, selection, 2, 1, fill_mode="KEEP")
assert np.allclose(copied[2:4, 2:4], (1.0, 0.25, 0.5, 1.0))
assert np.allclose(copied[3:5, 4:6], (1.0, 0.25, 0.5, 1.0))

dx, dy, clamped = pixel_ops.clamp_translation(selection, 100, -100, 8, 8)
assert (dx, dy, clamped) == (4, -2, True)

padded = pixel_ops.rasterize_uv_selection(
    [[(0.25, 0.25), (0.50, 0.25), (0.50, 0.50), (0.25, 0.50)]],
    8,
    8,
    padding=1,
)
assert (padded.left, padded.bottom, padded.width, padded.height) == (1, 1, 4, 4)
assert np.count_nonzero(padded.mask) == 16

rgb = np.ones((2, 3, 3), dtype=np.float32)
rgba = pixel_ops.as_rgba(rgb)
assert rgba.shape == (2, 3, 4)
assert np.allclose(rgba[:, :, 3], 1.0)

try:
    pixel_ops.rasterize_uv_selection([[(-0.1, 0.0), (0.5, 0.0), (0.5, 0.5)]], 8, 8)
except ValueError as error:
    assert "0-1" in str(error)
else:
    raise AssertionError("UVs outside the 0-1 tile must fail")

print("UV_PIXEL_SYNC_PIXEL_OPS_TEST_OK")
