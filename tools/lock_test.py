"""Перевірка блокувань у справжньому вікні: Tab і G заблоковані в уроці 1,
а після «Вчителю: весь Blender» знову працюють.

  blender --factory-startup --enable-event-simulate -p 0 0 1400 860 --python tools/lock_test.py
"""

import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import edu_lessons  # noqa: E402
from edu_lessons import course  # noqa: E402

results = {}


def win():
    return bpy.context.window_manager.windows[0]


def center():
    w = win()
    area = next(a for a in w.screen.areas if a.type == 'VIEW_3D')
    return area.x + area.width // 2, area.y + area.height // 2


def press(key, **mods):
    x, y = center()
    w = win()
    w.event_simulate(type='MOUSEMOVE', value='NOTHING', x=x, y=y)
    w.event_simulate(type=key, value='PRESS', x=x, y=y, **mods)
    w.event_simulate(type=key, value='RELEASE', x=x, y=y, **mods)


def drag_after_g():
    x, y = center()
    w = win()
    press('G')
    w.event_simulate(type='MOUSEMOVE', value='NOTHING', x=x + 120, y=y)
    w.event_simulate(type='LEFTMOUSE', value='PRESS', x=x + 120, y=y)
    w.event_simulate(type='LEFTMOUSE', value='RELEASE', x=x + 120, y=y)


def cube():
    return bpy.data.objects["Cube"]


def select_cube():
    bpy.context.view_layer.objects.active = cube()
    cube().select_set(True)


steps = [
    lambda: course.start(bpy.context, "lesson1"),
    select_cube,
    lambda: press('TAB'),
    lambda: results.__setitem__("locked_tab_mode", bpy.context.object.mode),
    drag_after_g,
    lambda: results.__setitem__("locked_g_x", round(cube().location.x, 3)),
    lambda: bpy.ops.edu.stop(),
    select_cube,
    lambda: press('TAB'),
    lambda: results.__setitem__("free_tab_mode", bpy.context.object.mode),
    lambda: press('TAB'),
    drag_after_g,
    lambda: results.__setitem__("free_g_x", round(cube().location.x, 3)),
    lambda: print("EDU_LOCK_RESULT", results),
    lambda: bpy.ops.wm.quit_blender(),
]


def tick():
    if not steps:
        return None
    steps.pop(0)()
    return 0.8


edu_lessons.register()
bpy.app.timers.register(tick, first_interval=3.0)
