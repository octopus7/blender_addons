# SPDX-License-Identifier: GPL-3.0-or-later

bl_info = {
    "name": "Shape Key Linker",
    "author": "blendue",
    "version": (1, 1, 6),
    "blender": (4, 5, 0),
    "location": "Object Data Properties > Shape Keys",
    "description": "Link external meshes to shape keys and update them later",
    "category": "Animation",
}

from .addon import register, unregister

__all__ = ("register", "unregister")
