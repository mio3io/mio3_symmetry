import bpy
import bmesh
import gpu
from gpu_extras.batch import batch_for_shader
from bpy.types import Operator, SpaceImageEditor
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
        cross_shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        cross_batch = batch_for_shader(cross_shader, "LINES", {"pos": cross_lines})
        cross_shader.bind()
        cross_shader.uniform_float("color", (0.40, 0.80, 0.90, 1.0))  # (1.00, 0.73, 0.00, 1.0)
        cross_batch.draw(cross_shader)

    @classmethod
    def update_mesh(cls, context):
        # start_time = time.time()
        cls._vertices = []

        obj = context.active_object
        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.active
        deform_layer = bm.verts.layers.deform.active
        uv_group = obj.mio3qs.uv_group
        if not uv_group.items:
            return

        general_u = uv_group.items[0].uv_coord_u
        general_v = uv_group.items[0].uv_offset_v

        active_index = uv_group.active_index
        active_group = uv_group.items[active_index]
        cls._active_u = active_group.uv_coord_u
        cls._active_v = active_group.uv_offset_v
        is_general = active_index == 0

        uv_group_cache = []
        for item in uv_group.items:
            if vg := obj.vertex_groups.get(item.name):
                uv_group_cache.append((vg.index, item.uv_coord_u, item.uv_offset_v, item.name))

        sum_uv_y = 0.0
        cnt_uv_y = 0

        for f in bm.faces:
            u_co, off_v, match_name = general_u, general_v, None

            for idx, u, v, name in uv_group_cache:
                if all(vt[deform_layer].get(idx, 0) > 0 for vt in f.verts):
                    u_co, off_v, match_name = u, v, name
                    break

            # アクティブ or 一般グループのYを集計
            if (match_name == active_group.name) or (match_name is None and is_general):
                for loop in f.loops:
                    sum_uv_y += loop[uv_layer].uv.y
                    cnt_uv_y += 1

            poly_uvs = [cls.mirror_uv(loop[uv_layer].uv.copy(), u_co, off_v) for loop in f.loops]
            for i in range(len(poly_uvs)):
                cls._vertices.extend((poly_uvs[i], poly_uvs[(i + 1) % len(poly_uvs)]))

        if cnt_uv_y:
            cls._active_v += sum_uv_y / cnt_uv_y

        # print("time:", time.time() - start_time)

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
