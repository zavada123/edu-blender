"""Панель «Урок», меню «Додати»/«Вигляд» і оператори уроку."""

import textwrap

import bpy

from . import course

ADD_ITEMS = (
    ("cube", "Куб", 'MESH_CUBE'),
    ("cylinder", "Циліндр", 'MESH_CYLINDER'),
    ("torus", "Тор", 'MESH_TORUS'),
    ("uv_sphere", "Сфера", 'MESH_UVSPHERE'),
    ("cone", "Конус", 'MESH_CONE'),
    ("plane", "Площина", 'MESH_PLANE'),
)

VIEW_ITEMS = (
    ("FRONT", "Спереду (1)"),
    ("RIGHT", "Справа (3)"),
    ("TOP", "Зверху (7)"),
)

CHARS_PER_PIXEL = 1 / 7.5
ICON_CHARS = 5


def _wrapped(layout, context, text: str, icon='NONE') -> None:
    scale = context.preferences.view.ui_scale or 1.0
    width = int(context.region.width / scale * CHARS_PER_PIXEL) - 4
    if icon != 'NONE':
        width -= ICON_CHARS
    width = max(16, width)
    col = layout.column(align=True)
    for i, line in enumerate(textwrap.wrap(text, width) or [""]):
        col.label(text=line, icon=icon if i == 0 else 'BLANK1' if icon != 'NONE' else 'NONE')


class EDU_OT_add_primitive(bpy.types.Operator):
    bl_idname = "edu.add_primitive"
    bl_label = "Додати тіло"
    bl_options = {'REGISTER', 'UNDO'}

    kind: bpy.props.StringProperty()

    def execute(self, context):
        operator = getattr(bpy.ops.mesh, f"primitive_{self.kind}_add", None)
        if operator is None:
            return {'CANCELLED'}
        operator()
        context.active_object["edu_kind"] = self.kind
        return {'FINISHED'}


class EDU_OT_view(bpy.types.Operator):
    bl_idname = "edu.view"
    bl_label = "Вигляд"

    side: bpy.props.StringProperty()

    def execute(self, context):
        bpy.ops.view3d.view_axis(type=self.side)
        return {'FINISHED'}


class EDU_MT_add(bpy.types.Menu):
    bl_label = "Додати"

    def draw(self, context):
        features = course.current_features()
        for kind, label, icon in ADD_ITEMS:
            if f"add.{kind}" in features:
                self.layout.operator("edu.add_primitive", text=label, icon=icon).kind = kind


class EDU_MT_view(bpy.types.Menu):
    bl_label = "Вигляд"

    def draw(self, context):
        for side, label in VIEW_ITEMS:
            self.layout.operator("edu.view", text=label).side = side
        self.layout.operator("view3d.view_persportho", text="Перспектива / ортогональна (5)")


class EDU_OT_start_lesson(bpy.types.Operator):
    bl_idname = "edu.start_lesson"
    bl_label = "Почати урок"

    lesson_id: bpy.props.StringProperty()

    def execute(self, context):
        course.start(context, self.lesson_id)
        return {'FINISHED'}


class EDU_OT_check(bpy.types.Operator):
    bl_idname = "edu.check"
    bl_label = "Перевірити"

    def execute(self, context):
        course.check_now(context, manual=True)
        return {'FINISHED'}


class EDU_OT_stop(bpy.types.Operator):
    bl_idname = "edu.stop"
    bl_label = "Показати весь Blender"
    bl_description = "Режим вчителя: повертає повний інтерфейс Blender"

    def execute(self, context):
        course.stop(context)
        return {'FINISHED'}


class EDU_PT_transform(bpy.types.Panel):
    """Заміна вбудованої панелі «Трансформація» (вкладка «Елемент»).

    Вбудовану панель написано на C, її не можна сховати й повернути з Python,
    тому додаток реєструє власну під тим самим іменем. Під час уроку вона
    з'являється лише тоді, коли урок відкрив "panel.transform".
    """

    bl_idname = "VIEW3D_PT_transform"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Елемент"
    bl_label = "Трансформація"
    bl_translation_context = "edu"

    @classmethod
    def poll(cls, context):
        if context.active_object is None:
            return False
        return course.current_lesson() is None or "panel.transform" in course.current_features()

    def draw(self, context):
        obj = context.active_object
        layout = self.layout
        layout.use_property_split = True
        layout.prop(obj, "location", text="Розташування")
        layout.prop(obj, "rotation_euler", text="Обертання")
        layout.prop(obj, "scale", text="Масштаб")
        layout.prop(obj, "dimensions", text="Розміри")


