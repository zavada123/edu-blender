"""Бульбашка-підказка з поточним завданням просто в 3D-виді.

Малюється поверх 3D-виду (gpu + blf) біля місця, де треба щось натиснути:
  * tool:* — праворуч від потрібної кнопки на панелі інструментів;
  * menu:* / op:* — під потрібним меню в заголовку 3D-виду;
  * panel:transform — на ярлик Item бічної панелі, а коли вкладка відкрита, на потрібне поле;
  * ptab:* — на вкладку редактора властивостей (лише якщо це остання ціль кроку);
  * gizmo:navigate — біля кольорових осей огляду;
  * без цілі — внизу посередині.
Python не знає точних координат кнопок Blender, тому положення рахуємо з розмірів
регіонів і стандартної розкладки. Саму кнопку додатково підсвічує lock.py, а цілі поза
полотном 3D-виду (ярлики, поля бічної панелі, вкладки властивостей) обводить overlay.py.
Текст завдання може мати розмітку (див. richtext.py): назви кнопок жирним, осі кольором осі.
"""

import blf
import bpy

from . import overlay, richtext, shapes

BG = (0.09, 0.13, 0.24, 1.0)
BORDER = (0.96, 0.76, 0.18, 1.0)
TITLE = (0.98, 0.80, 0.25, 1.0)
TEXT = (0.95, 0.96, 0.98, 1.0)
HINT = (1.0, 0.62, 0.45, 1.0)

WIDTH = 330
PAD = 14
RADIUS = 10
BORDER_PX = 2
ARROW = 12
FONT_TITLE = 13
FONT_TEXT = 14
LINE_GAP = 1.45
NO_OBJECT_HINT = "Вкладка **Item** з'являється, коли тіло виділено: спершу клацни по ньому."

# Центр кнопок меню в заголовку 3D-виду (Object Mode, масштаб 1), пікселі від лівого краю.
HEADER_MENU_X = {
    "VIEW3D_MT_view": 198,
    "VIEW3D_MT_select_object": 245,
    "VIEW3D_MT_add": 290,
    "VIEW3D_MT_object": 335,
}
# Центр меню у верхньому рядку вікна (File, Edit, Render), пікселі від лівого краю вікна.
TOPBAR_MENU_X = {
    "TOPBAR_MT_file": 42,
    "TOPBAR_MT_edit": 78,
    "TOPBAR_MT_render": 125,
}
MENU_OF_OP = {
    "op:mesh.primitive_": "VIEW3D_MT_add",
    "op:object.delete": "VIEW3D_MT_object",
    "op:object.duplicate": "VIEW3D_MT_object",
    "op:object.join": "VIEW3D_MT_object",
    "op:view3d.view_axis": "VIEW3D_MT_view",
    "op:view3d.view_camera": "VIEW3D_MT_view",
    "op:render.render": "TOPBAR_MT_render",
    "op:wm.save": "TOPBAR_MT_file",
    "op:wm.stl_export": "TOPBAR_MT_file",
}
SUBMENU_PARENT = {
    "VIEW3D_MT_mesh_add": "VIEW3D_MT_add",
    "VIEW3D_MT_view_viewpoint": "VIEW3D_MT_view",
    "VIEW3D_MT_view_cameras": "VIEW3D_MT_view",
    "TOPBAR_MT_file_export": "TOPBAR_MT_file",
}
# Інші місця в заголовку 3D-виду: відступ від лівого (>0) або правого (<0) краю.
HEADER_ITEM_X = {
    "prop:View3DShading.type": -75,
    "template:template_header_3D_mode": 205,
    "op:object.mode_set": 95,
}

# Поля шкали часу під 3D-видом: відступ центру поля від правого краю 3D-виду.
FRAME_FIELD_X = {
    "Scene.frame_current": 326,
    "Scene.frame_start": 208,
    "Scene.frame_end": 113,
}

# Кольорові осі огляду (gizmo) у правому верхньому куті вільного місця: центр і радіус.
GIZMO_FROM_RIGHT = 47
GIZMO_FROM_TOP = 46
GIZMO_RADIUS = 42

# Панель інструментів: висота кнопки й відступи (масштаб 1).
TOOL_TOP = 6
TOOL_STEP = 36
TOOL_GROUP_GAP = 5
TOOL_HALF = 17

_handler = None


def _scale() -> float:
    # system.ui_scale уже враховує DPI екрана й масштаб інтерфейсу. pixel_size — лише товщина ліній
    # (на екранах 200% вона 2), тому на неї не множимо, інакше все вдвічі більше й не на місці.
    return bpy.context.preferences.system.ui_scale


