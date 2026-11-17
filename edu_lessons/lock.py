"""Урок у повному інтерфейсі Blender: зайве видно, але воно сіре й не натискається.

Набір відкритих можливостей (features) задає урок, наприклад
{"tool.select", "tool.move", "add.cube"}. Модуль:
  * лишає звичайне вікно Blender (панелі, меню, редактори на своїх місцях);
  * обгортає draw() усіх Python-меню, заголовків і панелей: кнопки закритих
    операцій малюються вимкненими (сірими), відкриті лишаються робочими;
  * на панелі інструментів ліворуч вимикає закриті інструменти;
  * підсвічує (червоним) кнопки, які треба натиснути в поточному кроці;
  * вимикає гарячі клавіші закритих операцій;
  * додає клавіші 1/3/7 верхнього ряду для виглядів спереду/справа/зверху.
restore() повертає все як було (режим вчителя або вимкнення додатка).
"""

import types

import bpy
import gpu
from gpu_extras.batch import batch_for_shader

from . import coach
from . import features as F

LOCKED_KEYMAPS = (
    "Window", "Screen", "Screen Editing", "Frames", "3D View", "3D View Generic",
    "Object Mode", "Object Non-modal", "Outliner", "Mesh", "Animation",
)

SKIP_CLASSES = {"STATUSBAR_HT_header"}
# Вікна збереження файлу і перегляду рендеру лишаються звичайними.
SKIP_SPACES = {"FILE_BROWSER", "IMAGE_EDITOR", "PREFERENCES"}
HIGHLIGHT_MARK = "→ "
ADDON_CLASS_PREFIX = "EDU_"
TOOLBAR_PANEL = "VIEW3D_PT_tools_active"
TOOL_OPS = {"wm.tool_set_by_id"}

LAYOUT_METHODS = {"row", "column", "split", "box", "grid_flow", "column_flow", "menu_pie"}
PASSTHROUGH_METHODS = {
    "label", "separator", "separator_spacer", "context_pointer_set", "context_string_set",
    "menu_contents", "introspect", "progress",
}
OPERATOR_METHODS = {"operator", "operator_menu_hold", "operator_enum", "operator_menu_enum"}
MENU_METHODS = {"menu"}
PROP_METHODS = {"prop", "prop_enum", "prop_menu_enum", "prop_with_popover", "prop_with_menu", "props_enum"}


# Редактори, які в уроках не потрібні: поверх них малюємо напівпрозору тінь.
SHADED_SPACES = {"OUTLINER": bpy.types.SpaceOutliner, "DOPESHEET_EDITOR": bpy.types.SpaceDopeSheetEditor}
SHADE_COLOR = (0.0, 0.0, 0.0, 0.5)


class _State:
    """Що зараз відкрито і що треба повернути в restore()."""

    active = False
    allowed_ops = set()
    allowed_menus = set()
    allowed_tools = set()
    allowed_panels = set()
    allowed_props = set()
    allowed_templates = set()
    features = set()
    highlight = set()
    keymap_original = {}
    draw_original = {}
    view_keys = []
    shade_handlers = []
    render_display = None


_state = _State()


# ---------------------------------------------------------------- what is open

def _allowed_tools(features: set) -> set:
    return F.collect(F.TOOLS, features)


def _set_allowed(features: set) -> None:
    _state.features = set(features)
    _state.allowed_tools = _allowed_tools(features)
    _state.allowed_ops = F.collect(F.OPS, features, F.ALWAYS_OPS) | (TOOL_OPS if _state.allowed_tools else set())
    _state.allowed_menus = F.collect(F.MENUS, features, F.ALWAYS_MENUS)
    _state.allowed_panels = F.collect(F.PANELS, features, F.ALWAYS_PANELS)
    _state.allowed_props = F.collect(F.PROPS, features)
    _state.allowed_templates = F.collect(F.TEMPLATES, features)


def _expand_highlight(tokens) -> set:
    """«menu:VIEW3D_MT_mesh_add» підсвічує й батьківське меню «Add»."""
    result = set(tokens or ())
    for token in list(result):
        kind, _, name = token.partition(":")
        while kind == "menu" and name in F.MENU_PARENT:
            name = F.MENU_PARENT[name]
            result.add("menu:" + name)
    return result


# ---------------------------------------------------------------- shaded layout

