"""Перевірки кроків уроку.

Кожна перевірка отримує контекст і параметри з JSON уроку і повертає
(виконано, пояснення). Пояснення показуємо учневі, коли крок ще не виконано.
"""

import math

import bpy

NAME_PREFIX = {
    "cube": "Cube",
    "cylinder": "Cylinder",
    "torus": "Torus",
    "uv_sphere": "Sphere",
    "cone": "Cone",
    "plane": "Plane",
}

KIND_LABEL = {
    "cube": "куб",
    "cylinder": "циліндр",
    "torus": "тор",
    "uv_sphere": "сферу",
    "cone": "конус",
    "plane": "площину",
}

# Як пункт підписано в меню Add → Mesh.
MENU_LABEL = {
    "cube": "Cube",
    "cylinder": "Cylinder",
    "torus": "Torus",
    "uv_sphere": "UV Sphere",
    "cone": "Cone",
    "plane": "Plane",
}

AXIS = {"x": 0, "y": 1, "z": 2}


def object_kind(obj) -> str | None:
    kind = obj.get("edu_kind")
    if kind:
        return kind
    for key, prefix in NAME_PREFIX.items():
        if obj.name.startswith(prefix):
            return key
    return None


def find_objects(kind: str) -> list:
    return [o for o in bpy.data.objects if o.type == 'MESH' and object_kind(o) == kind]


def first_object(kind: str):
    found = find_objects(kind)
    return found[0] if found else None


def view_region(context):
    screen = context.window.screen if context.window else None
    if screen is None:
        return None
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            return area.spaces.active.region_3d
    return None


def _missing(kind: str):
    return False, f"На сцені немає об'єкта: {KIND_LABEL.get(kind, kind)}."


def check_selected(context, params, state):
    obj = context.view_layer.objects.active
    kind = params["kind"]
    if obj is None or object_kind(obj) != kind or not obj.select_get():
        return False, f"Клацни лівою кнопкою миші по об'єкту «{KIND_LABEL.get(kind, kind)}»."
    return True, None


def check_view_rotated(context, params, state):
    rv3d = view_region(context)
    if rv3d is None:
        return False, None
    start = state.setdefault("view_start", tuple(rv3d.view_rotation))
    current = rv3d.view_rotation
    dot = abs(sum(a * b for a, b in zip(start, current, strict=True)))
    angle = math.degrees(2 * math.acos(min(1.0, dot)))
    if angle < params.get("min_degrees", 20):
        return False, "Затисни коліщатко миші й потягни, або тягни кольорові осі в правому верхньому куті."
    return True, None


def check_absent(context, params, state):
    kind = params["kind"]
    if find_objects(kind):
        return False, f"Виділи {KIND_LABEL.get(kind, kind)} і натисни X або Delete (або Object → Delete)."
    return True, None


def check_exists(context, params, state):
    kind = params["kind"]
    if len(find_objects(kind)) < params.get("count", 1):
        return False, f"Відкрий меню Add угорі → Mesh → {MENU_LABEL.get(kind, kind)}."
    return True, None


def check_side_view(context, params, state):
    rv3d = view_region(context)
    if rv3d is None:
        return False, None
    if rv3d.view_perspective != 'ORTHO' or not getattr(rv3d, "is_orthographic_side_view", True):
        return False, "Наведи мишку на сцену і натисни 1 (спереду), 3 (справа) або 7 (зверху). Або View → Viewpoint → Front."
    return True, None


def _compare(value: float, params) -> bool:
    if "equals" in params:
        return abs(value - params["equals"]) <= params.get("tolerance", 0.05)
    low = params.get("min", -math.inf)
    high = params.get("max", math.inf)
    return low <= value <= high


def _transform_value(obj, prop: str, axis: int) -> float:
    if prop == "rotation":
        return math.degrees(obj.rotation_euler[axis]) % 360
    return getattr(obj, prop)[axis]


def check_transform(context, params, state):
    kind = params["kind"]
    obj = first_object(kind)
    if obj is None:
        return _missing(kind)
    value = _transform_value(obj, params["property"], AXIS[params["axis"]])
    if not _compare(value, params):
        return False, params.get("hint")
    return True, None


CHECKS = {
    "selected": check_selected,
    "view_rotated": check_view_rotated,
    "absent": check_absent,
    "exists": check_exists,
    "side_view": check_side_view,
    "transform": check_transform,
}


def run(context, spec: dict, state: dict):
    check = CHECKS.get(spec["type"])
    if check is None:
        return False, f"Невідома перевірка: {spec['type']}"
    return check(context, spec, state)