# ---------------------------------------------------------------- shapes

def _arrow(side, x, y, w, h, target, size):
    """Трикутник від краю бульбашки до цілі."""
    tx, ty = target
    if side == "left":
        base = min(max(ty, y + size + RADIUS), y + h - size - RADIUS)
        return [(x, base - size), (x, base + size), (x - size, base)]
    if side == "top":
        base = min(max(tx, x + size + RADIUS), x + w - size - RADIUS)
        return [(base - size, y + h), (base + size, y + h), (base, y + h + size)]
    if side == "right":
        base = min(max(ty, y + size + RADIUS), y + h - size - RADIUS)
        return [(x + w, base - size), (x + w, base + size), (x + w + size, base)]
    if side == "bottom":
        base = min(max(tx, x + size + RADIUS), x + w - size - RADIUS)
        return [(base - size, y), (base + size, y), (base, y - size)]
    return []


# ---------------------------------------------------------------- placement

def _region(area, kind):
    return next((r for r in area.regions if r.type == kind), None)


def _tool_index(tool_id):
    """(номер кнопки, кількість розділювачів перед нею) на панелі інструментів."""
    from bl_ui.space_toolsystem_toolbar import VIEW3D_PT_tools_active as panel
    mode = bpy.context.mode if bpy.context.mode in panel._tools else 'OBJECT'
    index = groups = 0
    items = list(panel._tools[None]) + list(panel._tools.get(mode, []))
    for item in items:
        if callable(item) and type(item) is not tuple and not hasattr(item, "idname"):
            continue
        if item is None:
            groups += 1
            continue
        members = item if type(item) is tuple else (item,)
        if any(getattr(m, "idname", None) == tool_id for m in members):
            return index, groups
        index += 1
    return None


def _target(token, area, window_region):
    s = _scale()
    kind, _, name = token.partition(":")
    left = window_region.x
    top = window_region.y + window_region.height
    if kind == "tool":
        tools = _region(area, 'TOOLS')
        found = _tool_index(name)
        if tools is None or found is None:
            return None
        index, groups = found
        y = tools.y + tools.height - (TOOL_TOP + index * TOOL_STEP + groups * TOOL_GROUP_GAP + TOOL_HALF) * s
        return "left", (tools.x + tools.width - left, y - window_region.y)
    # Стрілка вгору впирається в нижній край заголовків 3D-виду.
    edge = _ceiling(area, window_region)
    if token in HEADER_ITEM_X:
        offset = HEADER_ITEM_X[token] * s
        x = area.x + offset if offset > 0 else area.x + area.width + offset
        return "top", (x - left, edge)
    if kind in {"menu", "op"}:
        menu = name if kind == "menu" else next((m for p, m in MENU_OF_OP.items() if token.startswith(p)), None)
        menu = SUBMENU_PARENT.get(menu, menu)
        if menu in TOPBAR_MENU_X:
            return "top", (TOPBAR_MENU_X[menu] * s - left, edge)
        if menu not in HEADER_MENU_X:
            return None
        return "top", (area.x + HEADER_MENU_X[menu] * s - left, edge)
    if name in FRAME_FIELD_X:
        return "bottom", (window_region.width - FRAME_FIELD_X[name] * s, 0)
    if kind == "hud":
        return "bottom", (110 * s, 0)
    if kind == "area":
        # Бічна панель 3D-виду малюється поверх, тому стрілку ставимо біля її лівого краю.
        ui = _region(area, 'UI')
        right = ui.x - left if ui is not None and ui.width > 1 else window_region.width
        return "right", (right, top - 220 * s - window_region.y)
    if token == "panel:transform":
        _, ui, rect = overlay.sidebar_focus(area)
        if ui is None:
            return None
        y = ui.y + rect[1] + rect[3] / 2 - window_region.y
        return "right", (ui.x - left, min(max(y, 0), ui.y + ui.height - window_region.y))
    if kind == "ptab":
        rect = overlay.properties_focus(bpy.context.window, name)
        if rect is None:
            return None
        ui = _region(area, 'UI')
        right = (ui.x if ui is not None and ui.width > 1 else area.x + area.width) - left
        return "right", (right, rect[1] + rect[3] / 2 - window_region.y)
    if kind == "gizmo":
        ui = _region(area, 'UI')
        right = (ui.x if ui and ui.width > 1 else left + window_region.width) - left
        x = right - (GIZMO_FROM_RIGHT + GIZMO_RADIUS) * s
        return "right", (x, _ceiling(area, window_region) - GIZMO_FROM_TOP * s)
    return None