class _ShadedLayout:
    """Обгортка UILayout: кожна кнопка йде в окремий підрядок з enabled/alert.

    Blender вимикає кнопки на рівні layout, а вимкнений батьківський layout
    не можна знову ввімкнути. Тому кожну кнопку кладемо в свій row().
    """

    __slots__ = ("_framed", "_real", "_tools")

    def __init__(self, real, tools=None, framed=False):
        object.__setattr__(self, "_real", real)
        object.__setattr__(self, "_tools", tools)
        object.__setattr__(self, "_framed", framed)

    def __getattr__(self, name):
        attr = getattr(self._real, name)
        if not callable(attr) or name in PASSTHROUGH_METHODS:
            return attr
        if name in LAYOUT_METHODS:
            return lambda *a, **kw: _ShadedLayout(attr(*a, **kw), self._tools, self._framed)
        if name in {"panel", "panel_prop"}:
            return lambda *a, **kw: tuple(
                _ShadedLayout(part, self._tools, self._framed) if part is not None else None
                for part in attr(*a, **kw)
            )
        return lambda *a, **kw: self._item(name, a, kw)

    def __setattr__(self, name, value):
        setattr(self._real, name, value)

    def _item(self, method, args, kwargs):
        enabled, alert = self._decide(method, args, kwargs)
        # У заголовку підсвічену кнопку обводимо рамкою (у меню рамка ламає стовпчик).
        holder = self._real.box() if alert and self._framed else self._real
        sub = holder.row(align=True)
        sub.enabled = enabled
        if alert:
            sub.alert = True
            if self._tools is None and method in OPERATOR_METHODS | MENU_METHODS:
                # У меню й заголовках колір alert не видно, тому додаємо стрілку до напису.
                kwargs = dict(kwargs, text=HIGHLIGHT_MARK + _item_label(method, args, kwargs))
        return getattr(sub, method)(*args, **kwargs)

    def _decide(self, method, args, kwargs):
        if method in OPERATOR_METHODS:
            idname = args[0] if args else kwargs.get("operator", "")
            if idname in TOOL_OPS and self._tools is not None:
                return next(self._tools, (False, False))
            return idname in _state.allowed_ops, "op:" + idname in _state.highlight
        if method in MENU_METHODS:
            name = args[0] if args else kwargs.get("menu", "")
            return name in _state.allowed_menus, "menu:" + name in _state.highlight
        if method in PROP_METHODS and len(args) >= 2:
            data = args[0]
            key = getattr(getattr(data, "bl_rna", None), "identifier", "") + "." + str(args[1])
            return key in _state.allowed_props, "prop:" + key in _state.highlight
        if method.startswith("template_"):
            return method in _state.allowed_templates, "template:" + method in _state.highlight
        return False, False


def _item_label(method, args, kwargs) -> str:
    """Напис кнопки, як його показав би Blender (без перекладу: у браузерній збірці його немає)."""
    if kwargs.get("text"):
        return kwargs["text"]
    name = args[0] if args else kwargs.get("operator", kwargs.get("menu", ""))
    if method in MENU_METHODS:
        cls = getattr(bpy.types, name, None)
        return getattr(cls, "bl_label", name)
    module, _, func = name.partition(".")
    try:
        return getattr(getattr(bpy.ops, module), func).get_rna_type().name
    except (AttributeError, KeyError):
        return name


class _ShadedSelf:
    """Підміняє self у draw(): self.layout стає _ShadedLayout, методи класу бачать його."""

    __slots__ = ("_real", "layout")

    def __init__(self, real, layout):
        object.__setattr__(self, "_real", real)
        object.__setattr__(self, "layout", layout)

    def __getattr__(self, name):
        for klass in type(self._real).__mro__:
            if name in klass.__dict__:
                if isinstance(klass.__dict__[name], types.FunctionType):
                    return types.MethodType(klass.__dict__[name], self)
                break
        return getattr(self._real, name)

    def __setattr__(self, name, value):
        setattr(self._real, name, value)


def _active_tool(context):
    try:
        return context.workspace.tools.from_space_view3d_mode(context.mode).idname
    except (AttributeError, RuntimeError, TypeError):
        return None


