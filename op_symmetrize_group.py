import bpy
from bpy.types import Operator, Panel, UIList, PropertyGroup
from bpy.props import (
    FloatProperty,
    IntProperty,
    StringProperty,
    EnumProperty,
    PointerProperty,
    CollectionProperty,
)
import bmesh
from .op_symmetrize_preview import UV_OT_mio3_symmetry_preview


class OBJECT_OT_mio3qs_uv_group_add(Operator):
    bl_idname = "object.mio3qs_uv_group_add"
    bl_label = "Add Group"
    bl_description = "Add a weighted vertex group"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.mio3qs.selected_vertex_group

    def invoke(self, context, event):
        obj = context.active_object
        if not obj or obj.type != "MESH":
            self.report({"ERROR"}, "No active mesh object")
            return {"CANCELLED"}
        return self.execute(context)

    def execute(self, context):
        obj = context.active_object
        selected_group_name = obj.mio3qs.selected_vertex_group

        if obj.vertex_groups.get(selected_group_name) is None:
            return {"CANCELLED"}

        uv_group = obj.mio3qs.uv_group
        item = uv_group.items.add()
        item.name = selected_group_name
        return {"FINISHED"}


class OBJECT_OT_mio3qs_update_by_vertex(Operator):
    bl_idname = "object.mio3qs_update_by_vertex"
    bl_label = "Update from UV"
    bl_description = "Update UV Group coords from Active UV"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.mode == "EDIT"

    def invoke(self, context, event):
        obj = context.active_object
        if not obj or obj.type != "MESH":
            self.report({"ERROR"}, "No active mesh object")
            return {"CANCELLED"}

        return self.execute(context)

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != "MESH":
            return {"CANCELLED"}

        uv_group = obj.mio3qs.uv_group
        update_item = uv_group.items[uv_group.active_index]

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.active
        selected_vert = None
        for face in bm.faces:
            for loop in face.loops:
                if loop[uv_layer].select:
                    selected_vert = loop[uv_layer].uv
                    break

        if not selected_vert:
            return {"CANCELLED"}

        new_uv_coord = selected_vert
        uv_group = obj.mio3qs.uv_group

        update_item.uv_coord_u = new_uv_coord.x
        update_item
        bm.free()
        return {"FINISHED"}


