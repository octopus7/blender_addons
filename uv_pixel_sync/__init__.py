# SPDX-License-Identifier: MIT

bl_info = {
    "name": "UV Pixel Sync",
    "author": "octopus7",
    "version": (1, 0, 0),
    "blender": (4, 5, 0),
    "location": "UV Editor > Sidebar > UV Pixel Sync",
    "description": "Move selected UVs and their texture pixels together",
    "category": "UV",
}

from .addon import register, unregister

__all__ = ("register", "unregister")
