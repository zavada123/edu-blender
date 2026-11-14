"""Спрощений інтерфейс Blender: ховаємо все, крім відкритих в уроці інструментів.

Набір відкритих можливостей (features) задає урок, наприклад
{"tool.select", "tool.move", "add.cube"}. Модуль:
  * закриває зайві області вікна і показує лише 3D-вид з бічною панеллю уроку;
  * підміняє верхню панель і заголовок 3D-виду власними, коротшими;
  * лишає на панелі інструментів тільки дозволені інструменти;
  * вимикає гарячі клавіші недозволених операцій;
  * ховає вкладки бічної панелі, яких урок ще не відкрив.
restore() повертає все як було (режим вчителя або вимкнення додатка).
"""

import bpy
from bl_ui import space_toolsystem_toolbar as toolbar_mod
from bl_ui import space_topbar, space_view3d

TOOLS_BY_FEATURE = {
    "tool.select": {"builtin.select", "builtin.select_box", "builtin.select_circle", "builtin.select_lasso"},
    "tool.move": {"builtin.move"},
    "tool.rotate": {"builtin.rotate"},
    "tool.scale": {"builtin.scale"},
}

ALWAYS_OPS = {
    "view3d.rotate", "view3d.move", "view3d.zoom", "view3d.dolly", "view3d.view_selected",
    "view3d.view_all", "view3d.select", "view3d.select_box", "view3d.select_circle",
    "view3d.select_lasso", "object.select_all", "ed.undo", "ed.redo", "ed.undo_history",
    "view3d.ndof_orbit", "view3d.ndof_orbit_zoom", "view3d.ndof_pan", "view3d.ndof_all",
    "view3d.zoom_border", "view3d.smoothview",
}

OPS_BY_FEATURE = {
    "object.delete": {"object.delete"},
    "tool.move": {"transform.translate"},
    "tool.rotate": {"transform.rotate"},
    "tool.scale": {"transform.resize"},
    "view.numpad": {"view3d.view_axis", "view3d.view_persportho", "view3d.view_camera"},
}

LOCKED_KEYMAPS = (
    "Window", "Screen", "Screen Editing", "Frames", "3D View", "3D View Generic",
    "Object Mode", "Object Non-modal",
)

ADDON_CLASS_PREFIX = "EDU_"


class _State:
    """Оригінали, які треба повернути в restore()."""

    active = False
    toolbar_original = None
    keymap_original = {}
    hidden_panels = []
    draw_original = {}


_state = _State()


# ---------------------------------------------------------------- toolbar

def _filter_tools(items, allowed: set) -> list:
    result = []
    for item in items:
        if item is None:
            if result and result[-1] is not None:
                result.append(None)
            continue
        if hasattr(item, "idname"):
            if item.idname in allowed:
                result.append(item)
            continue
        if isinstance(item, tuple):
            group = tuple(t for t in item if hasattr(t, "idname") and t.idname in allowed)
            if len(group) == 1:
                result.append(group[0])
            elif group:
                result.append(group)
    while result and result[-1] is None:
        result.pop()
    return result


def _apply_toolbar(features: set) -> None:
    tools = toolbar_mod.VIEW3D_PT_tools_active._tools
    if _state.toolbar_original is None:
        _state.toolbar_original = list(tools['OBJECT'])
    allowed = set()
    for feature, ids in TOOLS_BY_FEATURE.items():
        if feature in features:
            allowed |= ids
    tools['OBJECT'] = _filter_tools(_state.toolbar_original, allowed)


def _restore_toolbar() -> None:
    if _state.toolbar_original is not None:
        toolbar_mod.VIEW3D_PT_tools_active._tools['OBJECT'] = _state.toolbar_original
        _state.toolbar_original = None