def _toolbar_flags(cls, context):
    """(enabled, alert) для кожної кнопки панелі інструментів по черзі."""
    flags = []
    # Інструмент уже вибрано: червоне підсвічування знімаємо, лишається звичайне синє.
    active = _active_tool(context)
    for item in cls.tools_from_context(context):
        if item is None:
            continue
        # ToolDef теж namedtuple, тому група інструментів це саме tuple.
        group = item if type(item) is tuple else (item,)
        ids = {tool.idname for tool in group if tool is not None}
        alert = active not in ids and any("tool:" + i in _state.highlight for i in ids)
        flags.append((bool(ids & _state.allowed_tools), alert))
    return iter(flags)


def _wrap_shaded(func, is_toolbar, is_header):
    def draw(self, context):
        tools = _toolbar_flags(type(self), context) if is_toolbar else None
        func(_ShadedSelf(self, _ShadedLayout(self.layout, tools, is_header)), context)
    draw._edu_original = func
    return draw


def _wrap_disabled(func):
    def draw(self, context):
        self.layout.enabled = type(self).__name__ in _state.allowed_panels
        func(self, context)
    draw._edu_original = func
    return draw


def _ui_classes() -> list:
    found = []
    for name in dir(bpy.types):
        cls = getattr(bpy.types, name)
        if not isinstance(cls, type) or not issubclass(cls, (bpy.types.Panel, bpy.types.Menu, bpy.types.Header)):
            continue
        if cls in (bpy.types.Panel, bpy.types.Menu, bpy.types.Header):
            continue
        if cls.__name__.startswith(ADDON_CLASS_PREFIX) or cls.__name__ in SKIP_CLASSES:
            continue
        if getattr(cls, "bl_space_type", "") in SKIP_SPACES:
            continue
        found.append(cls)
    return found


def _patch(cls, attr, wrapper) -> None:
    func = getattr(cls, attr, None)
    if not isinstance(func, types.FunctionType):
        return
    _state.draw_original[(cls, attr)] = cls.__dict__.get(attr)
    setattr(cls, attr, wrapper(func))


def _apply_shading() -> None:
    if _state.draw_original:
        return
    for cls in _ui_classes():
        is_panel = issubclass(cls, bpy.types.Panel)
        is_toolbar = cls.__name__ == TOOLBAR_PANEL
        if is_panel and not is_toolbar:
            _patch(cls, "draw", _wrap_disabled)
            _patch(cls, "draw_header", _wrap_disabled)
            _patch(cls, "draw_header_preset", _wrap_disabled)
        else:
            # *_editor_menus це меню, але малюються вони рядком у заголовку.
            is_header = issubclass(cls, bpy.types.Header) or cls.__name__.endswith("_editor_menus")
            _patch(cls, "draw", lambda f, t=is_toolbar, h=is_header: _wrap_shaded(f, t, h))


def _restore_shading() -> None:
    for (cls, attr), original in _state.draw_original.items():
        if original is None:
            if attr in cls.__dict__:
                delattr(cls, attr)
        else:
            setattr(cls, attr, original)
    _state.draw_original = {}


# ---------------------------------------------------------------- shade overlay

def _draw_shade(space_type):
    feature = F.SHADED_EDITORS.get(space_type)
    if feature and feature in _state.features:
        return
    region = bpy.context.region
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    w, h = region.width, region.height
    batch = batch_for_shader(shader, 'TRIS', {"pos": ((0, 0), (w, 0), (w, h), (0, 0), (w, h), (0, h))})
    gpu.state.blend_set('ALPHA')
    shader.uniform_float("color", SHADE_COLOR)
    batch.draw(shader)
    gpu.state.blend_set('NONE')


def _apply_shade_overlay() -> None:
    if _state.shade_handlers:
        return
    for space_type, space in SHADED_SPACES.items():
        for region_type in ('WINDOW', 'HEADER'):
            handler = space.draw_handler_add(_draw_shade, (space_type,), region_type, 'POST_PIXEL')
            _state.shade_handlers.append((space, handler, region_type))


def _restore_shade_overlay() -> None:
    for space, handler, region_type in _state.shade_handlers:
        space.draw_handler_remove(handler, region_type)
    _state.shade_handlers = []


# ---------------------------------------------------------------- tools

def ensure_allowed_tool(context, features: set) -> None:
    """Якщо активний інструмент закритий, перемикаємо на виділення."""
    tool = context.workspace.tools.from_space_view3d_mode('OBJECT', create=False)
    if tool is None or tool.idname not in _allowed_tools(features):
        _call_in_view3d(context, lambda: bpy.ops.wm.tool_set_by_id(name="builtin.select_box"))


