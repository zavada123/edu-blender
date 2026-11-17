"""Панель «Урок», панель Transform і оператори уроку."""

import textwrap

import bpy

from . import course, richtext

CHARS_PER_PIXEL = 1 / 7.5
ICON_CHARS = 5


def _wrapped(layout, context, text: str, icon='NONE') -> None:
    scale = context.preferences.view.ui_scale or 1.0
    width = int(context.region.width / scale * CHARS_PER_PIXEL) - 4
    if icon != 'NONE':
        width -= ICON_CHARS
    width = max(16, width)
    col = layout.column(align=True)
    for i, line in enumerate(textwrap.wrap(richtext.plain(text), width) or [""]):
        col.label(text=line, icon=icon if i == 0 else 'BLANK1' if icon != 'NONE' else 'NONE')


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
    """Заміна вбудованої панелі Transform (вкладка Item).

    Вбудовану панель написано на C, її не можна вимкнути з Python, тому додаток
    реєструє власну під тим самим іменем і з тими самими підписами. Під час уроку
    вона сіра, доки урок не відкрив "panel.transform".
    """

    bl_idname = "VIEW3D_PT_transform"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Item"
    bl_label = "Transform"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def draw(self, context):
        obj = context.active_object
        layout = self.layout
        layout.use_property_split = True
        lesson = course.current_lesson()
        layout.enabled = lesson is None or "panel.transform" in course.current_features()
        layout.alert = lesson is not None and "panel:transform" in (course.current_step() or {}).get("highlight", [])
        layout.prop(obj, "location")
        layout.prop(obj, "rotation_euler", text="Rotation")
        layout.prop(obj, "scale")
        layout.prop(obj, "dimensions")


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
            box.label(text="Клавіша: " + richtext.plain(card["key"]), icon='EVENT_SHIFT' if "Shift" in card["key"] else 'KEYINGSET')

    def _draw_task(self, context, step):
        layout = self.layout
        layout.separator()
        layout.label(text="Завдання", icon='INFO')
        _wrapped(layout, context, step["task"])
        message = course.message()
        if message:
            box = layout.box()
            _wrapped(box, context, message, icon='ERROR')
        elif step.get("tip"):
            box = layout.box()
            _wrapped(box, context, step["tip"], icon='QUESTION')
        layout.operator("edu.check", icon='CHECKMARK')

    def _draw_finished(self, context, lesson):
        box = self.layout.box()
        box.label(text="Урок завершено!", icon='FUND')
        _wrapped(box, context, lesson.get("finish", "Молодець!"))
        _wrapped(self.layout, context, "Наступний урок і список уроків чекають у картці внизу сторінки.", icon='FORWARD')
        self._draw_footer()

    def _draw_footer(self):
        layout = self.layout
        layout.separator()
        row = layout.row()
        row.scale_y = 0.8
        row.operator("edu.stop", text="Вчителю: весь Blender", icon='UNLOCKED', emboss=False)


CLASSES = (
    EDU_OT_start_lesson,
    EDU_OT_check,
    EDU_OT_stop,
    EDU_PT_lesson,
    EDU_PT_transform,
)

def _context_properties_after_transform() -> None:
    """Панель Properties вкладки Item іде після нашої Transform, як у звичайному Blender.

    Порядок панелей — порядок реєстрації, а наша Transform реєструється пізніше за вбудовані.
    Тоді рядок Location X завжди на тому самому місці, і overlay.py точно його обводить.
    """
    panel = getattr(bpy.types, "VIEW3D_PT_context_properties", None)
    if panel is None:
        return
    try:
        bpy.utils.unregister_class(panel)
        bpy.utils.register_class(panel)
    except RuntimeError:
        pass


def register() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    _context_properties_after_transform()


def unregister() -> None:
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
