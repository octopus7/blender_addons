# SPDX-License-Identifier: MIT

from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from typing import Any

import blf
import bmesh
import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatVectorProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup

from .pixel_ops import PixelSelection, as_rgba, clamp_translation, rasterize_uv_selection, translate_pixels


PREVIEW_MARKER = ".UVPS_Preview"


@dataclass(frozen=True)
class UVPoint:
    face_index: int
    loop_index: int
    uv: tuple[float, float]


@dataclass
class PreviewSession:
    obj: Any
    mesh: Any
    uv_layer_name: str
    image: Any
    source_pixels: np.ndarray
    width: int
    height: int
    channels: int
    uv_points: list[UVPoint]
    pixel_selection: PixelSelection
    dx: int = 0
    dy: int = 0
    result_pixels: np.ndarray | None = None
    preview_image: Any = None
    image_spaces: list[Any] = field(default_factory=list)
    image_nodes: list[Any] = field(default_factory=list)


@dataclass
class ApplyBackup:
    obj: Any
    mesh: Any
    uv_layer_name: str
    image: Any
    pixels: np.ndarray
    uv_points: list[UVPoint]


_SESSION: PreviewSession | None = None
_BACKUP: ApplyBackup | None = None
_DRAW_HANDLE = None
_KEYMAP_ITEMS: list[tuple[Any, Any]] = []


class UVPS_PG_settings(PropertyGroup):
    padding: IntProperty(
        name="Padding",
        description="Include this many neighboring pixels around the selected UV area",
        default=0,
        min=0,
        max=64,
        subtype='PIXEL',
    )
    fill_mode: EnumProperty(
        name="Source Area",
        description="How to treat pixels at the old location",
        items=(
            ('TRANSPARENT', "Transparent", "Clear the old pixels to transparent black"),
            ('BLACK', "Black", "Fill the old pixels with opaque black"),
            ('CUSTOM', "Custom", "Use the selected RGBA color"),
            ('KEEP', "Keep (Copy)", "Keep the old pixels and copy them to the new location"),
        ),
        default='TRANSPARENT',
    )
    fill_color: FloatVectorProperty(
        name="Fill Color",
        subtype='COLOR',
        size=4,
        min=0.0,
        max=1.0,
        default=(0.0, 0.0, 0.0, 0.0),
    )
    material_preview: BoolProperty(
        name="3D Material Preview",
        description="Temporarily show the preview image in material Image Texture nodes",
        default=True,
    )


class UVPS_PG_runtime(PropertyGroup):
    state: StringProperty(default="IDLE", options={'SKIP_SAVE'})
    message: StringProperty(default="Ready", options={'SKIP_SAVE'})
    dx: IntProperty(default=0, options={'SKIP_SAVE'})
    dy: IntProperty(default=0, options={'SKIP_SAVE'})
    axis: StringProperty(default="FREE", options={'SKIP_SAVE'})
    clamped: BoolProperty(default=False, options={'SKIP_SAVE'})


def _runtime() -> UVPS_PG_runtime | None:
    wm = getattr(bpy.context, "window_manager", None)
    return getattr(wm, "uvps_runtime", None) if wm else None


def _redraw_image_editors() -> None:
    wm = getattr(bpy.context, "window_manager", None)
    if wm is None:
        return
    for window in wm.windows:
        if window.screen is None:
            continue
        for area in window.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                area.tag_redraw()


def _set_status(
    state: str,
    message: str,
    *,
    dx: int = 0,
    dy: int = 0,
    axis: str = "FREE",
    clamped: bool = False,
) -> None:
    runtime = _runtime()
    if runtime is not None:
        runtime.state = state
        runtime.message = message
        runtime.dx = int(dx)
        runtime.dy = int(dy)
        runtime.axis = axis
        runtime.clamped = bool(clamped)
    _redraw_image_editors()


def _source_image(context) -> Any:
    if _SESSION is not None:
        return _SESSION.image
    space = getattr(context, "space_data", None)
    if space is not None and getattr(space, "type", None) == 'IMAGE_EDITOR':
        return getattr(space, "image", None)
    return None


