import bpy
import bmesh
from bpy.types import Operator, Panel, UIList, PropertyGroup
from bpy.props import (
    FloatProperty,
    IntProperty,
    StringProperty,
    EnumProperty,
    PointerProperty,
    CollectionProperty,
)
from .op_symmetrize_preview import UV_OT_mio3_symmetry_preview
from .globals import NAME_ATTR_GROUP


class Mio3qsUVGroupOperator:
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == "MESH" and obj.mode == "EDIT"

    def invoke(self, context, event):
        obj = context.active_object
        if not obj or obj.type != "MESH":
            self.report({"ERROR"}, "No active mesh object")
            return {"CANCELLED"}
        return self.execute(context)


class OBJECT_OT_mio3qs_uv_group_add(Mio3qsUVGroupOperator, Operator):
    bl_idname = "object.mio3qs_uv_group_add"
    bl_label = "Add Group"
    bl_description = "Create a new UV group"
    bl_options = {"REGISTER", "UNDO"}
    input_name: StringProperty(name="Name", options={"SKIP_SAVE", "HIDDEN"}, default="")

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == "MESH"

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = context.active_object

        if NAME_ATTR_GROUP not in obj.data.attributes:
            obj.data.attributes.new(name=NAME_ATTR_GROUP, type="INT", domain="FACE")

        uv_group = obj.mio3qs.uv_group
        if not uv_group.items:
            item = uv_group.items.add()
            item.name = "Default"

        new_group_name = "Group {}".format(len(uv_group.items)) if not self.input_name else self.input_name

        item = uv_group.items.add()
        item.name = new_group_name
        uv_group.active_index = len(uv_group.items) - 1
        obj.data.update()
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.ui_units_x = 12
        split = layout.split(factor=0.4)
        split.label(text="Group Name")
        split.prop(self, "input_name", text="")


class OBJECT_OT_mio3qs_uv_group_remove(Mio3qsUVGroupOperator, Operator):
    bl_idname = "object.mio3qs_uv_group_remove"
    bl_label = "Remove Group"
    bl_description = "Remove an active group"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        uv_group = obj.mio3qs.uv_group
        active_index = uv_group.active_index
        if len(uv_group.items) > 1 and active_index <= 0:
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        if (p_layer := bm.faces.layers.int.get(NAME_ATTR_GROUP)) is None:
            return {"CANCELLED"}

        for face in bm.faces:
            val = face[p_layer]
            if val == active_index:
                face[p_layer] = 0
            elif val > active_index:
                face[p_layer] -= 1

        uv_group.items.remove(active_index)
        if uv_group.items:
            uv_group.active_index = min(max(0, active_index - 1), len(uv_group.items) - 1)
        else:
            uv_group.active_index = 0
            prop = obj.data.attributes.get(NAME_ATTR_GROUP)
            if prop:
                obj.data.attributes.remove(prop)

        bmesh.update_edit_mesh(obj.data)
        UV_OT_mio3_symmetry_preview.redraw(context)
        return {"FINISHED"}


class OBJECT_OT_mio3qs_uv_group_move(Mio3qsUVGroupOperator, Operator):
    bl_idname = "object.mio3qs_uv_group_move"
    bl_label = "Move Item"
    bl_options = {"REGISTER", "UNDO"}
    direction: EnumProperty(items=[("UP", "Up", ""), ("DOWN", "Down", "")], options={"HIDDEN"})

    def execute(self, context):
        obj = context.active_object
        uv_group = obj.mio3qs.uv_group
        active_index = uv_group.active_index
        bm = bmesh.from_edit_mesh(obj.data)
        p_layer = bm.faces.layers.int.get(NAME_ATTR_GROUP)
        if p_layer is None or active_index == 0:
            return {"CANCELLED"}

        if self.direction == "UP" and active_index > 1:
            swap_a = active_index
            swap_b = active_index - 1
        elif self.direction == "DOWN" and (active_index < len(uv_group.items) - 1 and active_index != 0):
            swap_a = active_index
            swap_b = active_index + 1
        else:
            return {"CANCELLED"}

        for face in bm.faces:
            if face[p_layer] == swap_a:
                face[p_layer] = -1
            elif face[p_layer] == swap_b:
                face[p_layer] = swap_a
        for face in bm.faces:
            if face[p_layer] == -1:
                face[p_layer] = swap_b

        uv_group.items.move(swap_a, swap_b)
        uv_group.active_index = swap_b

        bmesh.update_edit_mesh(obj.data)
        return {"FINISHED"}


