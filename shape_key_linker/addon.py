# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from array import array

import bpy
from bpy.props import BoolProperty, CollectionProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Menu, Object, Operator, PropertyGroup, UIList


def _active_mesh(context):
    obj = context.active_object
    if obj is None or obj.type != 'MESH':
        return None
    return obj


def _shape_keys(target):
    keys = target.data.shape_keys
    return keys.key_blocks if keys else None


def _find_key(target, link):
    key_blocks = _shape_keys(target)
    if not key_blocks:
        return None

    key = key_blocks.get(link.shape_key_name)
    if key is not None:
        link.shape_key_index = key_blocks.find(key.name)
        link.target_key_count = len(key_blocks)
        return key

    # A stable index is only trusted when the number of keys has not changed.
    # This lets us follow a simple rename without ever overwriting a neighboring
    # key after a deletion or insertion.
    if (
        link.target_key_count == len(key_blocks)
        and 0 < link.shape_key_index < len(key_blocks)
    ):
        key = key_blocks[link.shape_key_index]
        link.shape_key_name = key.name
        return key
    return None


def _ensure_basis(target):
    if target.data.shape_keys is None:
        target.shape_key_add(name="Basis", from_mix=False)


def _new_linked_key(target, source, link):
    _ensure_basis(target)
    requested_name = link.shape_key_name or source.name
    key = target.shape_key_add(name=requested_name, from_mix=False)
    link.shape_key_name = key.name
    link.shape_key_index = target.data.shape_keys.key_blocks.find(key.name)
    link.target_key_count = len(target.data.shape_keys.key_blocks)
    return key


def _evaluated_coordinates(source, depsgraph):
    evaluated = source.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=False, depsgraph=depsgraph)
    try:
        coordinates = array('f', [0.0]) * (len(mesh.vertices) * 3)
        mesh.vertices.foreach_get("co", coordinates)
        return coordinates, len(mesh.vertices)
    finally:
        evaluated.to_mesh_clear()


def _copy_coordinates_to_key(target, key, coordinates, source_count):
    target_count = len(target.data.vertices)
    key_count = len(key.data)

    if source_count != target_count or key_count != target_count:
        raise ValueError(
            f"vertex count mismatch: source {source_count}, target {target_count}, "
            f"shape key {key_count}"
        )

    key.data.foreach_set("co", coordinates)
    target.data.update()
    return source_count


def _link_for_source(target, source):
    for link in target.shape_key_linker_links:
        if link.source == source:
            return link
    return None


def _update_link(target, link, depsgraph, create_missing=True):
    source = link.source
    if source is None:
        return False, f"source '{link.source_name or 'Unknown'}' is missing"
    if source.type != 'MESH':
        return False, f"source '{source.name}' is not a mesh"
    if source == target:
        return False, "source and target cannot be the same object"

    try:
        coordinates, source_count = _evaluated_coordinates(source, depsgraph)
    except RuntimeError as exc:
        return False, f"could not evaluate source mesh: {exc}"

    target_count = len(target.data.vertices)
    if source_count != target_count:
        return False, f"vertex count mismatch: source {source_count}, target {target_count}"

    key = _find_key(target, link)
    if key is None:
        if not create_missing:
            return False, f"shape key '{link.shape_key_name}' is missing"
        key = _new_linked_key(target, source, link)

    try:
        count = _copy_coordinates_to_key(target, key, coordinates, source_count)
    except ValueError as exc:
        return False, str(exc)

    link.source_name = source.name
    link.source_vertex_count = count
    link.shape_key_name = key.name
    link.shape_key_index = target.data.shape_keys.key_blocks.find(key.name)
    link.target_key_count = len(target.data.shape_keys.key_blocks)
    return True, key.name


class SKL_PG_link(PropertyGroup):
    source: PointerProperty(
        name="Source",
        description="Source mesh used to update this shape key",
        type=Object,
    )
    source_name: StringProperty(
        name="Last Source Name",
        description="Last known source name, retained when the source is deleted",
    )
    shape_key_name: StringProperty(
        name="Shape Key",
        description="Linked shape key name",
    )
    source_vertex_count: IntProperty(default=0, options={'HIDDEN'})
    shape_key_index: IntProperty(default=-1, options={'HIDDEN'})
    target_key_count: IntProperty(default=0, options={'HIDDEN'})
    enabled: BoolProperty(
        name="Enabled",
        description="Include this link when updating all linked shapes",
        default=True,
    )