def _read_image(image) -> tuple[np.ndarray, int, int, int]:
    width, height = int(image.size[0]), int(image.size[1])
    if width <= 0 or height <= 0:
        raise RuntimeError("The active image has no pixel data")
    total_values = len(image.pixels)
    pixel_count = width * height
    if total_values == 0 or total_values % pixel_count:
        raise RuntimeError("Unsupported image pixel layout")
    channels = total_values // pixel_count
    if not 1 <= channels <= 4:
        raise RuntimeError(f"Unsupported image channel count: {channels}")

    flat = np.empty(total_values, dtype=np.float32)
    image.pixels.foreach_get(flat)
    return flat.reshape((height, width, channels)), width, height, channels


def _write_image(image, pixels: np.ndarray) -> None:
    flat = np.ascontiguousarray(pixels, dtype=np.float32).reshape(-1)
    if len(image.pixels) != flat.size:
        raise RuntimeError("The image dimensions changed during the operation")
    image.pixels.foreach_set(flat)
    image.update()


def _selected_uv_geometry(context) -> tuple[Any, Any, str, list[UVPoint], list[list[tuple[float, float]]]]:
    obj = context.edit_object
    if obj is None or obj.type != 'MESH':
        raise RuntimeError("Enter Mesh Edit Mode first")

    mesh = obj.data
    bm = bmesh.from_edit_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    uv_layer = bm.loops.layers.uv.active
    if uv_layer is None:
        raise RuntimeError("The mesh has no active UV map")

    visible_faces = [face for face in bm.faces if not face.hide and face.loops]
    if visible_faces and hasattr(visible_faces[0], "uv_select"):
        # Blender 5.x stores UV selection on BMesh faces/loops directly.
        uv_selected = [face for face in visible_faces if face.uv_select]
    else:
        # Blender 4.5 exposes it through the BMLoopUV custom-data value.
        uv_selected = [face for face in visible_faces if all(loop[uv_layer].select for loop in face.loops)]
    selected_faces = uv_selected or [face for face in visible_faces if face.select]
    if not selected_faces:
        raise RuntimeError("Select one or more complete UV faces or islands")

    points: list[UVPoint] = []
    polygons: list[list[tuple[float, float]]] = []
    for face in selected_faces:
        polygon: list[tuple[float, float]] = []
        for loop_index, loop in enumerate(face.loops):
            uv = loop[uv_layer].uv
            coordinates = (float(uv.x), float(uv.y))
            points.append(UVPoint(face.index, loop_index, coordinates))
            polygon.append(coordinates)
        polygons.append(polygon)
    return obj, mesh, uv_layer.name, points, polygons


def _write_uv_points(
    obj,
    mesh,
    uv_layer_name: str,
    points: list[UVPoint],
    dx: int,
    dy: int,
    width: int,
    height: int,
) -> None:
    if obj is None or obj.name not in bpy.data.objects or obj.mode != 'EDIT':
        raise RuntimeError("Keep the source mesh in Edit Mode")

    bm = bmesh.from_edit_mesh(mesh)
    bm.faces.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv.get(uv_layer_name)
    if uv_layer is None:
        raise RuntimeError("The UV map used by this operation no longer exists")

    offset_u = int(dx) / int(width)
    offset_v = int(dy) / int(height)
    for point in points:
        if point.face_index >= len(bm.faces):
            raise RuntimeError("Mesh topology changed during the operation")
        loops = bm.faces[point.face_index].loops
        if point.loop_index >= len(loops):
            raise RuntimeError("Mesh topology changed during the operation")
        loops[point.loop_index][uv_layer].uv = (
            point.uv[0] + offset_u,
            point.uv[1] + offset_v,
        )
    bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)


def _make_preview_image(session: PreviewSession):
    name = f"{session.image.name}{PREVIEW_MARKER}"
    existing = bpy.data.images.get(name)
    if existing is not None:
        bpy.data.images.remove(existing)

    preview = bpy.data.images.new(
        name,
        width=session.width,
        height=session.height,
        alpha=True,
        float_buffer=bool(getattr(session.image, "is_float", False)),
    )
    try:
        preview.colorspace_settings.name = session.image.colorspace_settings.name
        preview.alpha_mode = session.image.alpha_mode
    except Exception:
        pass
    preview.pixels.foreach_set(np.ascontiguousarray(as_rgba(session.result_pixels)).reshape(-1))
    preview.update()
    return preview