# ---------------------------------------------------------------- keymaps

def _kmi_allowed(kmi) -> bool:
    if kmi.idname in _state.allowed_ops:
        return True
    if kmi.idname in {"wm.call_menu", "wm.call_menu_pie"}:
        return getattr(kmi.properties, "name", "") in _state.allowed_menus
    return False


def _apply_keymaps(context) -> None:
    keyconfig = context.window_manager.keyconfigs.user
    if keyconfig is None:
        return
    for km_name in LOCKED_KEYMAPS:
        keymap = keyconfig.keymaps.get(km_name)
        if keymap is None:
            continue
        for kmi in keymap.keymap_items:
            key = (km_name, kmi.id)
            original = _state.keymap_original.setdefault(key, kmi.active)
            kmi.active = original and _kmi_allowed(kmi)


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


def _apply_view_keys(context, features: set) -> None:
    """Клавіші верхнього ряду для виглядів і камери.

    Додаємо прямо в розкладку користувача: розкладку додатків Blender
    підмішує лише під час повного оновлення клавіатурних налаштувань.
    """
    keyconfig = context.window_manager.keyconfigs.user
    keymap = keyconfig.keymaps.get("Object Mode") if keyconfig else None
    if keymap is None:
        return
    for feature, key, idname, props in F.TOP_ROW_KEYS:
        if feature not in features or (idname, key) in _state.view_keys:
            continue
        kmi = keymap.keymap_items.new(idname, key, 'PRESS')
        for prop, value in props.items():
            setattr(kmi.properties, prop, value)
        _state.view_keys.append((idname, key))


def _restore_view_keys(context) -> None:
    """Знімаємо додані клавіші. Шукаємо їх заново: Blender міг перебудувати розкладку."""
    keyconfig = context.window_manager.keyconfigs.user
    keymap = keyconfig.keymaps.get("Object Mode") if keyconfig else None
    if keymap is not None:
        for idname, key in _state.view_keys:
            for kmi in list(keymap.keymap_items):
                if kmi.idname == idname and kmi.type == key and not (kmi.shift or kmi.ctrl or kmi.alt):
                    keymap.keymap_items.remove(kmi)
                    break
    _state.view_keys = []


# ---------------------------------------------------------------- screen

def _call_in_view3d(context, func) -> None:
    window = context.window or context.window_manager.windows[0]
    for area in window.screen.areas:
        if area.type == 'VIEW_3D':
            region = next(r for r in area.regions if r.type == 'WINDOW')
            with context.temp_override(window=window, area=area, region=region):
                func()
            return


def _show_lesson_sidebar(context) -> None:
    """Відкриває бічну панель 3D-виду на вкладці «Урок»."""
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != 'VIEW_3D':
                continue
            area.spaces.active.show_region_ui = True
            for region in area.regions:
                if region.type == 'UI':
                    try:
                        region.active_panel_category = "Урок"
                    except (AttributeError, TypeError, ValueError):
                        pass


# ---------------------------------------------------------------- public

def apply(context, features: set, highlight=()) -> None:
    _set_allowed(features)
    _state.highlight = _expand_highlight(highlight)
    if not _state.active:
        context.preferences.use_preferences_save = False
        _state.render_display = context.preferences.view.render_display_type
        # Рендер у тому ж вікні: у браузері нові вікна не відкриваються.
        context.preferences.view.render_display_type = 'SCREEN'
        _apply_shading()
        _apply_shade_overlay()
        _show_lesson_sidebar(context)
        coach.enable()
        _state.active = True
    _apply_keymaps(context)
    _apply_view_keys(context, features)
    if context.window_manager.windows:
        ensure_allowed_tool(context, features)
    redraw_all(context)


def set_highlight(context, tokens) -> None:
    _state.highlight = _expand_highlight(tokens)
    redraw_all(context)


def restore(context) -> None:
    if not _state.active:
        return
    _restore_keymaps(context)
    _restore_view_keys(context)
    _restore_shading()
    _restore_shade_overlay()
    coach.disable()
    if _state.render_display:
        context.preferences.view.render_display_type = _state.render_display
    _state.active = False
    _state.highlight = set()
    redraw_all(context)


def is_active() -> bool:
    return _state.active


def redraw_all(context) -> None:
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()
