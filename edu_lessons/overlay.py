"""Рамки навколо цілей поза полотном 3D-виду.

Бульбашка (coach.py) малюється в полотні 3D-виду і під бічну панель чи в інший редактор
не дістає. Тому ці цілі обводимо окремо, у їхніх власних регіонах:
  * panel:transform — ярлик Item на правому краї бічної панелі, а коли вкладка Item
    відкрита, рядок потрібного поля (Location X тощо) у групі Transform;
  * ptab:<ВКЛАДКА> — вкладка в стовпчику значків редактора властивостей (ptab:OBJECT, ptab:MATERIAL).

Python не знає координат кнопок, тому положення рахуємо з розкладки Blender: списку
ярликів/вкладок (його віддає сам Blender), розміру шрифту, масштабу інтерфейсу і прокрутки
регіону (view2d). Числа перевірено на Blender 5.3 при масштабі 1, 1.5 і 2.
"""

import re

import blf
import bpy

from . import shapes

FRAME = (0.98, 0.80, 0.25, 1.0)
FRAME_FILL = (0.98, 0.80, 0.25, 0.12)
FRAME_OUTSET = 2
FRAME_PX = 2.5
FRAME_RADIUS = 5
POINTER = 9

# Ярлики бічної панелі (вертикальні, на правому краї).
TAB_TOP = 4.8
TAB_PAD = 15
TAB_GAP = 4.3
TAB_WIDTH = 21
SIDEBAR_CATEGORY = "Item"

# Група Transform на вкладці Item: центр рядка Location X від верху регіону, крок рядків.
ROW_FIRST = 44.6
ROW_STEP = 19.6
ROW_GROUP_GAP = 7.3
ROW_HALF = 10.5
ROW_GROUPS = ("location", "rotation", "scale", "dimensions")

# Стовпчик вкладок редактора властивостей.
PROP_TOP = 5.5
PROP_STEP = 28
PROP_SPACER = 8
PROP_SPACER_BEFORE = {"COLLECTION", "OBJECT", "TEXTURE"}

_handlers = []
_last_sidebar = [None]


def _scale() -> float:
    # system.ui_scale уже враховує DPI екрана й масштаб інтерфейсу. pixel_size — лише товщина ліній
    # (на екранах 200% вона 2), тому на неї не множимо, інакше все вдвічі більше й не на місці.
    return bpy.context.preferences.system.ui_scale


def _choices(owner, prop) -> list:
    """Поточні варіанти динамічного списку Blender, у тому порядку, як їх видно на екрані.

    Python не має прямого доступу до них, але Blender перелічує їх у тексті помилки,
    коли присвоїти неіснуючий варіант. Саме значення при цьому не змінюється.
    """
    try:
        setattr(owner, prop, "\u0001")
    except (TypeError, ValueError) as err:
        found = re.search(r"not found in \((.*)\)", str(err))
        if found:
            return re.findall(r"'([^']*)'", found.group(1))
    except AttributeError:
        pass
    return []


def region_of(area, kind):
    return next((r for r in area.regions if r.type == kind), None)


# ---------------------------------------------------------------- геометрія

def sidebar_tab_rect(region, category):
    """(x, y, w, h) ярлика бічної панелі в координатах регіону або None, якщо ярлика немає."""
    categories = _choices(region, "active_panel_category")
    if category not in categories:
        return None
    s = _scale()
    blf.size(0, bpy.context.preferences.ui_styles[0].widget.points * s)
    top = region.height - TAB_TOP * s
    for name in categories:
        length = blf.dimensions(0, name)[0] + TAB_PAD * s
        if name == category:
            return region.width - TAB_WIDTH * s, top - length, (TAB_WIDTH - 1) * s, length
        top -= length + TAB_GAP * s
    return None


def transform_row_rect(region, prop, axis):
    """(x, y, w, h) рядка поля Transform (наприклад location, x) на вкладці Item."""
    if prop not in ROW_GROUPS or axis not in "xyz":
        prop, axis = "location", "x"
    s = _scale()
    group = ROW_GROUPS.index(prop)
    row = group * 3 + "xyz".index(axis)
    center = (ROW_FIRST + row * ROW_STEP + group * ROW_GROUP_GAP) * s
    y = region.view2d.view_to_region(0, -center, clip=False)[1]
    left, right = 6 * s, region.width - (TAB_WIDTH + 4) * s
    return left, y - ROW_HALF * s, right - left, 2 * ROW_HALF * s


