"""Перебіг уроку: кроки, перевірки, відкриття інструментів.

Урок описано в lessons/<id>.json. Кожен крок має текст завдання, підказку,
перевірку (див. checks.py) і, за потреби, список можливостей, які відкриваються
на початку кроку, разом із карткою «Новий інструмент».
"""

import json
import math
import os

import bpy

from . import bridge, checks, lock

LESSONS_DIR = os.path.join(os.path.dirname(__file__), "lessons")
CHECK_INTERVAL = 0.5


class _Run:
    lesson = None
    step = 0
    features = set()
    check_state = {}
    message = ""
    finished = False


_run = _Run()


def available_lessons() -> list:
    lessons = []
    for name in sorted(os.listdir(LESSONS_DIR)):
        if name.endswith(".json"):
            lessons.append(load_lesson(name[:-5]))
    return lessons


def load_lesson(lesson_id: str) -> dict:
    with open(os.path.join(LESSONS_DIR, lesson_id + ".json"), encoding="utf-8") as fh:
        lesson = json.load(fh)
    lesson["id"] = lesson_id
    return lesson


def current_lesson():
    return _run.lesson


def current_features() -> set:
    return _run.features


def current_step():
    if _run.lesson is None or _run.finished:
        return None
    return _run.lesson["steps"][_run.step]


def progress() -> tuple:
    if _run.lesson is None:
        return 0, 0
    total = len(_run.lesson["steps"])
    return (total if _run.finished else _run.step), total


def message() -> str:
    return _run.message


def is_finished() -> bool:
    return _run.finished


def _features_until(lesson: dict, step_index: int) -> set:
    features = set(lesson.get("features", []))
    for step in lesson["steps"][: step_index + 1]:
        features |= set(step.get("unlock", []))
    return features


def _prepare_scene(lesson: dict) -> None:
    """Сцена уроку: лише тіла зі списку "scene" (камера і світло лишаються)."""
    wanted = set(lesson.get("scene", []))
    for obj in list(bpy.data.objects):
        if obj.type == 'MESH' and checks.object_kind(obj) not in wanted:
            bpy.data.objects.remove(obj)
    for kind in lesson.get("scene", []):
        if not checks.find_objects(kind):
            operator = getattr(bpy.ops.mesh, f"primitive_{kind}_add")
            operator()
            bpy.context.active_object["edu_kind"] = kind
    for placement in lesson.get("placement", []):
        obj = checks.first_object(placement["kind"])
        if obj is None:
            continue
        obj.location = placement.get("location", obj.location)
        obj.scale = placement.get("scale", obj.scale)
        if "rotation" in placement:
            obj.rotation_euler = [math.radians(a) for a in placement["rotation"]]
    for path, value in lesson.get("settings", {}).items():
        owner, _, prop = path.rpartition(".")
        setattr(bpy.context.scene.path_resolve(owner) if owner else bpy.context.scene, prop, value)
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)
    bpy.context.view_layer.objects.active = None


def start(context, lesson_id: str, step: int = 0) -> None:
    lesson = load_lesson(lesson_id)
    _run.lesson = lesson
    _run.finished = False
    _run.message = ""
    _prepare_scene(lesson)
    _enter_step(context, step)
    bridge.emit("lesson_start", lesson=lesson_id, steps=len(lesson["steps"]))
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=CHECK_INTERVAL, persistent=True)


def _enter_step(context, index: int) -> None:
    _run.step = index
    _run.check_state = {}
    _run.features = _features_until(_run.lesson, index)
    step = _run.lesson["steps"][index]
    lock.apply(context, _run.features, step.get("highlight", []))


def stop(context) -> None:
    _run.lesson = None
    _run.features = set()
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    lock.restore(context)


def check_now(context, manual: bool = False) -> bool:
    step = current_step()
    if step is None:
        return False
    done, hint = checks.run(context, step["check"], _run.check_state)
    if not done:
        if manual:
            _run.message = hint or "Ще не виконано."
        return False
    _complete_step(context)
    return True


def _complete_step(context) -> None:
    lesson = _run.lesson
    bridge.emit("step_done", lesson=lesson["id"], step=_run.step + 1, of=len(lesson["steps"]))
    _run.message = ""
    if _run.step + 1 >= len(lesson["steps"]):
        _run.finished = True
        bridge.emit("lesson_done", lesson=lesson["id"])
        lock.redraw_all(context)
        return
    _enter_step(context, _run.step + 1)


def _tick():
    if _run.lesson is None:
        return None
    context = bpy.context
    if context.window_manager.windows and not _run.finished:
        try:
            check_now(context)
        except (AttributeError, RuntimeError) as err:
            print("EDU check error:", err)
    return CHECK_INTERVAL


def auto_start_from_env() -> None:
    """Сторінка сайту передає урок через змінну середовища EDU_LESSON."""
    lesson_id = os.environ.get("EDU_LESSON")
    if not lesson_id:
        return

    def _deferred():
        start(bpy.context, lesson_id, int(os.environ.get("EDU_STEP", "0")))
        return None

    bpy.app.timers.register(_deferred, first_interval=0.1)