class OBJECT_OT_mio3qs_update_by_cursor(Operator):
    bl_idname = "object.mio3qs_update_by_cursor"
    bl_label = "Update from 2D Cursor"
    bl_description = "Update UV Group coords from 2D Cursor"
    bl_options = {"REGISTER", "UNDO"}
    type: EnumProperty(items=[("CURSOR_U", "Cursor", ""), ("CURSOR_V", "Cursor", "")], options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.mode == "EDIT"

    def execute(self, context):
        obj = context.active_object
        uv_group = obj.mio3qs.uv_group
        active_index = uv_group.active_index
        active_group = uv_group.items[active_index]

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.active
        deform_layer = bm.verts.layers.deform.active

        offset_v = self.calc_offset_v(
            bm, uv_layer, deform_layer, obj.vertex_groups, active_group.name if active_index != 0 else None
        )

        cursor = context.space_data.cursor_location
        if self.type == "CURSOR_U":
            active_group.uv_coord_u = cursor.x
        elif self.type == "CURSOR_V":
            active_group.uv_offset_v = cursor.y - offset_v

        return {"FINISHED"}

    @staticmethod
    def calc_offset_v(bm, uv_layer, deform_layer, vertex_groups, group_name=None):
        uv_y_list = []
        for face in bm.faces:
            if group_name is None:
                if all(not any(v[deform_layer].get(vg.index, 0) > 0 for vg in vertex_groups) for v in face.verts):
                    uv_y_list.extend([loop[uv_layer].uv.y for loop in face.loops])
            else:
                vg = vertex_groups.get(group_name)
                if vg and all(v[deform_layer].get(vg.index, 0) > 0 for v in face.verts):
                    uv_y_list.extend([loop[uv_layer].uv.y for loop in face.loops])

        return sum(uv_y_list) / len(uv_y_list) if uv_y_list else 0.0


class OBJECT_OT_mio3qs_uv_group_remove(Operator):
    bl_idname = "object.mio3qs_uv_group_remove"
    bl_label = "Remove Item"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        uv_group = context.active_object.mio3qs.uv_group
        uv_group.items.remove(uv_group.active_index)
        uv_group.active_index = min(max(0, uv_group.active_index - 1), len(uv_group.items) - 1)
        return {"FINISHED"}


class OBJECT_OT_mio3qs_uv_group_move(Operator):
    bl_idname = "object.mio3qs_uv_group_move"
    bl_label = "Move Item"
    bl_options = {"REGISTER", "UNDO"}
    direction: EnumProperty(items=[("UP", "Up", ""), ("DOWN", "Down", "")], options={"HIDDEN"})

    def execute(self, context):
        obj = context.active_object
        uv_group = obj.mio3qs.uv_group
        index = uv_group.active_index
        if self.direction == "UP":
            if index > 1:
                uv_group.items.move(index, index - 1)
                uv_group.active_index -= 1
        elif self.direction == "DOWN":
            if index < len(uv_group.items) - 1 and index != 0:
                if index + 1 != 0:
                    uv_group.items.move(index, index + 1)
                    uv_group.active_index += 1
        return {"FINISHED"}


class OBJECT_OT_mio3qs_select_grpup_uvs(Operator):
    bl_idname = "object.mio3qs_select_grpup_uvs"
    bl_label = "Select Active"
    bl_options = {"REGISTER", "UNDO"}
    index: IntProperty(options={"HIDDEN"})

    def execute(self, context):
        obj = context.active_object
        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.active
        deform_layer = bm.verts.layers.deform.active
        uv_group = obj.mio3qs.uv_group

        if not uv_group.items:
            return {"CANCELLED"}

        for loop in (l for f in bm.faces for l in f.loops):
            loop[uv_layer].select = False

        active_uv_item = uv_group.items[self.index]
        active_vg = obj.vertex_groups.get(active_uv_item.name)
        active_vg_index = active_vg.index if active_vg else None

        other_vg_indices = {
            obj.vertex_groups[item.name].index
            for i, item in enumerate(uv_group.items)
            if i != self.index and item.name in obj.vertex_groups
        }

        for face in bm.faces:
            if active_vg_index is None:
                if any(not any(v[deform_layer].get(idx, 0) > 0 for idx in other_vg_indices) for v in face.verts):
                    for loop in face.loops:
                        loop[uv_layer].select = True
            else:
                if all(v[deform_layer].get(active_vg_index, 0) > 0 for v in face.verts):
                    for loop in face.loops:
                        loop[uv_layer].select = True

        bmesh.update_edit_mesh(obj.data)
        return {"FINISHED"}


class MIO3QS_PT_main(Panel):
    bl_label = "Mio3 Symmetry"
    bl_idname = "MIO3QS_PT_main"
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Mio3"

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.mode == "EDIT"

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        uv_group = obj.mio3qs.uv_group

        layout.label(text="UV Groups", icon="MOD_MIRROR")

        row = layout.row(align=True)
        row.prop_search(obj.mio3qs, "selected_vertex_group", obj, "vertex_groups", text="")
        row.scale_x = 0.6
        row.operator("object.mio3qs_uv_group_add", text="Add")

        if uv_group.items and len(uv_group.items) > uv_group.active_index:
            row = layout.row()
            row.template_list(
                "MIO3QS_UL_uv_group_list", "uv_group", uv_group, "items", uv_group, "active_index", rows=3
            )

            col = row.column(align=True)
            col.operator("object.mio3qs_uv_group_remove", icon="REMOVE", text="")
            col.separator()
            col.operator("object.mio3qs_uv_group_move", icon="TRIA_UP", text="").direction = "UP"
            col.operator("object.mio3qs_uv_group_move", icon="TRIA_DOWN", text="").direction = "DOWN"

            item = uv_group.items[uv_group.active_index]

            col = layout.column(align=True)
            split = col.split(factor=0.33)
            row = split.row(align=True)
            row.label(text="Mirror")
            row = split.row(align=True)
            row.prop(item, "uv_coord_u", text="")
            row.separator(factor=0.4)
            row.operator("object.mio3qs_update_by_cursor", icon="PIVOT_CURSOR", text="").type = "CURSOR_U"
            row.operator("object.mio3qs_update_by_vertex", icon="UV_VERTEXSEL", text="")

            split = col.split(factor=0.33)
            row = split.row(align=True)
            row.label(text="Offset")
            row = split.row(align=True)
            row.prop(item, "uv_offset_v", text="")
            row.separator(factor=0.4)
            row.operator("object.mio3qs_update_by_cursor", icon="PIVOT_CURSOR", text="").type = "CURSOR_V"
            row.label(text="", icon="BLANK1")

        row = layout.row(align=True)
        row.scale_x = 1.3

        if not uv_group.items or (uv_group.items and uv_group.items[0].name != "__General__"):
            row = layout.row(align=True)
            row.alert = True
            row.operator("object.mio3qs_update_prop", text="Init Default Group", icon="FILE_TICK")
        else:
            row.operator(
                "uv.mio3_symmetry_preview",
                text="Preview",
                icon="AREA_SWAP",
                depress=UV_OT_mio3_symmetry_preview.is_running(),
            )


class MIO3QS_UL_uv_group_list(UIList):
    bl_idname = "MIO3QS_UL_uv_group_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        if index == 0:
            row.label(text="Default", icon="DOT")
        else:
            row.prop(item, "name", icon="GROUP_VERTEX", text="", emboss=False)
        row.operator("object.mio3qs_select_grpup_uvs", text="", icon="RESTRICT_SELECT_OFF", emboss=False).index = index


def update_props(self, context):
    UV_OT_mio3_symmetry_preview.redraw(context)


class OBJECT_PG_mio3qs_uv_group_item(PropertyGroup):
    uv_coord_u: FloatProperty(name="UV X", min=0.0, max=1.0, default=0.5, step=0.5, precision=3, update=update_props)
    uv_offset_v: FloatProperty(name="Offset Y", min=-1.0, max=1.0, step=0.5, precision=3, update=update_props)


class OBJECT_PG_mio3qs_uv_group(PropertyGroup):
    # def callback_active_index(self, context):
    #     bpy.ops.object.mio3qs_select_grpup_uvs(index=self.active_index)

    items: CollectionProperty(name="UV Group Items", type=OBJECT_PG_mio3qs_uv_group_item)
    active_index: IntProperty()


class OBJECT_PG_mio3qs(PropertyGroup):
    uv_group: PointerProperty(name="UV Group", type=OBJECT_PG_mio3qs_uv_group)
    selected_vertex_group: StringProperty(name="Selected Vertex Group")


class OBJECT_OT_mio3qs_update_props(Operator):
    bl_idname = "object.mio3qs_update_prop"
    bl_label = "Update Props"
    bl_description = "Update Props by Old Data"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != "MESH":
            return {"CANCELLED"}

        current_list = []
        for item in obj.mio3qs.uv_group.items:
            if item.name == "__General__":
                continue
            current_list.append({"name": item.name, "uv_coord_u": item.uv_coord_u, "uv_offset_v": item.uv_offset_v})

        obj.mio3qs.uv_group.items.clear()
        new_item = obj.mio3qs.uv_group.items.add()
        new_item.name = "__General__"

        for item in current_list:
            new_item = obj.mio3qs.uv_group.items.add()
            new_item.name = item["name"]
            new_item.uv_coord_u = item["uv_coord_u"]
            new_item.uv_offset_v = item["uv_offset_v"]

        if "vglist" in obj["mio3qs"]:
            old_version_list = list(obj["mio3qs"]["vglist"].get("items", []))
            if old_version_list and not len(current_list):
                for item in old_version_list:
                    new_item = obj.mio3qs.uv_group.items.add()
                    new_item.name = item["vertex_group"]
                    new_item.uv_coord_u = item["uv_coord_u"]
                    new_item.uv_offset_v = item["uv_offset_v"]
            del obj["mio3qs"]["vglist"]
        return {"FINISHED"}


classes = [
    OBJECT_PG_mio3qs_uv_group_item,
    OBJECT_PG_mio3qs_uv_group,
    OBJECT_PG_mio3qs,
    OBJECT_OT_mio3qs_uv_group_add,
    OBJECT_OT_mio3qs_uv_group_remove,
    OBJECT_OT_mio3qs_uv_group_move,
    OBJECT_OT_mio3qs_update_by_cursor,
    OBJECT_OT_mio3qs_update_by_vertex,
    OBJECT_OT_mio3qs_select_grpup_uvs,
    OBJECT_OT_mio3qs_update_props,
    MIO3QS_UL_uv_group_list,
    MIO3QS_PT_main,
]


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Object.mio3qs = PointerProperty(type=OBJECT_PG_mio3qs)


def unregister():
    del bpy.types.Object.mio3qs
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