def _all_node_trees():
    seen: set[int] = set()
    for collection in (bpy.data.materials, bpy.data.worlds, bpy.data.lights, bpy.data.node_groups):
        for datablock in collection:
            tree = getattr(datablock, "node_tree", None)
            if tree is None or tree.as_pointer() in seen:
                continue
            seen.add(tree.as_pointer())
            yield tree


def _show_preview(session: PreviewSession, settings: UVPS_PG_settings) -> None:
    wm = bpy.context.window_manager
    for window in wm.windows:
        if window.screen is None:
            continue
        for area in window.screen.areas:
            if area.type != 'IMAGE_EDITOR':
                continue
            space = area.spaces.active
            if getattr(space, "image", None) == session.image:
                session.image_spaces.append(space)
                space.image = session.preview_image

    if settings.material_preview:
        for tree in _all_node_trees():
            for node in tree.nodes:
                if getattr(node, "bl_idname", "") == "ShaderNodeTexImage" and getattr(node, "image", None) == session.image:
                    session.image_nodes.append(node)
                    node.image = session.preview_image


def _restore_image_references(session: PreviewSession) -> None:
    for space in session.image_spaces:
        try:
            if space and space.image == session.preview_image:
                space.image = session.image
        except ReferenceError:
            pass
    for node in session.image_nodes:
        try:
            if node and node.image == session.preview_image:
                node.image = session.image
        except ReferenceError:
            pass
    session.image_spaces.clear()
    session.image_nodes.clear()


def _delete_preview_image(session: PreviewSession) -> None:
    preview = session.preview_image
    session.preview_image = None
    if preview is not None:
        try:
            bpy.data.images.remove(preview)
        except (ReferenceError, RuntimeError):
            pass


def _cancel_session(message="Preview cancelled") -> None:
    global _SESSION
    session = _SESSION
    if session is None:
        return
    try:
        _write_uv_points(
            session.obj,
            session.mesh,
            session.uv_layer_name,
            session.uv_points,
            0,
            0,
            session.width,
            session.height,
        )
    except Exception:
        traceback.print_exc()
    _restore_image_references(session)
    _delete_preview_image(session)
    _SESSION = None
    _set_status("IDLE", message)


def _movement_name(dx: int, dy: int, axis: str) -> str:
    if axis == 'X' or (dx and not dy):
        return "HORIZONTAL"
    if axis == 'Y' or (dy and not dx):
        return "VERTICAL"
    return "XY MOVE"


def _draw_hud() -> None:
    runtime = _runtime()
    context = bpy.context
    region = getattr(context, "region", None)
    area = getattr(context, "area", None)
    if runtime is None or runtime.state == "IDLE" or region is None or area is None or area.type != 'IMAGE_EDITOR':
        return

    if runtime.state == "MOVING":
        title = f"PIXEL SYNC · {_movement_name(runtime.dx, runtime.dy, runtime.axis)}"
        detail = f"X {runtime.dx:+d} px    Y {runtime.dy:+d} px"
        note = "Image boundary reached" if runtime.clamped else "Whole-pixel movement"
    elif runtime.state == "PREVIEW":
        title = "PREVIEW · ORIGINAL IMAGE UNCHANGED"
        detail = f"X {runtime.dx:+d} px    Y {runtime.dy:+d} px"
        note = "Use Apply or Cancel in the sidebar"
    else:
        title = runtime.message
        detail = ""
        note = ""

    font_id = 0
    x = 24
    y = region.height - 38
    blf.size(font_id, 15.0)
    blf.color(font_id, 0.35, 0.9, 1.0, 1.0)
    blf.position(font_id, x, y, 0)
    blf.draw(font_id, title)
    blf.size(font_id, 13.0)
    blf.color(font_id, 0.95, 0.95, 0.95, 1.0)
    if detail:
        blf.position(font_id, x, y - 22, 0)
        blf.draw(font_id, detail)
    if note:
        blf.color(font_id, 0.7, 0.7, 0.7, 1.0)
        blf.position(font_id, x, y - 42, 0)
        blf.draw(font_id, note)


