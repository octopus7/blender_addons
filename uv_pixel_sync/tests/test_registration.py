import importlib
import sys
from pathlib import Path

import bpy


ADDON_PARENT = Path(__file__).resolve().parents[2]
if str(ADDON_PARENT) not in sys.path:
    sys.path.insert(0, str(ADDON_PARENT))

addon = importlib.import_module("uv_pixel_sync")
addon.register()

assert hasattr(bpy.types.Scene, "uv_pixel_sync_settings")
assert hasattr(bpy.types.WindowManager, "uvps_runtime")
assert addon.addon.UVPS_OT_move.is_registered
assert addon.addon.UVPS_PT_sidebar.is_registered

addon.unregister()
assert not hasattr(bpy.types.Scene, "uv_pixel_sync_settings")
assert not hasattr(bpy.types.WindowManager, "uvps_runtime")

print("UV_PIXEL_SYNC_REGISTRATION_TEST_OK")
