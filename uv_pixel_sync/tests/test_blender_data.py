import importlib
import sys
from pathlib import Path

import bpy
import numpy as np


ADDON_PARENT = Path(__file__).resolve().parents[2]
if str(ADDON_PARENT) not in sys.path:
    sys.path.insert(0, str(ADDON_PARENT))

addon_module = importlib.import_module("uv_pixel_sync.addon")

image = bpy.data.images.new("UVPS_Test", width=4, height=4, alpha=True, float_buffer=True)
pixels = np.arange(4 * 4 * 4, dtype=np.float32).reshape((4, 4, 4)) / 64.0
addon_module._write_image(image, pixels)
read_back, width, height, channels = addon_module._read_image(image)
assert (width, height, channels) == (4, 4, 4)
assert np.allclose(read_back, pixels)

mesh = bpy.data.meshes.new("UVPS_TestMesh")
mesh.from_pydata(
    [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)],
    [],
    [(0, 1, 2, 3)],
)
uv_layer = mesh.uv_layers.new(name="UVMap")
for loop, uv in zip(mesh.loops, ((0.25, 0.25), (0.50, 0.25), (0.50, 0.50), (0.25, 0.50))):
    uv_layer.uv[loop.index].vector = uv

obj = bpy.data.objects.new("UVPS_TestObject", mesh)
bpy.context.scene.collection.objects.link(obj)
bpy.context.view_layer.objects.active = obj
obj.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')

found_obj, found_mesh, layer_name, points, polygons = addon_module._selected_uv_geometry(bpy.context)
assert found_obj == obj and found_mesh == mesh and layer_name == "UVMap"
assert len(points) == 4 and len(polygons) == 1

addon_module._write_uv_points(obj, mesh, layer_name, points, 1, -1, 4, 4)
bpy.ops.object.mode_set(mode='OBJECT')
result_layer = mesh.uv_layers[layer_name]
actual = [tuple(result_layer.uv[loop.index].vector) for loop in mesh.loops]
expected = [(0.50, 0.00), (0.75, 0.00), (0.75, 0.25), (0.50, 0.25)]
for value, target in zip(actual, expected):
    assert np.allclose(value, target), f"Expected {target}, got {value}; all UVs: {actual}"

print("UV_PIXEL_SYNC_BLENDER_DATA_TEST_OK")
