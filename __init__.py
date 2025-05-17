import bpy
from . import op_symmetrize
from . import op_symmetrize_group
from . import op_symmetrize_preview

translation_dict = {
    "ja_JP": {
        ("Operator", "Symmetrize & Recovery"): "対称化＆リカバリー",
        ("*", "Symmetrize meshes, shape keys, vertex groups, UVs, and normals"): "メッシュ・シェイプキー・頂点グループ・UV・法線を対称化",
        ("*", "UnSymmetrize L/R Facial ShapeKeys"): "L/Rの表情シェイプキーを非対称化",
        ("*", "Remove Mirror Modifier"): "ミラーモディファイアがあれば削除",
        ("*", "Origin to Center"): "原点を基準に対称化",
        ("*", "Object is not a mesh"): "オブジェクトがメッシュではありません",
        ("*", "Symmetrize meshes, shape keys, vertex groups, UVs, and normals while maintaining multi-resolution"): "マルチレゾを維持してメッシュ・シェイプキー・頂点グループ・UV・法線を対称化",

        ("Operator", "Add Group"): "グループを追加",
        ("*", "Create a new UV group"): "新しいUVグループを作成する",
        ("Operator", "Remove Group"): "グループを削除",
        ("*", "Remove an active group"): "アクティブなグループを削除する",
        ("Operator", "Update from 2D Cursor"): "2Dカーソルからグループを更新",
        ("*", "Update Group coords from 2D Cursor"): "2Dカーソルからグループの座標を更新します",
        ("Operator", "Update from UV"): "UVからグループを更新",
        ("*", "Update Group coords from Active UV"): "アクティブなUVからグループの座標を更新します",

        ("Operator", "Un Assign"): "割り当て解除",
        ("Operator", "Preview"): "プレビュー",

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
