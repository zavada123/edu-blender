"""Перевірки для уроків 3–7: рендер і файли, копії, режим редагування, матеріали, анімація."""

import os

import bmesh
import bpy

from .checks import KIND_LABEL, compare, first_object, view_space


class _Counters:
    """Що сталося з початку уроку (рахують обробники Blender)."""

    renders = 0


counters = _Counters()


def _on_render(*_args) -> None:
    counters.renders += 1


def register_handlers() -> None:
    if _on_render not in bpy.app.handlers.render_post:
        bpy.app.handlers.render_post.append(_on_render)


def unregister_handlers() -> None:
    if _on_render in bpy.app.handlers.render_post:
        bpy.app.handlers.render_post.remove(_on_render)


def _label(kind: str) -> str:
    return KIND_LABEL.get(kind, kind)


# ---------------------------------------------------------------- рендер і файли

def check_rendered(context, params, state):
    start = state.setdefault("renders_start", counters.renders)
    if counters.renders <= start:
        return False, "Натисни F12 або відкрий меню Render угорі і вибери Render Image."
    return True, None


def check_saved(context, params, state):
    if not bpy.data.is_saved or bpy.data.is_dirty:
        return False, "Натисни Ctrl+S (або File → Save As), введи назву файлу і натисни Save."
    return True, None


def _export_dirs(context, operator) -> list:
    """Де шукати свіжий файл: останній шлях експорту, тека .blend, робоча й домашня теки."""
    props = context.window_manager.operator_properties_last(operator)
    last = bpy.path.abspath(getattr(props, "filepath", "") or "")
    dirs = [os.path.dirname(last)] if last else []
    if bpy.data.filepath:
        dirs.append(os.path.dirname(bpy.data.filepath))
    dirs += [os.getcwd(), os.path.expanduser("~")]
    return [d for d in dict.fromkeys(dirs) if d and os.path.isdir(d)]


def check_exported(context, params, state):
    """У відомих теках з'явився файл потрібного формату, новіший за початок кроку."""
    import time
    started = state.setdefault("export_start", time.time() - 1)
    ext = params.get("ext", ".stl").lower()
    for folder in _export_dirs(context, params["operator"]):
        for entry in os.scandir(folder):
            if entry.is_file() and entry.name.lower().endswith(ext) and entry.stat().st_mtime >= started:
                return True, None
    return False, params.get("hint", "Відкрий File → Export і вибери потрібний формат.")


# ---------------------------------------------------------------- об'єкти

def check_selected_count(context, params, state):
    count = sum(1 for o in context.view_layer.objects if o.type == 'MESH' and o.select_get())
    if count < params["min"]:
        return False, "Клацни по першому тілу, а далі по кожному наступному з затиснутим Shift."
    return True, None


def check_mesh_count(context, params, state):
    count = sum(1 for o in bpy.data.objects if o.type == 'MESH')
    if not compare(count, params):
        return False, params.get("hint")
    return True, None


def check_vertices(context, params, state):
    kind = params["kind"]
    obj = first_object(kind)
    if obj is None:
        return False, f"На сцені немає об'єкта: {_label(kind)}."
    if obj.mode == 'EDIT':
        obj.update_from_editmode()
    if not compare(len(obj.data.vertices), params):
        return False, params.get("hint")
    return True, None


def check_height(context, params, state):
    """Найвища точка тіла (світові координати)."""
    kind = params["kind"]
    obj = first_object(kind)
    if obj is None:
        return False, f"На сцені немає об'єкта: {_label(kind)}."
    if obj.mode == 'EDIT':
        obj.update_from_editmode()
    top = max((obj.matrix_world @ v.co).z for v in obj.data.vertices)
    if not compare(top, params):
        return False, params.get("hint")
    return True, None


def check_apex(context, params, state):
    """Верхні вершини зведені в одну точку (піраміда)."""
    obj = first_object(params["kind"])
    if obj is None:
        return False, None
    if obj.mode == 'EDIT':
        obj.update_from_editmode()
    verts = [v.co for v in obj.data.vertices]
    top = max(v.z for v in verts)
    upper = [v for v in verts if v.z > top - 0.01]
    spread = max(max(v.x for v in upper) - min(v.x for v in upper), max(v.y for v in upper) - min(v.y for v in upper))
    if len(upper) < 2 and len(verts) > 5 or spread > params.get("max_spread", 0.05):
        return False, params.get("hint")
    return True, None