def ensure_allowed_tool(context, features: set) -> None:
    """Якщо активний інструмент закрили, перемикаємо на виділення."""
    tool = context.workspace.tools.from_space_view3d_mode('OBJECT', create=False)
    allowed = set()
    for feature, ids in TOOLS_BY_FEATURE.items():
        if feature in features:
            allowed |= ids
    if tool is None or tool.idname not in allowed:
        _call_in_view3d(context, lambda: bpy.ops.wm.tool_set_by_id(name="builtin.select_box"))


# ---------------------------------------------------------------- keymaps

def _kmi_allowed(kmi, allowed_ops: set, features: set) -> bool:
    if kmi.idname in allowed_ops:
        return True
    if kmi.idname == "wm.call_menu" and getattr(kmi.properties, "name", "") == "EDU_MT_add":
        return any(f.startswith("add.") for f in features)
    return False


def _apply_keymaps(context, features: set) -> None:
    keyconfig = context.window_manager.keyconfigs.user
    if keyconfig is None:
        return
    allowed_ops = set(ALWAYS_OPS)
    for feature, ops in OPS_BY_FEATURE.items():
        if feature in features:
            allowed_ops |= ops
    for km_name in LOCKED_KEYMAPS:
        keymap = keyconfig.keymaps.get(km_name)
        if keymap is None:
            continue
        for kmi in keymap.keymap_items:
            key = (km_name, kmi.id)
            original = _state.keymap_original.setdefault(key, kmi.active)
            kmi.active = original and _kmi_allowed(kmi, allowed_ops, features)


def _restore_keymaps(context) -> None:
    keyconfig = context.window_manager.keyconfigs.user
    if keyconfig is None:
        return
    for (km_name, kmi_id), active in _state.keymap_original.items():
        keymap = keyconfig.keymaps.get(km_name)
        if keymap is None:
            continue
        for kmi in keymap.keymap_items:
            if kmi.id == kmi_id:
                kmi.active = active
    _state.keymap_original = {}


# ---------------------------------------------------------------- sidebar panels

def _sidebar_panels() -> list:
    found = []
    for name in dir(bpy.types):
        cls = getattr(bpy.types, name)
        if not (isinstance(cls, type) and issubclass(cls, bpy.types.Panel)):
            continue
        if cls.__name__.startswith(ADDON_CLASS_PREFIX) or not getattr(cls, "is_registered", False):
            continue
        if getattr(cls, "bl_space_type", "") == 'VIEW_3D' and getattr(cls, "bl_region_type", "") == 'UI':
            found.append(cls)
    # Найглибші дочірні панелі знімаємо першими: повертаємо у зворотному порядку.
    by_id = {getattr(c, "bl_idname", c.__name__): c for c in found}

    def depth(cls) -> int:
        level, parent = 0, getattr(cls, "bl_parent_id", "")
        while parent:
            level += 1
            parent = getattr(by_id.get(parent), "bl_parent_id", "") if parent in by_id else ""
        return level

    return sorted(found, key=depth, reverse=True)


def _apply_panels() -> None:
    """Знімаємо всі вбудовані вкладки бічної панелі, лишаємо тільки панелі додатка.

    Вбудовану (C) панель «Трансформація» додаток заміняє власною (ui.EDU_PT_transform),
    яка з'являється, коли урок відкриває "panel.transform".
    """
    if _state.hidden_panels:
        return
    for cls in _sidebar_panels():
        bpy.utils.unregister_class(cls)
        _state.hidden_panels.append(cls)


def _restore_panels() -> None:
    for cls in reversed(_state.hidden_panels):
        bpy.utils.register_class(cls)
    _state.hidden_panels = []


# ---------------------------------------------------------------- headers

def _draw_topbar(self, context):
    from . import course
    if context.region.alignment == 'RIGHT':
        return
    layout = self.layout
    row = layout.row(align=True)
    row.label(text="Едупростір", icon='MESH_CUBE')
    lesson = course.current_lesson()
    if lesson:
        row.separator()
        row.label(text=lesson["title"])