class UVPS_OT_move(Operator):
    bl_idname = "uv.uv_pixel_sync_move"
    bl_label = "Move UV + Pixels"
    bl_description = "Move complete selected UV faces and matching pixels on whole-pixel steps"
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'}

    _session: PreviewSession | None = None
    _start_view = (0.0, 0.0)
    _axis = "FREE"

    @classmethod
    def poll(cls, context):
        return (
            _SESSION is None
            and context.area is not None
            and context.area.type == 'IMAGE_EDITOR'
            and context.mode == 'EDIT_MESH'
        )

    def invoke(self, context, event):
        image = _source_image(context)
        if image is None:
            self.report({'ERROR'}, "Select an image in the UV Editor")
            return {'CANCELLED'}
        if image.source == 'TILED':
            self.report({'ERROR'}, "UDIM images are not supported")
            return {'CANCELLED'}

        try:
            obj, mesh, uv_layer_name, uv_points, polygons = _selected_uv_geometry(context)
            pixels, width, height, channels = _read_image(image)
            settings = context.scene.uv_pixel_sync_settings
            selection = rasterize_uv_selection(polygons, width, height, settings.padding)
        except (RuntimeError, ValueError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}

        self._session = PreviewSession(
            obj=obj,
            mesh=mesh,
            uv_layer_name=uv_layer_name,
            image=image,
            source_pixels=pixels,
            width=width,
            height=height,
            channels=channels,
            uv_points=uv_points,
            pixel_selection=selection,
        )
        self._start_view = context.region.view2d.region_to_view(event.mouse_region_x, event.mouse_region_y)
        self._axis = "FREE"
        context.window.cursor_modal_set('SCROLL_XY')
        context.window_manager.modal_handler_add(self)
        _set_status("MOVING", "Move selected UVs", axis=self._axis)
        return {'RUNNING_MODAL'}

    def _update(self, context, event) -> None:
        session = self._session
        if session is None:
            return
        current = context.region.view2d.region_to_view(event.mouse_region_x, event.mouse_region_y)
        factor = 0.1 if event.shift else 1.0
        dx = round((current[0] - self._start_view[0]) * session.width * factor)
        dy = round((current[1] - self._start_view[1]) * session.height * factor)
        if self._axis == 'X':
            dy = 0
        elif self._axis == 'Y':
            dx = 0
        dx, dy, was_clamped = clamp_translation(
            session.pixel_selection,
            dx,
            dy,
            session.width,
            session.height,
        )
        if (dx, dy) != (session.dx, session.dy):
            _write_uv_points(
                session.obj,
                session.mesh,
                session.uv_layer_name,
                session.uv_points,
                dx,
                dy,
                session.width,
                session.height,
            )
            session.dx, session.dy = dx, dy
        _set_status(
            "MOVING",
            "Move selected UVs",
            dx=dx,
            dy=dy,
            axis=self._axis,
            clamped=was_clamped,
        )

    def _cancel(self, context):
        if self._session is not None:
            try:
                _write_uv_points(
                    self._session.obj,
                    self._session.mesh,
                    self._session.uv_layer_name,
                    self._session.uv_points,
                    0,
                    0,
                    self._session.width,
                    self._session.height,
                )
            except Exception:
                traceback.print_exc()
        context.window.cursor_modal_restore()
        self._session = None
        _set_status("IDLE", "Move cancelled")
        return {'CANCELLED'}

    def _finish(self, context):
        global _SESSION
        session = self._session
        if session is None or (session.dx == 0 and session.dy == 0):
            return self._cancel(context)
        try:
            settings = context.scene.uv_pixel_sync_settings
            session.result_pixels = translate_pixels(
                session.source_pixels,
                session.pixel_selection,
                session.dx,
                session.dy,
                fill_mode=settings.fill_mode,
                fill_color=settings.fill_color,
            )
            session.preview_image = _make_preview_image(session)
            _SESSION = session
            _show_preview(session, settings)
            _set_status("PREVIEW", "Preview ready", dx=session.dx, dy=session.dy, axis=self._axis)
            context.window.cursor_modal_restore()
            self._session = None
            return {'FINISHED'}
        except Exception as error:
            traceback.print_exc()
            self.report({'ERROR'}, str(error))
            return self._cancel(context)

    def modal(self, context, event):
        if self._session is None:
            context.window.cursor_modal_restore()
            return {'CANCELLED'}
        if event.type == 'MOUSEMOVE':
            try:
                self._update(context, event)
            except Exception as error:
                self.report({'ERROR'}, str(error))
                return self._cancel(context)
            return {'RUNNING_MODAL'}
        if event.type in {'X', 'Y'} and event.value == 'PRESS':
            self._axis = event.type if self._axis != event.type else "FREE"
            self._update(context, event)
            return {'RUNNING_MODAL'}
        if event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER'} and event.value in {'PRESS', 'RELEASE'}:
            if event.type != 'LEFTMOUSE' or (self._session.dx, self._session.dy) != (0, 0):
                return self._finish(context)
        if event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            return self._cancel(context)
        return {'RUNNING_MODAL'}


