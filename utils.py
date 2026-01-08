import bpy
import time
from bpy.types import Operator
from mathutils import Vector, kdtree

DEBUG = False


def is_local(obj):
    return obj.library is None and obj.override_library is None


def is_local_obj(obj):
    return obj is not None and obj.library is None and obj.override_library is None


def is_exist_menu(cls, target_function):
    "メニューに存在するか確認する"
    draw_funcs = cls._dyn_ui_initialize()
    if target_function in draw_funcs:
        return True
    return False


def check_register(cls):
    is_exist = hasattr(bpy.types, cls.__name__)
    if not is_exist:
        try:
            bpy.utils.register_class(cls)
        except:
            pass


def check_unregister(cls):
    is_exist = hasattr(bpy.types, cls.__name__)
    if is_exist:
        try:
            bpy.utils.unregister_class(cls)
        except:
            pass


class Mio3SYMDebug:
    _start_time = 0

    def start_time(self):
        if DEBUG:
            self._start_time = time.time()

    def print_time(self):
        if DEBUG:
            print("Time: {}".format(time.time() - self._start_time))

    def print(self, msg):
        if DEBUG:
            print(str(msg))


class Mio3SYMOperator(Mio3SYMDebug, Operator):
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return cls.is_local_obj(obj)

    def invoke(self, context, event):
        obj = context.active_object
        if not self.is_local_obj(obj):
            self.report({"WARNING"}, "Library cannot be edited")
            return {"CANCELLED"}
        return self.execute(context)

    @staticmethod
    def is_local(obj):
        return obj.library is None and obj.override_library is None

    @staticmethod
    def is_local_obj(obj):
        return obj is not None and obj.library is None and obj.override_library is None


def find_x_mirror_verts(bm, selected_verts):
    kd = kdtree.KDTree(len(bm.verts))
    for i, v in enumerate(bm.verts):
        kd.insert(v.co, i)
    kd.balance()

    mirror_verts = set()
    for v in selected_verts:
        mirror_co = v.co.copy()
        mirror_co.x = -mirror_co.x
        _, index, dist = kd.find(mirror_co)
        if dist < 0.0001:
            mirror_vert = bm.verts[index]
            if mirror_vert not in selected_verts:
                mirror_verts.add(mirror_vert)

    return mirror_verts