def _draw_view3d_header(self, context):
    from . import course
    layout = self.layout
    features = course.current_features()
    if any(f.startswith("add.") for f in features):
        layout.menu("EDU_MT_add", text="Додати", icon='ADD')
    if "view.numpad" in features:
        layout.menu("EDU_MT_view", text="Вигляд", icon='VIEW_PERSPECTIVE')
    layout.separator_spacer()
    if "object.delete" in features:
        layout.operator("object.delete", text="Видалити", icon='TRASH').use_global = False


def _patch_draw(cls, func) -> None:
    if cls not in _state.draw_original:
        _state.draw_original[cls] = cls.draw
    cls.draw = func


def _restore_draws() -> None:
    for cls, draw in _state.draw_original.items():
        cls.draw = draw
    _state.draw_original = {}


# ---------------------------------------------------------------- screen layout

def _call_in_view3d(context, func) -> None:
    window = context.window or context.window_manager.windows[0]
    for area in window.screen.areas:
        if area.type == 'VIEW_3D':
            region = next(r for r in area.regions if r.type == 'WINDOW')
            with context.temp_override(window=window, area=area, region=region):
                func()
            return


def _simplify_screen(context) -> None:
    """Розгортає 3D-вид на все вікно (як Ctrl+Space), решта областей ховається.

    Закривати області по одній небезпечно: Blender звільняє їх відкладено.
    Налаштування регіонів робимо наступним тіком, коли новий екран уже готовий.
    """
    window = context.window or context.window_manager.windows[0]
    if window.screen.show_fullscreen:
        _configure_view3d(window)
        return
    _call_in_view3d(context, lambda: bpy.ops.screen.screen_full_area(use_hide_panels=False))

    def _later():
        _configure_view3d(window)
        return None

    bpy.app.timers.register(_later, first_interval=0.05)


def _configure_view3d(window) -> None:
    window.screen.show_statusbar = False
    for area in window.screen.areas:
        if area.type != 'VIEW_3D':
            continue
        space = area.spaces.active
        space.show_region_tool_header = False
        space.show_region_ui = True
        space.show_region_toolbar = True
        space.overlay.show_stats = False
        area.tag_redraw()


def _unsimplify_screen(context) -> None:
    window = context.window or context.window_manager.windows[0]
    if window.screen.show_fullscreen:
        _call_in_view3d(context, lambda: bpy.ops.screen.screen_full_area(use_hide_panels=False))


# ---------------------------------------------------------------- public

def _set_ukrainian(prefs) -> None:
    """Українська мова інтерфейсу, якщо збірка має переклади.

    Браузерну збірку зібрано без перекладів (WITH_INTERNATIONAL=OFF), тоді лишається
    англійська. Власні написи додатка українською в будь-якому разі.
    """
    try:
        prefs.view.language = 'uk_UA'
    except TypeError:
        return
    prefs.view.use_translate_interface = True
    prefs.view.use_translate_tooltips = True
    prefs.view.use_translate_new_dataname = False


def apply(context, features: set) -> None:
    if not _state.active:
        prefs = context.preferences
        prefs.use_preferences_save = False
        _set_ukrainian(prefs)
        _patch_draw(space_topbar.TOPBAR_HT_upper_bar, _draw_topbar)
        _patch_draw(space_view3d.VIEW3D_HT_header, _draw_view3d_header)
        if context.window is not None or context.window_manager.windows:
            _simplify_screen(context)
        _state.active = True
    _apply_toolbar(features)
    _apply_keymaps(context, features)
    _apply_panels()
    if context.window_manager.windows:
        ensure_allowed_tool(context, features)
    redraw_all(context)


def restore(context) -> None:
    if not _state.active:
        return
    _restore_toolbar()
    _restore_keymaps(context)
    _restore_panels()
    _restore_draws()
    if context.window_manager.windows:
        _unsimplify_screen(context)
    for window in context.window_manager.windows:
        window.screen.show_statusbar = True
    _state.active = False
    redraw_all(context)


def is_active() -> bool:
    return _state.active


def redraw_all(context) -> None:
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()