class OBJECT_OT_mio3qs_uv_group_assign(Mio3qsUVGroupOperator, Operator):
    bl_idname = "object.mio3qs_uv_group_assign"
    bl_label = "Assign Group"
    bl_description = "Assign from selected UVs"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.active
        if (p_layer := bm.faces.layers.int.get(NAME_ATTR_GROUP)) is None:
            p_layer = bm.faces.layers.int.new(NAME_ATTR_GROUP)

        active_uv_group_index = obj.mio3qs.uv_group.active_index
        for face in bm.faces:
            if all(loop[uv_layer].select for loop in face.loops):
                face[p_layer] = active_uv_group_index

        bmesh.update_edit_mesh(obj.data)
        UV_OT_mio3_symmetry_preview.redraw(context)
        return {"FINISHED"}


class OBJECT_OT_mio3qs_uv_group_unassign(Mio3qsUVGroupOperator, Operator):
    bl_idname = "object.mio3qs_uv_group_unassign"
    bl_label = "Remove Group"
    bl_description = "Remove from selected UVs"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.active
        if (p_layer := bm.faces.layers.int.get(NAME_ATTR_GROUP)) is None:
            p_layer = bm.faces.layers.int.new(NAME_ATTR_GROUP)

        for face in bm.faces:
            if all(loop[uv_layer].select for loop in face.loops):
                face[p_layer] = 0

        bmesh.update_edit_mesh(obj.data)
        UV_OT_mio3_symmetry_preview.redraw(context)
        return {"FINISHED"}


class OBJECT_OT_mio3qs_update_by_vertex(Mio3qsUVGroupOperator, Operator):
    bl_idname = "object.mio3qs_update_by_vertex"
    bl_label = "Update from UV"
    bl_description = "Update Group coords from Active UV"
    bl_options = {"REGISTER", "UNDO"}

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
            if selected_vert:
                break

        if selected_vert:
            update_item.uv_coord_u = selected_vert.x
        return {"FINISHED"}


class OBJECT_OT_mio3qs_update_by_cursor(Mio3qsUVGroupOperator, Operator):
    bl_idname = "object.mio3qs_update_by_cursor"
    bl_label = "Update from 2D Cursor"
    bl_description = "Update Group coords from 2D Cursor"
    bl_options = {"REGISTER", "UNDO"}
    type: EnumProperty(items=[("CURSOR_U", "Cursor", ""), ("CURSOR_V", "Cursor", "")], options={"HIDDEN"})

    def execute(self, context):
        obj = context.active_object
        uv_group = obj.mio3qs.uv_group
        active_index = uv_group.active_index

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.active
        p_layer = bm.faces.layers.int.get(NAME_ATTR_GROUP)
        offset_v = self.calc_offset_v(bm, uv_layer, p_layer, active_index)

        cursor = context.space_data.cursor_location
        if self.type == "CURSOR_U":
            uv_group.items[active_index].uv_coord_u = cursor.x
        elif self.type == "CURSOR_V":
            uv_group.items[active_index].uv_offset_v = cursor.y - offset_v

        return {"FINISHED"}

    @staticmethod
    def calc_offset_v(bm, uv_layer, p_layer, group_index):
        uv_y_list = []
        for face in bm.faces:
            if face[p_layer] == group_index:
                uv_y_list.extend([loop[uv_layer].uv.y for loop in face.loops])
        return sum(uv_y_list) / len(uv_y_list) if uv_y_list else 0.0


class OBJECT_OT_mio3qs_select_grpup_uvs(Mio3qsUVGroupOperator, Operator):
    bl_idname = "object.mio3qs_select_grpup_uvs"
    bl_label = "Select Active"
    bl_options = {"REGISTER", "UNDO"}
    index: IntProperty(options={"HIDDEN"})

    def execute(self, context):
        obj = context.active_object
        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.active
        p_layer = bm.faces.layers.int.get(NAME_ATTR_GROUP)
        uv_group = obj.mio3qs.uv_group
        if not uv_group.items:
            return {"CANCELLED"}

        for loop in (l for f in bm.faces for l in f.loops):
            loop[uv_layer].select = False

        for face in bm.faces:
            if face[p_layer] == self.index:
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
        return obj is not None and obj.mode == "EDIT" and obj.type == "MESH"

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        uv_group = obj.mio3qs.uv_group

        split = layout.split(factor=0.5, align=True)

        split.label(text="UV Group", icon="MOD_MIRROR")
        if NAME_ATTR_GROUP not in obj.data.attributes:
            row = split.row(align=True)
            row.alert = True
            row.operator("object.mio3qs_update_prop", text="Init Group")
        else:
            split.operator("uv.mio3_symmetry_preview", depress=UV_OT_mio3_symmetry_preview.is_running())

        row = layout.row()
        row.template_list("MIO3QS_UL_uv_groups", "uv_group", uv_group, "items", uv_group, "active_index", rows=3)

        col = row.column(align=True)
        col.operator("object.mio3qs_uv_group_add", icon="ADD", text="")
        col.operator("object.mio3qs_uv_group_remove", icon="REMOVE", text="")
        col.separator()
        col.operator("object.mio3qs_uv_group_move", icon="TRIA_UP", text="").direction = "UP"
        col.operator("object.mio3qs_uv_group_move", icon="TRIA_DOWN", text="").direction = "DOWN"

        if uv_group.items and len(uv_group.items) > uv_group.active_index:
            item = uv_group.items[uv_group.active_index]

            row = layout.row(align=True)
            row.operator("object.mio3qs_uv_group_assign", text="Assign", icon="PINNED")
            row.operator("object.mio3qs_uv_group_unassign", text="Remove", icon="UNPINNED")

            col = layout.column(align=True)
            split = col.split(factor=0.35)
            row = split.row(align=True)
            row.label(text="Mirror")
            row = split.row(align=True)
            row.prop(item, "uv_coord_u", text="")
            row.separator(factor=0.4)
            row.operator("object.mio3qs_update_by_cursor", icon="PIVOT_CURSOR", text="").type = "CURSOR_U"
            row.operator("object.mio3qs_update_by_vertex", icon="UV_VERTEXSEL", text="")

            split = col.split(factor=0.35)
            row = split.row(align=True)
            row.label(text="Offset")
            row = split.row(align=True)
            row.prop(item, "uv_offset_v", text="")
            row.separator(factor=0.4)
            row.operator("object.mio3qs_update_by_cursor", icon="PIVOT_CURSOR", text="").type = "CURSOR_V"
            row.label(text="", icon="BLANK1")


