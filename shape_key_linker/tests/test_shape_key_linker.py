import importlib
import sys
from pathlib import Path

import bmesh
import bpy


ADDON_PARENT = Path(__file__).resolve().parents[2]
if str(ADDON_PARENT) not in sys.path:
    sys.path.insert(0, str(ADDON_PARENT))

addon = importlib.import_module("shape_key_linker")
implementation = importlib.import_module("shape_key_linker.addon")
addon.register()


def mesh_object(name, coordinates):
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(coordinates, [], [(0, 1, 2)])
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


target = mesh_object("Target", [(0, 0, 0), (1, 0, 0), (0, 1, 0)])
source = mesh_object("Smile", [(0, 0, 0), (1, 0, 0), (0, 2, 0)])

for obj in bpy.context.selected_objects:
    obj.select_set(False)
target.select_set(True)
source.select_set(True)
bpy.context.view_layer.objects.active = target

result = bpy.ops.object.shape_key_join_and_link()
assert result == {'FINISHED'}
assert len(target.shape_key_linker_links) == 1
link = target.shape_key_linker_links[0]
assert link.source == source
assert link.shape_key_name == "Smile"
assert tuple(target.data.shape_keys.key_blocks["Smile"].data[2].co) == (0.0, 2.0, 0.0)
assert target.shape_key_linker_live is False
assert implementation._live_depsgraph_update in bpy.app.handlers.depsgraph_update_post

source.data.vertices[2].co.y = 3.0
source.name = "SmileRenamed"
for obj in bpy.context.selected_objects:
    obj.select_set(False)
target.select_set(True)
bpy.context.view_layer.objects.active = target

result = bpy.ops.object.shape_key_update_linked()
assert result == {'FINISHED'}
assert tuple(target.data.shape_keys.key_blocks["Smile"].data[2].co) == (0.0, 3.0, 0.0)
assert link.source_name == "SmileRenamed"

# The refresh button on a link row updates only that source/key pair.
source.data.vertices[2].co.y = 3.5
result = bpy.ops.object.shape_key_update_linked_one(index=0)
assert result == {'FINISHED'}
assert tuple(target.data.shape_keys.key_blocks["Smile"].data[2].co) == (0.0, 3.5, 0.0)

target.data.shape_keys.key_blocks["Smile"].name = "Happy"
source.data.vertices[2].co.y = 4.0
result = bpy.ops.object.shape_key_update_linked()
assert result == {'FINISHED'}
assert link.shape_key_name == "Happy"
assert tuple(target.data.shape_keys.key_blocks["Happy"].data[2].co) == (0.0, 4.0, 0.0)

# A missing linked key is recreated, while the source link is preserved.
target.shape_key_remove(target.data.shape_keys.key_blocks["Happy"])
source.data.vertices[2].co.y = 4.5
result = bpy.ops.object.shape_key_update_linked()
assert result == {'FINISHED'}
assert tuple(target.data.shape_keys.key_blocks["Happy"].data[2].co) == (0.0, 4.5, 0.0)

# Live Update is opt-in and refreshes enabled links through the debounced queue.
target.shape_key_linker_live = True
implementation._run_live_updates()
source.data.vertices[2].co.y = 4.75
source.data.update()
bpy.context.view_layer.update()
assert target.as_pointer() in implementation._LIVE_DIRTY
implementation._run_live_updates()
assert tuple(target.data.shape_keys.key_blocks["Happy"].data[2].co) == (0.0, 4.75, 0.0)

# Live Update also follows source changes made in Mesh Edit Mode.
for obj in bpy.context.selected_objects:
    obj.select_set(False)
source.select_set(True)
bpy.context.view_layer.objects.active = source
bpy.ops.object.mode_set(mode='EDIT')
edit_mesh = bmesh.from_edit_mesh(source.data)
edit_mesh.verts.ensure_lookup_table()
edit_mesh.verts[2].co.y = 4.875
bmesh.update_edit_mesh(source.data, loop_triangles=False, destructive=False)
bpy.context.view_layer.update()
assert target.as_pointer() in implementation._LIVE_DIRTY
implementation._run_live_updates()
assert tuple(target.data.shape_keys.key_blocks["Happy"].data[2].co) == (0.0, 4.875, 0.0)
bpy.ops.object.mode_set(mode='OBJECT')
target.shape_key_linker_live = False

# A topology mismatch must not leave either a link or an orphan shape key.
bad_source = mesh_object(
    "WrongTopology",
    [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)],
)
for obj in bpy.context.selected_objects:
    obj.select_set(False)
bad_source.select_set(True)
target.select_set(True)
bpy.context.view_layer.objects.active = target
key_count_before = len(target.data.shape_keys.key_blocks)
try:
    result = bpy.ops.object.shape_key_join_and_link()
except RuntimeError:
    # Blender raises Python-side when an operator reports ERROR and cancels.
    result = {'CANCELLED'}
assert result == {'CANCELLED'}
assert len(target.data.shape_keys.key_blocks) == key_count_before
assert len(target.shape_key_linker_links) == 1

bpy.ops.wm.save_as_mainfile(filepath=str(Path(__file__).with_name("shape_key_linker_test.blend")))
print("SHAPE_KEY_LINKER_TEST_OK")

addon.unregister()