# ---------------------------------------------------------------- режим редагування

def check_mode(context, params, state):
    obj = context.view_layer.objects.active
    mode = params["mode"]
    if obj is None or obj.mode != mode:
        if mode == 'EDIT':
            return False, "Наведи мишку на сцену і натисни Tab (або вибери Edit Mode у списку ліворуч угорі)."
        return False, "Натисни Tab, щоб повернутися в Object Mode."
    return True, None


def check_select_mode(context, params, state):
    modes = {"VERT": 0, "EDGE": 1, "FACE": 2}
    if not context.tool_settings.mesh_select_mode[modes[params["mode"]]]:
        return False, params.get("hint", "У режимі редагування натисни 3 (грані) або кнопку з квадратиком угорі.")
    return True, None


def check_selected_face(context, params, state):
    obj = context.view_layer.objects.active
    if obj is None or obj.mode != 'EDIT':
        return False, "Спершу ввійди в Edit Mode (Tab)."
    mesh = bmesh.from_edit_mesh(obj.data)
    faces = [f for f in mesh.faces if f.select]
    if len(faces) != 1 or (obj.matrix_world.to_3x3() @ faces[0].normal).z < 0.9:
        return False, params.get("hint", "Клацни по верхній грані, щоб виділити тільки її.")
    return True, None


# ---------------------------------------------------------------- матеріали

def _principled(obj):
    mat = obj.active_material
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return mat, None
    node = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    return mat, node


def check_material(context, params, state):
    kind = params["kind"]
    obj = first_object(kind)
    if obj is None:
        return False, f"На сцені немає об'єкта: {_label(kind)}."
    mat, node = _principled(obj)
    if mat is None:
        return False, f"Виділи {_label(kind)}, відкрий вкладку Material (червона кулька праворуч) і натисни New."
    prop = params.get("property")
    if prop is None:
        return True, None
    if node is None:
        return False, None
    if prop == "color":
        r, g, b, _a = node.inputs["Base Color"].default_value
        saturation = max(r, g, b) - min(r, g, b)
        if saturation < params.get("min_saturation", 0.2):
            return False, params.get("hint")
        return True, None
    value = node.inputs[prop].default_value
    if not compare(value, params):
        return False, params.get("hint")
    return True, None


def check_shading(context, params, state):
    space = view_space(context)
    if space is None:
        return False, None
    if space.shading.type != params["mode"]:
        return False, params.get("hint", "Угорі праворуч у 3D-виді натисни третю кульку (Material Preview).")
    return True, None


# ---------------------------------------------------------------- анімація

def _keyframes(obj) -> list:
    anim = obj.animation_data
    if anim is None or anim.action is None:
        return []
    action = anim.action
    fcurves = getattr(action, "fcurves", None)
    if fcurves is None:
        from bpy_extras import anim_utils
        channelbag = anim_utils.action_get_channelbag_for_slot(action, anim.action_slot)
        fcurves = channelbag.fcurves if channelbag else []
    return [k for fc in fcurves for k in fc.keyframe_points]


def check_keyframes(context, params, state):
    kind = params["kind"]
    obj = first_object(kind)
    if obj is None:
        return False, f"На сцені немає об'єкта: {_label(kind)}."
    frames = {round(k.co.x) for k in _keyframes(obj)}
    if len(frames) < params.get("min_frames", 1):
        return False, params.get("hint", "Наведи мишку на сцену і натисни I, щоб поставити ключовий кадр.")
    return True, None


def check_scene(context, params, state):
    value = context.scene.path_resolve(params["property"])
    if not compare(value, params):
        return False, params.get("hint")
    return True, None


def check_playing(context, params, state):
    windows = context.window_manager.windows
    screen = context.screen or (windows[0].screen if windows else None)
    if screen is None or not screen.is_animation_playing:
        return False, "Наведи мишку на сцену і натисни пробіл. Ще раз пробіл зупинить відтворення."
    return True, None


CHECKS = {
    "rendered": check_rendered,
    "saved": check_saved,
    "exported": check_exported,
    "selected_count": check_selected_count,
    "mesh_count": check_mesh_count,
    "vertices": check_vertices,
    "height": check_height,
    "apex": check_apex,
    "mode": check_mode,
    "select_mode": check_select_mode,
    "selected_face": check_selected_face,
    "material": check_material,
    "shading": check_shading,
    "keyframes": check_keyframes,
    "scene": check_scene,
    "playing": check_playing,
}

