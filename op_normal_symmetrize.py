import bpy
import bmesh
from mathutils import Vector, kdtree
from bpy.props import EnumProperty
from .utils import Mio3SYMOperator, find_x_mirror_verts


class MESH_OT_mio3_normal_symmetrize(Mio3SYMOperator):
    bl_idname = "mesh.mio3_normal_symmetrize"
    bl_label = "Normal Symmetrize"
    bl_description = "Mirroring custom normals to symmetric vertices"
    bl_options = {"REGISTER", "UNDO"}

    axis: EnumProperty(
        name="Axis",
        default="POSITIVE_X",
        items=[("NEGATIVE_X", "-X → +X", ""), ("POSITIVE_X", "-X ← +X", "")],
    )

    _center_threshold = 1e-5
    _threshold = 1e-4

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.mode == "EDIT"

    def execute(self, context):
        self.start_time()
        obj = context.active_object

        if not obj.data.has_custom_normals:
            self.report({"WARNING"}, "No custom normals")
            return {"CANCELLED"}

        bpy.ops.object.mode_set(mode="OBJECT")

        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()

        kd = kdtree.KDTree(len(bm.verts))
        for i, v in enumerate(bm.verts):
            kd.insert(v.co, i)
        kd.balance()

        normals = [list(l.normal) for l in obj.data.loops]

        get_mirror_point = lambda co: Vector((-co.x, co.y, co.z))
        get_mirror_normal = lambda n: [-n[0], n[1], n[2]]

        selected_verts = {v for v in bm.verts if v.select}
        selected_verts.update(find_x_mirror_verts(bm, selected_verts))

        if self.axis == "POSITIVE_X":
            is_source = lambda x: x > self._center_threshold
        else:
            is_source = lambda x: x < -self._center_threshold

        for v in selected_verts:
            if not is_source(v.co.x):
                continue

            mirror_co = get_mirror_point(v.co)
            _, idx, dist = kd.find(mirror_co)
            if dist > self._threshold:
                continue
            mirror_v = bm.verts[idx]

            for face in v.link_faces:
                mirror_center = get_mirror_point(face.calc_center_median())
                if not (target_face := self.find_mirror_face(mirror_v.link_faces, mirror_center)):
                    continue

                target_loops = {l.vert: l for l in target_face.loops}
                for loop in face.loops:
                    if loop.vert == v and mirror_v in target_loops:
                        sym_loop = target_loops[mirror_v]
                        normals[sym_loop.index] = get_mirror_normal(normals[loop.index])

        bm.free()
        obj.data.normals_split_custom_set([tuple(n) for n in normals])
        bpy.ops.object.mode_set(mode="EDIT")
        self.print_time()
        return {"FINISHED"}

    def find_mirror_face(self, mirror_faces, mirror_center):
        return min(mirror_faces, key=lambda f: (mirror_center - f.calc_center_median()).length_squared)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.row().prop(self, "axis", text="Axis", expand=True)


def menu(self, context):
    self.layout.separator()
    self.layout.operator("mesh.mio3_normal_symmetrize")


def register():
    bpy.utils.register_class(MESH_OT_mio3_normal_symmetrize)
    bpy.types.VIEW3D_MT_edit_mesh_normals.append(menu)


def unregister():
    bpy.utils.unregister_class(MESH_OT_mio3_normal_symmetrize)
    bpy.types.VIEW3D_MT_edit_mesh_normals.remove(menu)
