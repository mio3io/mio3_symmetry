import bpy
import bmesh
import gpu
from gpu_extras.batch import batch_for_shader
from bpy.types import Operator, SpaceImageEditor
from .globals import NAME_ATTR_GROUP
import time

msgbus_owner = object()


def reload_view(context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "IMAGE_EDITOR":
                area.tag_redraw()


class UV_OT_mio3_symmetry_preview(Operator):
    bl_idname = "uv.mio3_symmetry_preview"
    bl_label = "Preview UV"
    bl_description = "Preview UV"
    bl_options = {"REGISTER", "UNDO"}

    _handle = None
    _color = (0.5, 0.5, 0.5, 1)
    _vertices = []
    _polygons = []
    _active_u = 0.5
    _active_v = 0
    _time = 0.0

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.mode == "EDIT"

    @classmethod
    def remove_handler(cls):
        if cls.is_running():
            SpaceImageEditor.draw_handler_remove(cls._handle, "WINDOW")
            cls._handle = None
        bpy.msgbus.clear_by_owner(msgbus_owner)
        reload_view(bpy.context)

    @classmethod
    def is_running(cls):
        return cls._handle is not None

    @classmethod
    def redraw(cls, context):
        if cls.is_running():
            cls.update_mesh(context)
            reload_view(context)

    def invoke(self, context, event):
        cls = self.__class__
        is_running = cls.is_running()
        cls.remove_handler()
        if is_running:
            return {"FINISHED"}

        if not context.active_object.data.uv_layers:
            self.report({"WARNING"}, "No UV layer found")
            return {"CANCELLED"}

        cls._handle = SpaceImageEditor.draw_handler_add(self.draw_2d, ((cls, context)), "WINDOW", "POST_PIXEL")

        def callback():
            cls.remove_handler()

        bpy.msgbus.subscribe_rna(key=(bpy.types.Object, "mode"), owner=msgbus_owner, args=(), notify=callback)

        cls.redraw(context)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        cls = self.__class__
        if not cls.is_running():
            return {"FINISHED"}
        if event.type == "LEFTMOUSE" and event.value == "RELEASE":
            self.update_mesh(context)
            reload_view(context)
        return {"PASS_THROUGH"}

    @staticmethod
    def draw_2d(cls, context):
        region = context.region
        view_to_region = region.view2d.view_to_region

        all_tris = []
        for poly in cls._polygons:
            if len(poly) < 3:
                continue
            for i in range(1, len(poly) - 1):
                all_tris.extend([poly[0], poly[i], poly[i + 1]])

        verts = [view_to_region(v[0], v[1], clip=False) for v in all_tris]
        gpu.state.blend_set("ALPHA")
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        shader.bind()
        shader.uniform_float("color", (0.18, 0.55, 0.67, 0.1))
        batch = batch_for_shader(shader, "TRIS", {"pos": verts})
        batch.draw(shader)
        gpu.state.blend_set("NONE")

        viewport_vertices = [view_to_region(v[0], v[1], clip=False) for v in cls._vertices]
        batch = batch_for_shader(shader, "LINES", {"pos": viewport_vertices})
        shader.bind()
        shader.uniform_float("color", cls._color)
        batch.draw(shader)

        cx, _ = view_to_region(cls._active_u, 0.5, clip=False)
        line_pos = [(cx, 0), (cx, region.height)]
        line_batch = batch_for_shader(shader, "LINES", {"pos": line_pos})
        shader.bind()
        shader.uniform_float("color", (0.4, 0.4, 0.4, 1))
        line_batch.draw(shader)

        cx, cy = view_to_region(cls._active_u, cls._active_v, clip=False)
        size = 20
        cross_lines = [(cx - size, cy), (cx + size, cy), (cx, cy - size), (cx, cy + size)]
        gpu.state.line_width_set(2)
        cross_batch = batch_for_shader(shader, "LINES", {"pos": cross_lines})
        shader.bind()
        shader.uniform_float("color", (0.40, 0.80, 0.90, 1.0))  # (1.00, 0.73, 0.00, 1.0)
        cross_batch.draw(shader)
        gpu.state.line_width_set(1)

    @classmethod
    def update_mesh(cls, context):
        cls._vertices = []
        cls._polygons = []

        obj = context.active_object
        bm = bmesh.from_edit_mesh(obj.data)

        uv_layer = bm.loops.layers.uv.active
        p_layer = bm.faces.layers.int.get(NAME_ATTR_GROUP)

        uv_group = obj.mio3qs.uv_group
        if not uv_group.items:
            return

        active_index = uv_group.active_index
        active_item = uv_group.items[active_index]
        vertices_extend = cls._vertices.extend
        polygons_append = cls._polygons.append

        cls._active_u = active_item.uv_coord_u
        cls._active_v = active_item.uv_offset_v

        sum_uv_y = 0.0
        cnt_uv_y = 0

        for face in bm.faces:
            g_idx = face[p_layer]
            g_item = uv_group.items[g_idx]
            u_co = g_item.uv_coord_u
            off_v = g_item.uv_offset_v

            loops_uv = [cls.mirror_uv(l[uv_layer].uv.copy(), u_co, off_v) for l in face.loops]

            if g_idx == active_index:
                if len(loops_uv) >= 3:
                    polygons_append(loops_uv)
                for i in range(len(loops_uv)):
                    vertices_extend((loops_uv[i], loops_uv[(i + 1) % len(loops_uv)]))

                for l in face.loops:
                    sum_uv_y += l[uv_layer].uv.y
                cnt_uv_y += len(face.loops)
            else:
                for i in range(len(loops_uv)):
                    vertices_extend((loops_uv[i], loops_uv[(i + 1) % len(loops_uv)]))

        if cnt_uv_y:
            cls._active_v += sum_uv_y / cnt_uv_y

    @staticmethod
    def mirror_uv(uv, u_co, offset_v):
        dx = uv.x - u_co
        uv.x = u_co if abs(dx) < 0.0001 else u_co - dx
        if offset_v:
            uv.y += offset_v
        return uv

    @classmethod
    def unregister(cls):
        cls.remove_handler()


@bpy.app.handlers.persistent
def load_handler(dummy):
    UV_OT_mio3_symmetry_preview.remove_handler()


def register():
    bpy.utils.register_class(UV_OT_mio3_symmetry_preview)
    bpy.app.handlers.load_post.append(load_handler)


def unregister():
    bpy.app.handlers.load_post.remove(load_handler)
    bpy.utils.unregister_class(UV_OT_mio3_symmetry_preview)