class UVPS_OT_apply(Operator):
    bl_idname = "uv.uv_pixel_sync_apply"
    bl_label = "Apply"
    bl_description = "Write the preview pixels to the original image datablock"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _SESSION is not None and _SESSION.result_pixels is not None

    def execute(self, context):
        global _SESSION, _BACKUP
        session = _SESSION
        if session is None or session.result_pixels is None:
            return {'CANCELLED'}
        try:
            _write_image(session.image, session.result_pixels)
            _restore_image_references(session)
            _delete_preview_image(session)
            _BACKUP = ApplyBackup(
                obj=session.obj,
                mesh=session.mesh,
                uv_layer_name=session.uv_layer_name,
                image=session.image,
                pixels=session.source_pixels,
                uv_points=session.uv_points,
            )
            dx, dy = session.dx, session.dy
            _SESSION = None
            _set_status("APPLIED", "Applied in memory", dx=dx, dy=dy)
            self.report({'INFO'}, "Applied in memory; save the image to write it to disk")
            return {'FINISHED'}
        except Exception as error:
            traceback.print_exc()
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


class UVPS_OT_cancel(Operator):
    bl_idname = "uv.uv_pixel_sync_cancel"
    bl_label = "Cancel"
    bl_description = "Discard the preview and restore the original UV coordinates"

    @classmethod
    def poll(cls, context):
        return _SESSION is not None

    def execute(self, context):
        _cancel_session()
        return {'FINISHED'}


class UVPS_OT_revert(Operator):
    bl_idname = "uv.uv_pixel_sync_revert"
    bl_label = "Revert Last Apply"
    bl_description = "Restore pixels and UV coordinates from the last Apply"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _BACKUP is not None and _SESSION is None

    def execute(self, context):
        global _BACKUP
        backup = _BACKUP
        if backup is None:
            return {'CANCELLED'}
        try:
            _write_image(backup.image, backup.pixels)
            height, width = backup.pixels.shape[:2]
            _write_uv_points(
                backup.obj,
                backup.mesh,
                backup.uv_layer_name,
                backup.uv_points,
                0,
                0,
                width,
                height,
            )
            _BACKUP = None
            _set_status("IDLE", "Last apply reverted")
            return {'FINISHED'}
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


class UVPS_OT_save_image(Operator):
    bl_idname = "uv.uv_pixel_sync_save_image"
    bl_label = "Save Image"
    bl_description = "Save the original image datablock to its file"

    def execute(self, context):
        image = _source_image(context)
        if image is None:
            self.report({'ERROR'}, "No active image")
            return {'CANCELLED'}
        if not image.filepath_raw:
            self.report({'WARNING'}, "The image has no file path; use Image > Save As")
            return {'CANCELLED'}
        try:
            image.save()
            self.report({'INFO'}, f"Saved '{image.name}'")
            return {'FINISHED'}
        except RuntimeError as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


