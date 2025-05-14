import bpy
from bpy.types import Operator
from bpy.props import EnumProperty, BoolProperty
import bmesh
import time
import numpy as np

TMP_VG_NAME = "Mio3qsTempVg"
TMP_DATA_TRANSFER_NAME = "Mio3qsTempDataTransfer"


class MIO3_OT_quick_symmetrize(Operator):
    bl_idname = "object.mio3_symmetry"
    bl_label = "Symmetrize & Recovery"
    bl_description = "Symmetrize meshes, shape keys, vertex groups, UVs, and normals"
    bl_options = {"REGISTER", "UNDO"}

    mode: EnumProperty(
        name="Mode",
        items=[("+X", "+X → -X", ""), ("-X", "-X → +X", "")],
    )
    facial: BoolProperty(name="UnSymmetrize L/R Facial ShapeKeys", default=False)
    normal: BoolProperty(name="Normal", default=True)
    uvmap: BoolProperty(name="UVMap", default=False)
    center: BoolProperty(name="Origin to Center", default=True)
    remove_mirror_mod: BoolProperty(name="Remove Mirror Modifier", default=True)
    suffix_pairs = [("_L", "_R"), (".L", ".R"), ("-L", "-R"), ("Left", "Right")]
    main_verts = []
    sub_verts = []
    replace_names = {
        "ウィンク": "MMD_Wink_R",
        "ウィンク右": "MMD_Wink_L",
        "ウィンク２": "MMD_Wink2_R",
        "ｳｨﾝｸ２右": "MMD_Wink2_L",
    }

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.mode == "OBJECT"

    def invoke(self, context, event):
        obj = context.active_object
        if obj.type != "MESH":
            self.report({"ERROR"}, "Object is not a mesh")
            return {"CANCELLED"}

        # bpy.ops.ed.undo_push()  # mesh.symmetrizeがReDoできない措置
        return self.execute(context)

    def execute(self, context):
        start_time = time.time()
        obj = context.active_object

        original_cursor_location = tuple(context.scene.cursor.location)
        original_location = obj.location

        for o in context.scene.objects:
            if o != obj:
                o.select_set(False)

        # 状態を保存
        if self.center and obj.location.x != 0:
            context.scene.cursor.location = (0,) + original_location[1:]
            bpy.ops.object.origin_set(type="ORIGIN_CURSOR", center="MEDIAN")
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        active_shape_key_index = obj.active_shape_key_index

        for mod in obj.modifiers:
            if self.remove_mirror_mod and mod.type == "MIRROR":
                obj.modifiers.remove(mod)

        vart_count_1 = len(obj.data.vertices)

        orig_shapekey_weights = []
        if obj.data.shape_keys:
            for key in obj.data.shape_keys.key_blocks:
                orig_shapekey_weights.append(key.value)
                key.value = 0
            obj.active_shape_key_index = 0

        orig_modifier_states = []
        for mod in obj.modifiers:
            orig_modifier_states.append(mod.show_viewport)
            mod.show_viewport = False

        orgcopy = obj.copy()
        orgcopy.data = obj.data.copy()
        context.collection.objects.link(orgcopy)

        # 対称化
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.symmetrize(
            bm,
            input=bm.verts[:] + bm.edges[:] + bm.faces[:],
            direction="X" if self.mode == "+X" else "-X",
            use_shapekey=True,
            dist=0.00001,
        )

        for elem in bm.verts[:] + bm.edges[:] + bm.faces[:]:
            elem.hide_set(False)
            elem.select_set(False)

        select_condition = lambda x: x <= 0 if self.mode == "+X" else x >= 0
        for v in bm.verts:
            if select_condition(v.co.x):
                v.select = True

        if self.uvmap:
            self.symm_uv(obj, bm)

        self.symm_vgroups(obj, bm)

        if self.normal and obj.data.has_custom_normals:
            vg = self.create_temp_vgroup(obj, bm)

        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()

        if self.normal and obj.data.has_custom_normals and vg:
            self.symm_normal(obj, orgcopy, vg.name)

        if self.facial:
            self.unsymm_facial(obj)

        # 状態を戻す
        if obj.data.shape_keys:
            for i, weight in enumerate(orig_shapekey_weights):
                obj.data.shape_keys.key_blocks[i].value = weight
        for i, state in enumerate(orig_modifier_states):
            obj.modifiers[i].show_viewport = state

        if original_cursor_location is not None:
            context.scene.cursor.location = original_cursor_location

        obj.active_shape_key_index = active_shape_key_index

        if TMP_VG_NAME in obj.vertex_groups:
            obj.vertex_groups.remove(obj.vertex_groups[TMP_VG_NAME])

        copy_mesh = orgcopy.data
        bpy.data.objects.remove(orgcopy, do_unlink=True)
        bpy.data.meshes.remove(copy_mesh, do_unlink=True)

        vart_count_2 = len(obj.data.vertices)
        stime = time.time() - start_time
        self.report({"INFO"}, f"Mio3 Symmetry Vertex Count {vart_count_1} → {vart_count_2}  Time: {stime:.4f}")  # fmt:skip
        return {"FINISHED"}

    def create_temp_vgroup(self, obj, bm):
        deform_layer = bm.verts.layers.deform.verify()

        if TMP_VG_NAME in obj.vertex_groups:
            vg = obj.vertex_groups[TMP_VG_NAME]
            obj.vertex_groups.remove(vg)

        self.vg = obj.vertex_groups.new(name=TMP_VG_NAME)

        for v in bm.verts:
            if v.select:
                if v.co.x != 0.0:
                    v[deform_layer][self.vg.index] = 1.0

        bm.to_mesh(obj.data)
        obj.data.update()
        return self.vg

    # UV
    def symm_uv(self, obj, bm):
        deform_layer = bm.verts.layers.deform.active
        uv_layer = bm.loops.layers.uv.active
        if not uv_layer:
            return

        def mirror_uv(faces, u_co, offset_v):
            for face in faces:
                for loop in face.loops:
                    uv = loop[uv_layer]
                    if abs(uv.uv.x - u_co) < 0.0001:
                        uv.uv.x = u_co
                    uv.uv.x = u_co + (u_co - uv.uv.x)
                    if offset_v:
                        uv.uv.y = uv.uv.y + offset_v

        face_groups = {}
        processed_faces = set()
        select_condition = lambda x: x < 0 if self.mode == "+X" else x > 0
        for item in obj.mio3qs.uv_group.items:
            vg = obj.vertex_groups.get(item.name)
            if vg:
                face_groups[item.name] = set()
                for f in bm.faces:
                    if f not in processed_faces:
                        # グループに登録されている
                        try:
                            if all(vg.index in v[deform_layer] for v in f.verts):
                                # 片側の面
                                if any(select_condition(v.co.x) for v in f.verts):
                                    face_groups[item.name].add(f)
                                processed_faces.add(f)
                        except:
                            pass

        # グループごとに処理
        for item in obj.mio3qs.uv_group.items:
            if item.name in face_groups:
                mirror_uv(face_groups[item.name], item.uv_coord_u, item.uv_offset_v)

        # General
        general_faces = set(bm.faces) - processed_faces
        selected_general_faces = [f for f in general_faces if any(select_condition(v.co.x) for v in f.verts)]
        mirror_uv(selected_general_faces, 0.5, 0)

    # 頂点ウェイト
    def symm_vgroups(self, obj, bm):
        deform_layer = bm.verts.layers.deform.verify()
        symmetric_groups = self.symmetric_group_mapping(obj)
        select_condition = lambda x: x <= 0 if self.mode == "+X" else x >= 0

        for v in bm.verts:
            if not v.select:
                continue

            if not select_condition(v.co.x):
                continue

            weight_dict = v[deform_layer]
            if not weight_dict:
                continue

            temp_weights = {}
            for vg_id, weight in weight_dict.items():
                if vg_id in symmetric_groups:
                    symmetric_id = symmetric_groups[vg_id]
                    if symmetric_id != vg_id:
                        temp_weights[vg_id] = weight
                        weight_dict[vg_id] = weight_dict.get(symmetric_id, 0.0)

            for vg_id, weight in temp_weights.items():
                symmetric_id = symmetric_groups[vg_id]
                weight_dict[symmetric_id] = weight
                if not weight_dict[vg_id]:
                    del weight_dict[vg_id]

    # 法線
    def symm_normal(self, obj, orgcopy, vg_name):
        orgcopy.scale[0] *= -1
        try:
            transfer_modifier = obj.modifiers.new(name=TMP_DATA_TRANSFER_NAME, type="DATA_TRANSFER")
            transfer_modifier.object = orgcopy
            transfer_modifier.vertex_group = vg_name
            transfer_modifier.use_max_distance = True
            transfer_modifier.max_distance = 0.0001
            transfer_modifier.data_types_loops = {"CUSTOM_NORMAL"}
            with bpy.context.temp_override(active_object=obj):
                bpy.ops.object.modifier_apply(modifier=transfer_modifier.name)

        finally:
            orgcopy.scale[0] *= -1

    # 表情の非対称化
    def unsymm_facial(self, obj):
        suffix_pairs = self.suffix_pairs
        if not obj.data.shape_keys:
            return

        key_blocks = obj.data.shape_keys.key_blocks
        if not key_blocks:
            return

        if self.mode == "+X":
            pairs = [(r, l) for l, r in suffix_pairs]
        else:
            pairs = suffix_pairs

        self.rename_shape_keys(obj, self.replace_names)

        basis = obj.data.shape_keys.reference_key
        basis_coords = np.zeros(len(basis.data) * 3, dtype=np.float32)
        basis.data.foreach_get("co", basis_coords)

        for i, target_kb in enumerate(key_blocks):
            for target_suffix, source_suffix in pairs:
                if target_kb.name.endswith(target_suffix):
                    source_name = target_kb.name[: -len(target_suffix)] + source_suffix
                    if source_name in key_blocks:

                        vertex_mask = np.array([v.select for v in obj.data.vertices], dtype=bool)
                        mask_indices = np.where(vertex_mask)[0]

                        if len(mask_indices) == 0:
                            continue

                        source_kb = key_blocks[source_name]

                        source_coords = np.zeros(len(source_kb.data) * 3, dtype=np.float32)
                        source_kb.data.foreach_get("co", source_coords)

                        target_coords = np.zeros(len(target_kb.data) * 3, dtype=np.float32)
                        target_kb.data.foreach_get("co", target_coords)

                        for idx in mask_indices:
                            coord_idx = idx * 3
                            target_coords[coord_idx : coord_idx + 3] = source_coords[
                                coord_idx : coord_idx + 3
                            ]
                        target_kb.data.foreach_set("co", target_coords)

                        for idx in mask_indices:
                            coord_idx = idx * 3
                            source_coords[coord_idx : coord_idx + 3] = basis_coords[coord_idx : coord_idx + 3]
                        source_kb.data.foreach_set("co", source_coords)
                        break

        reverse_names = {v: k for k, v in self.replace_names.items()}
        self.rename_shape_keys(obj, reverse_names)

    def rename_shape_keys(self, obj, dicts):
        if obj.data.shape_keys:
            for key in obj.data.shape_keys.key_blocks:
                if key.name in dicts:
                    key.name = dicts[key.name]

    def symmetric_group_mapping(self, obj):
        symmetric_groups = {}
        name_to_group = {vg.name: vg for vg in obj.vertex_groups}
        processed_vgroup = set()

        for vgroup_name in obj.vertex_groups.keys():
            if vgroup_name in processed_vgroup:
                continue

            base_name = vgroup_name
            extra_suffix = ""
            if "." in vgroup_name:
                split_name = vgroup_name.rsplit(".", 1)
                if split_name[1] not in {"L", "R"}:
                    base_name = split_name[0]
                    extra_suffix = ".{}".format(split_name[1])

            current_suffix = None
            for l_suffix, r_suffix in self.suffix_pairs:
                if base_name.endswith(l_suffix if self.mode == "+X" else r_suffix):
                    current_suffix = l_suffix if self.mode == "+X" else r_suffix
                    opposite_suffix = r_suffix if self.mode == "+X" else l_suffix
                    break

            if current_suffix:
                name_without_suffix = base_name[: -len(current_suffix)]
                opposite_name = "{}{}{}".format(name_without_suffix, opposite_suffix, extra_suffix)

                if opposite_name in name_to_group:
                    current_group = name_to_group[vgroup_name]
                    opposite_group = name_to_group[opposite_name]
                    symmetric_groups[current_group.index] = opposite_group.index
                    symmetric_groups[opposite_group.index] = current_group.index
                    processed_vgroup.add(vgroup_name)
                    processed_vgroup.add(opposite_name)
            else:
                current_group = name_to_group[vgroup_name]
                symmetric_groups[current_group.index] = current_group.index

        return symmetric_groups

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "mode")
        layout.prop(self, "normal")
        layout.prop(self, "uvmap")
        layout.prop(self, "center")
        layout.prop(self, "remove_mirror_mod")
        layout.prop(self, "facial")


classes = [MIO3_OT_quick_symmetrize]


def menu_transform(self, context):
    self.layout.separator()
    self.layout.operator(MIO3_OT_quick_symmetrize.bl_idname)


def register():
    bpy.types.VIEW3D_MT_object.append(menu_transform)
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    bpy.types.VIEW3D_MT_object.remove(menu_transform)
