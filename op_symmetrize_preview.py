import bpy
import bmesh
import gpu
from gpu_extras.batch import batch_for_shader
from bpy.types import Operator, SpaceImageEditor
from .globals import NAME_ATTR_GROUP


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
        v2d = region.view2d

        all_tris = []
        for poly in cls._polygons:
            if len(poly) < 3:
                continue
            for i in range(1, len(poly) - 1):
                all_tris.extend([poly[0], poly[i], poly[i + 1]])

        verts = [v2d.view_to_region(v[0], v[1], clip=False) for v in all_tris]
        gpu.state.blend_set("ALPHA")
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        shader.bind()
        shader.uniform_float("color", (0.18, 0.55, 0.67, 0.1))
        batch = batch_for_shader(shader, "TRIS", {"pos": verts})
        batch.draw(shader)
        gpu.state.blend_set("NONE")

        viewport_vertices = [v2d.view_to_region(v[0], v[1], clip=False) for v in cls._vertices]
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "LINES", {"pos": viewport_vertices})
        shader.bind()
        shader.uniform_float("color", cls._color)
        batch.draw(shader)

        cx, _ = v2d.view_to_region(cls._active_u, 0.5, clip=False)
        line_pos = [(cx, 0), (cx, region.height)]
        line_shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        line_batch = batch_for_shader(line_shader, "LINES", {"pos": line_pos})
        line_shader.bind()
        line_shader.uniform_float("color", (0.4, 0.4, 0.4, 1))
        line_batch.draw(line_shader)

        cx, cy = v2d.view_to_region(cls._active_u, cls._active_v, clip=False)
        size = 20
        cross_lines = [(cx - size, cy), (cx + size, cy), (cx, cy - size), (cx, cy + size)]
        gpu.state.line_width_set(2)
        cross_shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        cross_batch = batch_for_shader(cross_shader, "LINES", {"pos": cross_lines})
        cross_shader.bind()
        cross_shader.uniform_float("color", (0.40, 0.80, 0.90, 1.0))  # (1.00, 0.73, 0.00, 1.0)
        cross_batch.draw(cross_shader)
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
        active_group = uv_group.items[active_index]
        cls._active_u = active_group.uv_coord_u
        cls._active_v = active_group.uv_offset_v

        sum_uv_y = 0.0
        cnt_uv_y = 0

        for f in bm.faces:
            uv_group_index = f[p_layer]
            u_co = uv_group.items[uv_group_index].uv_coord_u
            off_v = uv_group.items[uv_group_index].uv_offset_v

            # アクティブグループのYを集計
            if active_index == uv_group_index:
                face_uvs = []
                for loop in f.loops:
                    uv = cls.mirror_uv(loop[uv_layer].uv.copy(), u_co, off_v)
                    face_uvs.append(uv)
                    sum_uv_y += loop[uv_layer].uv.y
                    cnt_uv_y += 1
                if len(face_uvs) >= 3:
                    cls._polygons.append(face_uvs)
                for i in range(len(face_uvs)):
                    cls._vertices.extend((face_uvs[i], face_uvs[(i + 1) % len(face_uvs)]))
            else:
                poly_uvs = [cls.mirror_uv(loop[uv_layer].uv.copy(), u_co, off_v) for loop in f.loops]
                for i in range(len(poly_uvs)):
                    cls._vertices.extend((poly_uvs[i], poly_uvs[(i + 1) % len(poly_uvs)]))

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
