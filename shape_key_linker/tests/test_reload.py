import importlib
import sys
from pathlib import Path

import bpy


ADDON_PARENT = Path(__file__).resolve().parents[2]
if str(ADDON_PARENT) not in sys.path:
    sys.path.insert(0, str(ADDON_PARENT))

addon = importlib.import_module("shape_key_linker")
addon.register()

target = bpy.data.objects["Target"]
source = bpy.data.objects["SmileRenamed"]
assert len(target.shape_key_linker_links) == 1
link = target.shape_key_linker_links[0]
assert link.source == source
assert link.shape_key_name == "Happy"

source.data.vertices[2].co.y = 5.0
bpy.context.view_layer.objects.active = target
target.select_set(True)
result = bpy.ops.object.shape_key_update_linked()
assert result == {'FINISHED'}
assert tuple(target.data.shape_keys.key_blocks["Happy"].data[2].co) == (0.0, 5.0, 0.0)

print("SHAPE_KEY_LINKER_RELOAD_TEST_OK")
addon.unregister()