class EDU_PT_lesson(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Урок"
    bl_label = "Урок"
    bl_translation_context = "edu"
    bl_options = {'HIDE_HEADER'}

    def draw(self, context):
        lesson = course.current_lesson()
        if lesson is None:
            self._draw_picker(context)
            return
        self._draw_header(context, lesson)
        if course.is_finished():
            self._draw_finished(context, lesson)
            return
        step = course.current_step()
        if step.get("new_tool"):
            self._draw_new_tool(context, step["new_tool"])
        self._draw_task(context, step)
        self._draw_footer()

    def _draw_picker(self, context):
        layout = self.layout
        layout.label(text="Едупростір: уроки 3D", icon='MESH_CUBE')
        for lesson in course.available_lessons():
            layout.operator("edu.start_lesson", text=lesson["title"]).lesson_id = lesson["id"]

    def _draw_header(self, context, lesson):
        layout = self.layout
        layout.label(text=lesson["title"], icon='BOOKMARKS')
        done, total = course.progress()
        row = layout.row(align=True)
        for i in range(total):
            row.label(icon='CHECKBOX_HLT' if i < done else 'CHECKBOX_DEHLT')
        if not course.is_finished():
            layout.label(text=f"Крок {done + 1} з {total}")

    def _draw_new_tool(self, context, card):
        box = self.layout.box()
        box.label(text="Новий інструмент: " + card["name"], icon=card.get("icon", 'TOOL_SETTINGS'))
        _wrapped(box, context, card["text"])
        if card.get("where"):
            _wrapped(box, context, "Де: " + card["where"], icon='HAND')
        if card.get("key"):
            box.label(text="Клавіша: " + card["key"], icon='EVENT_SHIFT' if "Shift" in card["key"] else 'KEYINGSET')

    def _draw_task(self, context, step):
        layout = self.layout
        layout.separator()
        layout.label(text="Завдання", icon='INFO')
        _wrapped(layout, context, step["task"])
        message = course.message()
        if message:
            box = layout.box()
            _wrapped(box, context, message, icon='ERROR')
        layout.operator("edu.check", icon='CHECKMARK')

    def _draw_finished(self, context, lesson):
        box = self.layout.box()
        box.label(text="Урок завершено!", icon='FUND')
        _wrapped(box, context, lesson.get("finish", "Молодець!"))
        self._draw_footer()

    def _draw_footer(self):
        layout = self.layout
        layout.separator()
        row = layout.row()
        row.scale_y = 0.8
        row.operator("edu.stop", text="Вчителю: весь Blender", icon='UNLOCKED', emboss=False)


CLASSES = (
    EDU_OT_add_primitive,
    EDU_OT_view,
    EDU_MT_add,
    EDU_MT_view,
    EDU_OT_start_lesson,
    EDU_OT_check,
    EDU_OT_stop,
    EDU_PT_lesson,
    EDU_PT_transform,
)

_addon_keymaps = []


def register_keymaps() -> None:
    keyconfig = bpy.context.window_manager.keyconfigs.addon
    if keyconfig is None:
        return
    keymap = keyconfig.keymaps.new(name="Object Mode", space_type='EMPTY')
    kmi = keymap.keymap_items.new("wm.call_menu", 'A', 'PRESS', shift=True)
    kmi.properties.name = "EDU_MT_add"
    _addon_keymaps.append((keymap, kmi))


def unregister_keymaps() -> None:
    for keymap, kmi in _addon_keymaps:
        keymap.keymap_items.remove(kmi)
    _addon_keymaps.clear()


def register() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    register_keymaps()


def unregister() -> None:
    unregister_keymaps()
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
