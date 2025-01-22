import typing
import bpy
from bpy.types import Context, Operator, Panel, UILayout, UIList, PropertyGroup
from bpy.props import (
    FloatProperty,
    IntProperty,
    StringProperty,
    EnumProperty,
    PointerProperty,
    CollectionProperty,
)
import bmesh
from .op_symmetrize_preview import MIO3QS_OT_preview_uv


class MIO3QS_OT_uv_group_add(Operator):
    bl_idname = "mio3qs.group_add"
    bl_label = "Add Item"
    bl_description = "Add group Align to vertex or cursor position"
    bl_options = {"REGISTER", "UNDO"}

    type: EnumProperty(
        items=[
            ("ADD", "Add", ""),
            ("REPLACE", "Replace", "Align to vertex position"),
            ("CURSOR_U", "Cursor", "Align to cursor position"),
            ("CURSOR_V", "Cursor", "Align to cursor position"),
        ],
        options={"HIDDEN"},
    )

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

        if self.type == "ADD":
            selected_group_name = obj.mio3qs.selected_vertex_group
        else:
            uv_group = context.object.mio3qs.uv_group
            selected_group_name = uv_group.items[uv_group.active_index].name

        if not selected_group_name:
            self.report({"ERROR"}, "No vertex group selected")
            return {"CANCELLED"}

        selected_vg = obj.vertex_groups.get(selected_group_name)
        if not selected_vg:
            self.report({"ERROR"}, "Selected vertex group not found")
            return {"CANCELLED"}

        if self.type in {"ADD", "REPLACE", "CURSOR_V"}:
            # 選択中の頂点のUV座標を取得
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.verify()
            selected_vert = None
            for face in bm.faces:
                for loop in face.loops:
                    if loop[uv_layer].select:
                        selected_vert = loop[uv_layer].uv
                        break

            if not selected_vert:
                self.report({"ERROR"}, "No vertex selected")
                return {"CANCELLED"}

            new_uv_coord = selected_vert
            uv_group = obj.mio3qs.uv_group

        # 登録済みかチェック
        update_item = None
        for item in uv_group.items:
            if item.name == selected_group_name:
                update_item = item
                break

        if self.type == "ADD" and not update_item:
            new_item = uv_group.items.add()

            new_item.name = selected_group_name

            new_item.uv_coord_u = new_uv_coord.x
        elif self.type == "REPLACE":
            update_item.uv_coord_u = new_uv_coord.x
        elif self.type == "CURSOR_U":
            update_item.uv_coord_u = context.space_data.cursor_location[0]
        elif self.type == "CURSOR_V":
            update_item.uv_offset_v = context.space_data.cursor_location[1] - new_uv_coord.y

        return {"FINISHED"}


class MIO3QS_OT_uv_group_remove(Operator):
    bl_idname = "mio3qs.group_remove"
    bl_label = "Remove Item"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        uv_group = context.object.mio3qs.uv_group
        uv_group.items.remove(uv_group.active_index)
        uv_group.active_index = min(max(0, uv_group.active_index - 1), len(uv_group.items) - 1)
        return {"FINISHED"}


class MIO3QS_OT_uv_group_move(Operator):
    bl_idname = "mio3qs.group_move"
    bl_label = "Move Item"
    bl_options = {"REGISTER", "UNDO"}

    direction: EnumProperty(
        items=[
            ("UP", "Up", ""),
            ("DOWN", "Down", ""),
        ]
    )

    def execute(self, context):
        obj = context.active_object
        uv_group = obj.mio3qs.uv_group
        index = uv_group.active_index

        if self.direction == "UP" and index > 0:
            uv_group.items.move(index, index - 1)
            uv_group.active_index -= 1
        elif self.direction == "DOWN" and index < len(uv_group.items) - 1:
            uv_group.items.move(index, index + 1)
            uv_group.active_index += 1

        return {"FINISHED"}


class MIO3QS_PT_main(Panel):
    bl_label = "Mio3 Symmetrize"
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
        row.operator("mio3qs.group_add", text="Add").type = "ADD"

        if uv_group.items and len(uv_group.items) > uv_group.active_index:

            row = layout.row()
            row.template_list(
                "MIO3QS_UL_uv_group_list",
                "uv_group",
                uv_group,
                "items",
                uv_group,
                "active_index",
                rows=3,
            )

            col = row.column(align=True)
            col.operator("mio3qs.group_remove", icon="REMOVE", text="")
            col.separator()
            col.operator("mio3qs.group_move", icon="TRIA_UP", text="").direction = "UP"
            col.operator("mio3qs.group_move", icon="TRIA_DOWN", text="").direction = "DOWN"

            item = uv_group.items[uv_group.active_index]

            split = layout.split(factor=0.3)
            row = split.row(align=True)
            row.label(text="Mirror X")
            row = split.row(align=True)
            row.prop(item, "uv_coord_u", text="")
            row.separator()

            row.operator("mio3qs.group_add", icon="PIVOT_CURSOR", text="").type = "CURSOR_U"
            row.operator("mio3qs.group_add", icon="UV_VERTEXSEL", text="").type = "REPLACE"

            split = layout.split(factor=0.3)
            row = split.row(align=True)
            row.label(text="Offset")
            row = split.row(align=True)
            row.prop(item, "uv_offset_v", text="")
            row.separator()
            row.operator("mio3qs.group_add", icon="PIVOT_CURSOR", text="").type = "CURSOR_V"
            row.label(text="", icon="BLANK1")

        row = layout.row(align=True)
        row.scale_x = 1.3
        row.operator("mio3qs.preview_uv", text="Preview UV", icon="AREA_SWAP", depress=MIO3QS_OT_preview_uv.is_running())
        row.operator("mio3qs.preview_uv_refresh", icon="FILE_REFRESH", text="")



class MIO3QS_UL_uv_group_list(UIList):
    bl_idname = "MIO3QS_UL_uv_group_list"
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "name", icon="GROUP_VERTEX", text="", emboss=False)


def update_props(self, context):
    MIO3QS_OT_preview_uv.redraw(context)


class MIO3QS_PG_uv_group_item(PropertyGroup):
    uv_coord_u: FloatProperty(name="UV X", min=0.0, max=1.0, step=0.5, precision=3, update=update_props)
    uv_offset_v: FloatProperty(name="Offset Y", min=-1.0, max=1.0, step=0.5, precision=3, update=update_props)


class MIO3QS_PG_uv_group(PropertyGroup):
    items: CollectionProperty(name="UV Group Items", type=MIO3QS_PG_uv_group_item)
    active_index: IntProperty()
    # general: PointerProperty(name="General", type=MIO3QS_PG_uv_group_item)

class MIO3QS_PG_main(PropertyGroup):
    uv_group: PointerProperty(name="UV Group", type=MIO3QS_PG_uv_group)
    selected_vertex_group: StringProperty(name="Selected Vertex Group")


classes = [
    MIO3QS_PG_uv_group_item,
    MIO3QS_PG_uv_group,
    MIO3QS_PG_main,
    MIO3QS_OT_uv_group_add,
    MIO3QS_OT_uv_group_remove,
    MIO3QS_OT_uv_group_move,
    MIO3QS_UL_uv_group_list,
    MIO3QS_PT_main,
]


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Object.mio3qs = PointerProperty(type=MIO3QS_PG_main)


def unregister():
    del bpy.types.Object.mio3qs
    for c in classes:
        bpy.utils.unregister_class(c)