class SKL_OT_join_and_link(Operator):
    bl_idname = "object.shape_key_join_and_link"
    bl_label = "Join & Link as Shapes"
    bl_description = (
        "Create shape keys from the selected mesh objects and remember their sources "
        "for future updates"
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        target = _active_mesh(context)
        return target is not None and target.mode == 'OBJECT'

    def execute(self, context):
        target = _active_mesh(context)
        sources = [
            obj for obj in context.selected_objects
            if obj != target and obj.type == 'MESH'
        ]
        if not sources:
            self.report({'ERROR'}, "Select one or more source meshes, then make the target active")
            return {'CANCELLED'}

        depsgraph = context.evaluated_depsgraph_get()
        created = 0
        updated = 0
        failures = []

        for source in sources:
            link = _link_for_source(target, source)
            is_new = link is None
            if is_new:
                link = target.shape_key_linker_links.add()
                link.source = source
                link.source_name = source.name
                link.shape_key_name = source.name

            ok, detail = _update_link(target, link, depsgraph, create_missing=True)
            if ok:
                if is_new:
                    created += 1
                else:
                    updated += 1
            else:
                failures.append(f"{source.name}: {detail}")
                if is_new:
                    target.shape_key_linker_links.remove(len(target.shape_key_linker_links) - 1)

        if created or updated:
            target.shape_key_linker_index = max(0, len(target.shape_key_linker_links) - 1)
            message = f"Linked {created} new shape(s)"
            if updated:
                message += f", updated {updated} existing link(s)"
            if failures:
                message += f"; skipped {len(failures)}"
                self.report({'WARNING'}, message + " — " + failures[0])
            else:
                self.report({'INFO'}, message)
            return {'FINISHED'}

        self.report({'ERROR'}, failures[0] if failures else "No shape keys were linked")
        return {'CANCELLED'}


class SKL_OT_update_all(Operator):
    bl_idname = "object.shape_key_update_linked"
    bl_label = "Update Linked Shapes"
    bl_description = "Update every enabled linked shape key without selecting its source"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        target = _active_mesh(context)
        return (
            target is not None
            and target.mode == 'OBJECT'
            and len(target.shape_key_linker_links) > 0
        )

    def execute(self, context):
        target = _active_mesh(context)
        depsgraph = context.evaluated_depsgraph_get()
        updated = 0
        failures = []

        for link in target.shape_key_linker_links:
            if not link.enabled:
                continue
            ok, detail = _update_link(target, link, depsgraph, create_missing=True)
            if ok:
                updated += 1
            else:
                failures.append(f"{link.source_name or link.shape_key_name}: {detail}")

        if failures:
            self.report(
                {'WARNING'},
                f"Updated {updated}; failed {len(failures)} — {failures[0]}",
            )
        else:
            self.report({'INFO'}, f"Updated {updated} linked shape(s)")
        return {'FINISHED'} if updated else {'CANCELLED'}


class SKL_OT_update_active(Operator):
    bl_idname = "object.shape_key_update_linked_active"
    bl_label = "Update Active Shape"
    bl_description = "Update the active shape key from its linked source"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        target = _active_mesh(context)
        return (
            target is not None
            and target.mode == 'OBJECT'
            and target.active_shape_key is not None
            and len(target.shape_key_linker_links) > 0
        )

    def execute(self, context):
        target = _active_mesh(context)
        active_key = target.active_shape_key
        if active_key is None:
            self.report({'ERROR'}, "No active shape key")
            return {'CANCELLED'}

        active_link = None
        for link in target.shape_key_linker_links:
            if _find_key(target, link) == active_key:
                active_link = link
                break

        if active_link is None:
            self.report({'ERROR'}, f"Shape key '{active_key.name}' is not linked")
            return {'CANCELLED'}

        ok, detail = _update_link(
            target,
            active_link,
            context.evaluated_depsgraph_get(),
            create_missing=False,
        )
        if not ok:
            self.report({'ERROR'}, detail)
            return {'CANCELLED'}

        self.report({'INFO'}, f"Updated active shape '{detail}'")
        return {'FINISHED'}


class SKL_OT_update_one(Operator):
    bl_idname = "object.shape_key_update_linked_one"
    bl_label = "Update Linked Shape"
    bl_description = "Update this shape key from its linked source"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        target = _active_mesh(context)
        return target is not None and target.mode == 'OBJECT'

    def execute(self, context):
        target = _active_mesh(context)
        if self.index < 0 or self.index >= len(target.shape_key_linker_links):
            self.report({'ERROR'}, "Linked shape entry no longer exists")
            return {'CANCELLED'}

        link = target.shape_key_linker_links[self.index]
        ok, detail = _update_link(
            target,
            link,
            context.evaluated_depsgraph_get(),
            create_missing=True,
        )
        if not ok:
            self.report({'ERROR'}, detail)
            return {'CANCELLED'}
        self.report({'INFO'}, f"Updated '{detail}'")
        return {'FINISHED'}


class SKL_OT_remove_link(Operator):
    bl_idname = "object.shape_key_remove_link"
    bl_label = "Unlink Shape Key"
    bl_description = "Remove the source link but keep the shape key"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        target = _active_mesh(context)
        return target is not None and len(target.shape_key_linker_links) > 0

    def execute(self, context):
        target = _active_mesh(context)
        if self.index < 0 or self.index >= len(target.shape_key_linker_links):
            return {'CANCELLED'}
        target.shape_key_linker_links.remove(self.index)
        target.shape_key_linker_index = min(
            target.shape_key_linker_index,
            max(0, len(target.shape_key_linker_links) - 1),
        )
        return {'FINISHED'}


class SKL_UL_links(UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        target = data
        link = item
        row = layout.row(align=True)
        row.prop(link, "enabled", text="")

        source = link.source
        key = _find_key(target, link)
        if source is None or source.type != 'MESH' or key is None:
            status_icon = 'ERROR'
        elif len(source.data.vertices) != len(target.data.vertices):
            status_icon = 'ERROR'
        else:
            status_icon = 'LINKED'

        row.prop(link, "source", text="", icon=status_icon)
        row.label(text=link.shape_key_name or "Missing Shape Key", icon='SHAPEKEY_DATA')
        op = row.operator("object.shape_key_update_linked_one", text="", icon='FILE_REFRESH')
        op.index = index
        op = row.operator("object.shape_key_remove_link", text="", icon='X')
        op.index = index


def _draw_linker_in_shape_keys(self, context):
    target = _active_mesh(context)
    if target is None:
        return

    layout = self.layout
    layout.separator()
    box = layout.box()
    box.label(text="Shape Key Linker", icon='LINKED')

    buttons = box.column(align=True)
    buttons.operator("object.shape_key_join_and_link", icon='ADD')
    buttons.operator("object.shape_key_update_linked_active", icon='SHAPEKEY_DATA')
    buttons.operator("object.shape_key_update_linked", text="Update All", icon='FILE_REFRESH')

    if not target.shape_key_linker_links:
        info = box.column(align=True)
        info.label(text="Select source mesh(es), then make target active.", icon='INFO')
        info.label(text="Join & Link stores the source for later updates.")
        return

    box.template_list(
        "SKL_UL_links",
        "",
        target,
        "shape_key_linker_links",
        target,
        "shape_key_linker_index",
        rows=min(6, max(2, len(target.shape_key_linker_links))),
    )

    box.label(text="Object transforms are ignored; vertex order must match.", icon='INFO')


def _draw_shape_key_menu(self: Menu, context):
    layout = self.layout
    layout.separator()
    layout.operator("object.shape_key_join_and_link", icon='LINKED')
    layout.operator("object.shape_key_update_linked_active", icon='SHAPEKEY_DATA')
    layout.operator("object.shape_key_update_linked", icon='FILE_REFRESH')


CLASSES = (
    SKL_PG_link,
    SKL_OT_join_and_link,
    SKL_OT_update_all,
    SKL_OT_update_active,
    SKL_OT_update_one,
    SKL_OT_remove_link,
    SKL_UL_links,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)

    bpy.types.Object.shape_key_linker_links = CollectionProperty(type=SKL_PG_link)
    bpy.types.Object.shape_key_linker_index = IntProperty(default=0)
    bpy.types.DATA_PT_shape_keys.append(_draw_linker_in_shape_keys)
    bpy.types.MESH_MT_shape_key_context_menu.append(_draw_shape_key_menu)


def unregister():
    bpy.types.MESH_MT_shape_key_context_menu.remove(_draw_shape_key_menu)
    bpy.types.DATA_PT_shape_keys.remove(_draw_linker_in_shape_keys)
    del bpy.types.Object.shape_key_linker_index
    del bpy.types.Object.shape_key_linker_links

    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
