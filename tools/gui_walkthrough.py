"""Прохід уроку в справжньому вікні Blender зі знімками екрана після кожного кроку.

Запуск (Linux, Xvfb):
  EDU_SHOTS=out/ EDU_WALK=lesson1 blender --factory-startup -p 0 0 1400 860 --python tools/gui_walkthrough.py
"""

import math
import os
import sys

import bpy

bpy.context.preferences.view.show_splash = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import edu_lessons  # noqa: E402
from edu_lessons import checks, course  # noqa: E402

OUT = os.environ.get("EDU_SHOTS", "/tmp/edu_shots")
LESSON = os.environ.get("EDU_WALK", "lesson1")
os.makedirs(OUT, exist_ok=True)
os.chdir(OUT)  # експорт без збереженого .blend шукається в робочій теці


def view3d():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == 'VIEW_3D')
    region = next(r for r in area.regions if r.type == 'WINDOW')
    return win, area, region


def in_view(func):
    win, area, region = view3d()
    with bpy.context.temp_override(window=win, area=area, region=region):
        func()


def shot(name):
    win = bpy.context.window_manager.windows[0]
    path = os.path.join(OUT, name + ".png")
    with bpy.context.temp_override(window=win, area=win.screen.areas[0]):
        bpy.ops.screen.screenshot(filepath=path)
    print("EDU_SHOT", path, "step", course.progress())


def select_only(kind):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj = checks.first_object(kind)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def rotate_view():
    _, area, _ = view3d()
    rv3d = area.spaces.active.region_3d
    rv3d.view_rotation.rotate(__import__("mathutils").Euler((0, 0, math.radians(60))))


ACTIONS = {
    "lesson1": [
        lambda: select_only("cube"),
        rotate_view,
        lambda: in_view(lambda: bpy.ops.object.delete()),
        lambda: in_view(lambda: bpy.ops.mesh.primitive_cylinder_add()),
        lambda: in_view(lambda: bpy.ops.mesh.primitive_torus_add()),
        lambda: in_view(lambda: bpy.ops.view3d.view_axis(type="FRONT")),
    ],
    "lesson2": [
        lambda: setattr(checks.first_object("cylinder"), "scale", (1, 1, 0.2)),
        lambda: setattr(checks.first_object("torus").rotation_euler, "x", math.radians(90)),
        lambda: setattr(checks.first_object("torus").location, "x", 1.0),
        lambda: setattr(checks.first_object("torus").location, "x", 1.1),
    ],
}

def view_axis(side):
    return lambda: in_view(lambda: bpy.ops.view3d.view_axis(type=side))


def add_beads():
    in_view(lambda: bpy.ops.mesh.primitive_uv_sphere_add(segments=8, ring_count=6))


def place_bead(x, y):
    def act():
        bead = bpy.context.active_object
        bead.location = (x, y, 0.3)
    return act


def duplicate_bead(x, y):
    def act():
        in_view(lambda: bpy.ops.object.duplicate())
        bpy.context.active_object.location = (x, y, 0.3)
    return act


def select_for_join():
    for o in bpy.context.view_layer.objects:
        o.select_set(checks.object_kind(o) in {"uv_sphere", "cylinder"})
    bpy.context.view_layer.objects.active = checks.first_object("cylinder")


def edit_select_top():
    import bmesh
    obj = bpy.context.active_object
    mesh = bmesh.from_edit_mesh(obj.data)
    for face in mesh.faces:
        face.select_set(face.normal.z > 0.9)
    bmesh.update_edit_mesh(obj.data)


def material(kind, **inputs):
    def act():
        obj = checks.first_object(kind)
        mat = obj.active_material or bpy.data.materials.new(kind)
        if obj.active_material is None:
            obj.data.materials.append(mat)
        node = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        for name, value in inputs.items():
            node.inputs[name].default_value = value
    return act


def shading(mode):
    _, area, _ = view3d()
    area.spaces.active.shading.type = mode


def keyframe(kind):
    return lambda: checks.first_object(kind).keyframe_insert("location")


EXPORT_PATH = os.path.join(OUT, "brelok.stl")

ACTIONS.update({
    "lesson3": [
        view_axis("FRONT"), view_axis("TOP"), view_axis("RIGHT"),
        lambda: in_view(lambda: bpy.ops.view3d.view_persportho()),
        lambda: in_view(lambda: bpy.ops.view3d.view_camera()),
        lambda: bpy.ops.render.render(),
        lambda: bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "brelok.blend")),
    ],
    "lesson4": [
        add_beads,
        lambda: setattr(bpy.context.active_object, "scale", (0.2, 0.2, 0.2)),
        place_bead(0.5, 0),
        duplicate_bead(-0.5, 0),
        lambda: [duplicate_bead(0, 0.5)(), duplicate_bead(0, -0.5)()],
        select_for_join,
        lambda: in_view(lambda: bpy.ops.object.join()),
    ],
    "lesson5": [
        lambda: select_only("cube"),
        lambda: in_view(lambda: bpy.ops.object.editmode_toggle()),
        lambda: in_view(lambda: bpy.ops.mesh.select_mode(type='FACE')),
        edit_select_top,
        lambda: in_view(lambda: bpy.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={"value": (0, 0, 1)})),
        lambda: in_view(lambda: bpy.ops.transform.resize(value=(0, 0, 1))),
        lambda: in_view(lambda: bpy.ops.object.editmode_toggle()),
    ],
    "lesson6": [
        lambda: select_only("cylinder"),
        material("cylinder"),
        material("cylinder", **{"Base Color": (0.1, 0.4, 0.9, 1.0)}),
        lambda: shading('MATERIAL'),
        lambda: select_only("torus"),
        material("torus", Metallic=1.0),
        material("torus", Roughness=0.2),
        material("cylinder", Alpha=0.5),
    ],
    "lesson7": [
        lambda: setattr(bpy.context.scene, "frame_end", 72),
        lambda: [select_only("torus"), keyframe("torus")()],
        lambda: bpy.context.scene.frame_set(72),
        lambda: setattr(checks.first_object("torus").location, "z", 1.2),
        keyframe("torus"),
        lambda: in_view(lambda: bpy.ops.screen.animation_play()),
        lambda: [in_view(lambda: bpy.ops.screen.animation_cancel()),
                 in_view(lambda: bpy.ops.wm.stl_export(filepath=EXPORT_PATH))],
    ],
})

plan = []


def build_plan():
    plan.append(lambda: course.start(bpy.context, LESSON))
    plan.append(lambda: shot("00_start"))
    for i, act in enumerate(ACTIONS[LESSON], start=1):
        plan.append(lambda i=i: shot(f"{i:02d}_task"))
        plan.append(act)
        plan.append(lambda: None)
    plan.append(lambda: shot("99_done"))
    plan.append(lambda: in_view(lambda: bpy.ops.edu.stop()))
    plan.append(lambda: None)
    plan.append(lambda: shot("zz_teacher_full_blender"))
    plan.append(lambda: print("EDU_RESULT", course.progress(), "finished", course.is_finished()))
    plan.append(lambda: bpy.ops.wm.quit_blender())


def tick():
    if not plan:
        return None
    step = plan.pop(0)
    step()
    return 1.2


edu_lessons.register()
build_plan()
bpy.app.timers.register(tick, first_interval=3.0)