class UVPS_PT_sidebar(Panel):
    bl_label = "UV Pixel Sync"
    bl_idname = "UVPS_PT_sidebar"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "UV Pixel Sync"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.uv_pixel_sync_settings
        runtime = _runtime()
        image = _source_image(context)

        status = layout.box()
        if _SESSION is not None:
            status.label(text="Preview Ready — Not Applied", icon='HIDE_OFF')
            status.label(text=f"X {_SESSION.dx:+d} px   Y {_SESSION.dy:+d} px")
        elif runtime is not None and runtime.state == "APPLIED":
            status.label(text="Applied in Memory", icon='CHECKMARK')
            status.label(text="Save Image to write the file")
        else:
            status.label(text="Ready", icon='UV')
        status.label(text=image.name if image else "No image selected", icon='IMAGE_DATA')

        if _SESSION is None:
            button = layout.row()
            button.scale_y = 1.4
            button.operator("uv.uv_pixel_sync_move", icon='TRANSFORM_MOVE')
        else:
            row = layout.row(align=True)
            row.scale_y = 1.3
            row.operator("uv.uv_pixel_sync_apply", icon='CHECKMARK')
            row.operator("uv.uv_pixel_sync_cancel", icon='X')

        options = layout.box()
        options.label(text="Pixel Options")
        options.prop(settings, "padding")
        options.prop(settings, "fill_mode")
        if settings.fill_mode == 'CUSTOM':
            options.prop(settings, "fill_color")
        options.prop(settings, "material_preview")

        row = layout.row(align=True)
        row.operator("uv.uv_pixel_sync_save_image", icon='FILE_TICK')
        row.operator("uv.uv_pixel_sync_revert", text="Revert Last", icon='LOOP_BACK')

        help_box = layout.box()
        help_box.label(text="Move: Mouse")
        help_box.label(text="Constrain: X / Y")
        help_box.label(text="Fine movement: Shift")
        help_box.label(text="Confirm: Click / Enter")
        help_box.label(text="Cancel: Esc / Right Mouse")


def _draw_uv_menu(self, context):
    self.layout.separator()
    self.layout.operator("uv.uv_pixel_sync_move", icon='TRANSFORM_MOVE')


CLASSES = (
    UVPS_PG_settings,
    UVPS_PG_runtime,
    UVPS_OT_move,
    UVPS_OT_apply,
    UVPS_OT_cancel,
    UVPS_OT_revert,
    UVPS_OT_save_image,
    UVPS_PT_sidebar,
)


def register():
    global _DRAW_HANDLE
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.uv_pixel_sync_settings = PointerProperty(type=UVPS_PG_settings)
    bpy.types.WindowManager.uvps_runtime = PointerProperty(type=UVPS_PG_runtime)

    _DRAW_HANDLE = bpy.types.SpaceImageEditor.draw_handler_add(_draw_hud, (), 'WINDOW', 'POST_PIXEL')
    menu = getattr(bpy.types, "IMAGE_MT_uvs", None)
    if menu is not None:
        menu.append(_draw_uv_menu)

    keyconfig = bpy.context.window_manager.keyconfigs.addon
    if keyconfig is not None:
        keymap = keyconfig.keymaps.new(name="UV Editor", space_type='IMAGE_EDITOR')
        item = keymap.keymap_items.new("uv.uv_pixel_sync_move", 'G', 'PRESS', ctrl=True, shift=True)
        _KEYMAP_ITEMS.append((keymap, item))


def unregister():
    global _DRAW_HANDLE, _BACKUP
    if _SESSION is not None:
        _cancel_session()

    for keymap, item in _KEYMAP_ITEMS:
        try:
            keymap.keymap_items.remove(item)
        except (ReferenceError, RuntimeError):
            pass
    _KEYMAP_ITEMS.clear()

    menu = getattr(bpy.types, "IMAGE_MT_uvs", None)
    if menu is not None:
        try:
            menu.remove(_draw_uv_menu)
        except RuntimeError:
            pass

    if _DRAW_HANDLE is not None:
        bpy.types.SpaceImageEditor.draw_handler_remove(_DRAW_HANDLE, 'WINDOW')
        _DRAW_HANDLE = None

    if hasattr(bpy.types.WindowManager, "uvps_runtime"):
        del bpy.types.WindowManager.uvps_runtime
    if hasattr(bpy.types.Scene, "uv_pixel_sync_settings"):
        del bpy.types.Scene.uv_pixel_sync_settings
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
    _BACKUP = None
