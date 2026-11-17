"""Знімки підказок кожного кроку уроку: бульбашка, стрілка, рамки.

Для перевірки підказок на різних розмірах вікна і масштабах інтерфейсу.
Кожен крок відкривається окремо (без виконання попередніх), активне тіло кроку виділяється.
Для кроків з panel:transform є ще знімок із відкритою вкладкою Item.

Запуск (Linux, Xvfb):
  EDU_WALK=lesson2 EDU_SHOTS=out/ EDU_UI_SCALE=1.5 \
    blender --factory-startup -p 0 0 1366 680 --python tools/hint_shots.py
"""

import os
import sys

import bpy

bpy.context.preferences.view.show_splash = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import edu_lessons  # noqa: E402
from edu_lessons import checks, course  # noqa: E402

OUT = os.environ.get("EDU_SHOTS", "/tmp/edu_hint_shots")
LESSON = os.environ.get("EDU_WALK", "lesson2")
UI_SCALE = float(os.environ.get("EDU_UI_SCALE", "1"))
os.makedirs(OUT, exist_ok=True)


def view3d_ui():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == 'VIEW_3D')
    return next(r for r in area.regions if r.type == 'UI')


def shot(name):
    win = bpy.context.window_manager.windows[0]
    path = os.path.join(OUT, name + ".png")
    with bpy.context.temp_override(window=win, area=win.screen.areas[0]):
        bpy.ops.screen.screenshot(filepath=path)
    print("EDU_SHOT", path)


def select_kind(kind):
    obj = checks.first_object(kind) if kind else None
    for other in bpy.context.view_layer.objects:
        other.select_set(False)
    if obj is not None:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def open_step(index):
    def act():
        course.start(bpy.context, LESSON, index)
        step = course.current_step()
        select_kind(step.get("check", {}).get("kind"))
    return act


def item_tab():
    view3d_ui().active_panel_category = "Item"


plan = [lambda: setattr(bpy.context.preferences.view, "ui_scale", UI_SCALE)]


def build_plan():
    steps = course.load_lesson(LESSON)["steps"]
    for i, step in enumerate(steps):
        plan.extend([open_step(i), lambda: None, lambda i=i: shot(f"{LESSON}_{i + 1:02d}")])
        if "panel:transform" in step.get("highlight", []):
            plan.extend([item_tab, lambda: None, lambda i=i: shot(f"{LESSON}_{i + 1:02d}_item")])
    plan.append(lambda: bpy.ops.wm.quit_blender())


def tick():
    if not plan:
        return None
    plan.pop(0)()
    return 0.8


edu_lessons.register()
build_plan()
bpy.app.timers.register(tick, first_interval=3.0)