def _ceiling(area, window_region) -> float:
    """Верх вільного місця: регіон 3D-виду заходить під заголовки, їх не перекриваємо."""
    lowest = window_region.y + window_region.height
    for kind in ('HEADER', 'TOOL_HEADER'):
        region = _region(area, kind)
        if region is not None and region.height > 1 and region.y > window_region.y:
            lowest = min(lowest, region.y)
    return lowest - window_region.y


def _free_x(area, region):
    """Ліва і права межа вільного місця полотна: між панеллю інструментів і бічною панеллю.

    Обидві панелі малюються поверх полотна, і бульбашка під ними була б схована.
    """
    tools, ui = _region(area, 'TOOLS'), _region(area, 'UI')
    left = tools.x + tools.width - region.x if tools is not None and tools.width > 1 else 0
    right = ui.x - region.x if ui is not None and ui.width > 1 else region.width
    return max(0, left), min(region.width, right)


def _layout(side, target, w, h, region, s, ceiling, free):
    margin = 8 * s
    if side == "left":
        # Стрілка біля верхнього краю бульбашки, сама бульбашка йде вниз.
        x, y = target[0] + ARROW * s + margin, target[1] - h + (RADIUS + ARROW + 10) * s
    elif side == "top":
        x, y = target[0] - 40 * s, target[1] - h - ARROW * s - margin
    elif side == "right":
        x, y = target[0] - w - ARROW * s - margin, target[1] - h / 2
    elif side == "bottom":
        x, y = target[0] - 40 * s, target[1] + ARROW * s + margin
    else:
        x, y = (free[0] + free[1] - w) / 2, 40 * s
    x = max(min(x, free[1] - w - margin), free[0] + margin)
    y = min(max(y, margin), ceiling - h - margin)
    return x, y


# ---------------------------------------------------------------- draw

def _content():
    from . import course
    step = course.current_step()
    if step is None:
        return None
    done, total = course.progress()
    title = f"Крок {done + 1} з {total}"
    tokens = step.get("highlight", [])
    hint = course.message()
    if "panel:transform" in tokens and overlay.sidebar_focus(bpy.context.area)[0] == "no_object":
        hint = (hint + " " if hint else "") + NO_OBJECT_HINT
    return title, step["task"], hint, (tokens[-1] if tokens else "")


def _draw():
    content = _content()
    if content is None:
        return
    title, task, hint, token = content
    context = bpy.context
    region, area = context.region, context.area
    s = _scale()
    width = WIDTH * s
    text_w = width - 2 * PAD * s
    lines = richtext.wrap(task, text_w, FONT_TEXT * s, s)
    hint_lines = richtext.wrap(hint, text_w, FONT_TEXT * s, s) if hint else []
    line_h = FONT_TEXT * s * LINE_GAP
    height = (2 * PAD + FONT_TITLE * LINE_GAP + 4) * s + line_h * (len(lines) + len(hint_lines))

    placed = _target(token, area, region) if token else None
    side, target = placed if placed else ("none", None)
    x, y = _layout(side, target, width, height, region, s, _ceiling(area, region), _free_x(area, region))

    if target:
        shapes.fill(_arrow(side, x, y, width, height, target, ARROW * s), BORDER)
    shapes.fill(shapes.rounded_rect(x, y, width, height, RADIUS * s), BORDER)
    b = BORDER_PX * s
    shapes.fill(shapes.rounded_rect(x + b, y + b, width - 2 * b, height - 2 * b, (RADIUS - BORDER_PX) * s), BG)

    cursor = y + height - PAD * s - FONT_TITLE * s
    blf.size(0, FONT_TITLE * s)
    blf.color(0, *TITLE)
    blf.position(0, x + PAD * s, cursor, 0)
    blf.draw(0, title)
    cursor -= (FONT_TITLE * (LINE_GAP - 1) + 4) * s + line_h
    for color, block in ((TEXT, lines), (HINT, hint_lines)):
        cursor = richtext.draw_lines(block, x + PAD * s, cursor, line_h, FONT_TEXT * s, s, color)


def enable() -> None:
    global _handler
    if _handler is None:
        _handler = bpy.types.SpaceView3D.draw_handler_add(_draw, (), 'WINDOW', 'POST_PIXEL')
    overlay.enable()


def disable() -> None:
    global _handler
    if _handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_handler, 'WINDOW')
        _handler = None
    overlay.disable()