def properties_tab_rect(area, region, tab):
    """(x, y, w, h) вкладки редактора властивостей у стовпчику значків або None."""
    tabs = _choices(area.spaces.active, "context")
    if tab not in tabs:
        return None
    s = _scale()
    offset = PROP_TOP * s
    for i, name in enumerate(tabs):
        if name in PROP_SPACER_BEFORE or (i and tabs[i - 1] == "TOOL"):
            offset += PROP_SPACER * s
        if name == tab:
            center = offset + PROP_STEP * s / 2
            y = region.view2d.view_to_region(0, -center, clip=False)[1]
            half = (PROP_STEP / 2 - 1.5) * s
            return 3 * s, y - half, region.width - 6 * s, 2 * half
        offset += PROP_STEP * s
    return None


# ---------------------------------------------------------------- що обводити

def _step():
    from . import course
    return course.current_step()


def _check_field(step):
    check = step.get("check", {})
    if check.get("type") == "transform":
        return check.get("property", "location"), check.get("axis", "x")
    return "location", "x"


def sidebar_focus(area):
    """Ціль у бічній панелі для panel:transform: ("tab"|"row", ui-регіон, rect) або ("no_object"|"closed", None, None)."""
    region = region_of(area, 'UI')
    if region is None or region.width <= 1:
        return "closed", None, None
    if region.active_panel_category == SIDEBAR_CATEGORY:
        return "row", region, transform_row_rect(region, *_check_field(_step()))
    rect = sidebar_tab_rect(region, SIDEBAR_CATEGORY)
    if rect is None:
        return "no_object", None, None
    return "tab", region, rect


def properties_focus(window, tab):
    """Вкладка редактора властивостей у координатах вікна: (x, y, w, h) або None."""
    for area in window.screen.areas:
        if area.type != 'PROPERTIES':
            continue
        region = region_of(area, 'NAVIGATION_BAR')
        if region is None or region.width <= 1:
            continue
        rect = properties_tab_rect(area, region, tab)
        if rect is None or rect[1] + rect[3] < 0 or rect[1] > region.height:
            continue
        return rect[0] + region.x, rect[1] + region.y, rect[2], rect[3]
    return None


# ---------------------------------------------------------------- малювання

def _frame(rect, pointer=None) -> None:
    """Рамка трохи ширша за ціль, щоб не закривати її підпис чи значок."""
    s = _scale()
    out = FRAME_OUTSET * s
    x, y, w, h = rect[0] - out, rect[1] - out, rect[2] + 2 * out, rect[3] + 2 * out
    shapes.fill(shapes.rounded_rect(x, y, w, h, FRAME_RADIUS * s), FRAME_FILL)
    shapes.fill(shapes.ring(x, y, w, h, FRAME_RADIUS * s, FRAME_PX * s), FRAME)
    if pointer == "left":
        tip = (x - 2 * s, y + h / 2)
        shapes.fill(shapes.arrow_to("left", tip, POINTER * s), FRAME)


def _tokens():
    step = _step()
    return step.get("highlight", []) if step else []


def _draw_sidebar() -> None:
    if "panel:transform" not in _tokens():
        return
    kind, region, rect = sidebar_focus(bpy.context.area)
    if kind != _last_sidebar[0]:
        # Учень відкрив вкладку Item: бульбашка в полотні 3D-виду має перемалюватися й показати на поле.
        _last_sidebar[0] = kind
        bpy.context.area.tag_redraw()
    if kind == "tab":
        _frame(rect, pointer="left")
    elif kind == "row" and 0 <= rect[1] + rect[3] and rect[1] <= region.height:
        _frame(rect)


def _draw_properties() -> None:
    tabs = [t.partition(":")[2] for t in _tokens() if t.startswith("ptab:")]
    if not tabs:
        return
    area, region = bpy.context.area, bpy.context.region
    for tab in tabs:
        rect = properties_tab_rect(area, region, tab)
        if rect is not None:
            _frame(rect)


def enable() -> None:
    if _handlers:
        return
    _handlers.append((bpy.types.SpaceView3D, bpy.types.SpaceView3D.draw_handler_add(_draw_sidebar, (), 'UI', 'POST_PIXEL'), 'UI'))
    _handlers.append((bpy.types.SpaceProperties, bpy.types.SpaceProperties.draw_handler_add(_draw_properties, (), 'NAVIGATION_BAR', 'POST_PIXEL'), 'NAVIGATION_BAR'))


def disable() -> None:
    while _handlers:
        space, handler, region = _handlers.pop()
        space.draw_handler_remove(handler, region)
