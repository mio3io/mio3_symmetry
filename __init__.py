import bpy
from . import op_symmetrize
from . import op_symmetrize_group
from . import op_symmetrize_preview

bl_info = {
    "name": "Mio3 Symmetry",
    "author": "mio",
    "version": (0, 9, 3),
    "blender": (4, 2, 0),
    "location": "View3D > Object",
    "description": "Symmetrize meshes, shape keys, vertex groups, UVs, and normals while maintaining multi-resolution",
    "category": "Object",
}


translation_dict = {
    "ja_JP": {
        ("Operator", "Symmetrize & Recovery"): "対称化＆リカバリー",
        ("*", "Symmetrize meshes, shape keys, vertex groups, UVs, and normals"): "メッシュ・シェイプキー・頂点グループ・UV・法線を対称化",
        ("*", "UnSymmetrize L/R Facial ShapeKeys"): "L/Rの表情シェイプキーを非対称化",
        ("*", "Remove Mirror Modifier"): "ミラーモディファイアがあれば削除",
        ("*", "Origin to Center"): "原点を基準に対称化",
        ("*", "Object is not a mesh"): "オブジェクトがメッシュではありません",
        ("*", "Symmetrize meshes, shape keys, vertex groups, UVs, and normals while maintaining multi-resolution"): "マルチレゾを維持してメッシュ・シェイプキー・頂点グループ・UV・法線を対称化",
        ("*", "Add a weighted vertex group"): "ウェイトを設定した頂点グループを追加する",

        ("Operator", "Update from 2D Cursor"): "2Dカーソルからグループを更新",
        ("*", "Update UV Group coords from 2D Cursor"): "2DカーソルからUVグループの座標を更新します",
        ("Operator", "Update from UV"): "UVからグループを更新",
        ("*", "Update UV Group coords from Active UV"): "アクティブなUVからUVグループの座標を更新します",

        ("*", ""): "",

    }  # fmt: skip
}


modules = [
    op_symmetrize,
    op_symmetrize_preview,
    op_symmetrize_group,
]


def register():
    for module in modules:
        module.register()
    bpy.app.translations.register(__name__, translation_dict)


def unregister():
    bpy.app.translations.unregister(__name__)
    for module in reversed(modules):
        module.unregister()


if __name__ == "__main__":
    register()
