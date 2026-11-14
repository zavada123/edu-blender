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