class MIO3QS_UL_uv_groups(UIList):
    bl_idname = "MIO3QS_UL_uv_groups"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        if index == 0:
            row.label(text="Default", icon="DOT")
        else:
            row.prop(item, "name", icon="KEYFRAME", text="", emboss=False)
        row.operator("object.mio3qs_select_grpup_uvs", text="", icon="RESTRICT_SELECT_OFF", emboss=False).index = index


def update_props(self, context):
    UV_OT_mio3_symmetry_preview.redraw(context)


class OBJECT_PG_mio3qs_uv_group_item(PropertyGroup):
    uv_coord_u: FloatProperty(name="UV X", min=0.0, max=1.0, default=0.5, step=0.5, precision=3, update=update_props)
    uv_offset_v: FloatProperty(name="Offset Y", min=-1.0, max=1.0, step=0.5, precision=3, update=update_props)


class OBJECT_PG_mio3qs_uv_group(PropertyGroup):
    items: CollectionProperty(name="UV Group Items", type=OBJECT_PG_mio3qs_uv_group_item)
    active_index: IntProperty(name="Active Index")


class OBJECT_PG_mio3qs(PropertyGroup):
    uv_group: PointerProperty(name="UV Group", type=OBJECT_PG_mio3qs_uv_group)


class OBJECT_OT_mio3qs_update_props(Mio3qsUVGroupOperator, Operator):
    bl_idname = "object.mio3qs_update_prop"
    bl_label = "Update Props"
    bl_description = "Update Props by Old Data"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != "MESH":
            return {"CANCELLED"}

        if NAME_ATTR_GROUP in obj.data.attributes:
            obj.data.attributes.remove(NAME_ATTR_GROUP)

        obj.data.attributes.new(name=NAME_ATTR_GROUP, type="INT", domain="FACE")

        current_list = []
        for item in obj.mio3qs.uv_group.items:
            if item.name == "Default":
                continue
            current_list.append({"name": item.name, "uv_coord_u": item.uv_coord_u, "uv_offset_v": item.uv_offset_v})

        obj.mio3qs.uv_group.items.clear()
        new_item = obj.mio3qs.uv_group.items.add()
        new_item.name = "Default"

        for item in current_list:
            new_item = obj.mio3qs.uv_group.items.add()
            new_item.name = item["name"]
            new_item.uv_coord_u = item["uv_coord_u"]
            new_item.uv_offset_v = item["uv_offset_v"]
        UV_OT_mio3_symmetry_preview.redraw(context)
        return {"FINISHED"}


classes = [
    OBJECT_PG_mio3qs_uv_group_item,
    OBJECT_PG_mio3qs_uv_group,
    OBJECT_PG_mio3qs,
    OBJECT_OT_mio3qs_uv_group_add,
    OBJECT_OT_mio3qs_uv_group_remove,
    OBJECT_OT_mio3qs_uv_group_move,
    OBJECT_OT_mio3qs_uv_group_assign,
    OBJECT_OT_mio3qs_uv_group_unassign,
    OBJECT_OT_mio3qs_update_by_cursor,
    OBJECT_OT_mio3qs_update_by_vertex,
    OBJECT_OT_mio3qs_select_grpup_uvs,
    OBJECT_OT_mio3qs_update_props,
    MIO3QS_UL_uv_groups,
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
