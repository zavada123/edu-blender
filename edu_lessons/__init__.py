"""Едупростір: покрокові уроки Blender для 9 класу (§4.2–4.5).

Встановлення в настільному Blender 5.3: Edit → Preferences → Get Extensions →
Install from Disk → edu_lessons.zip. Урок обирають у бічній панелі (N) на вкладці «Урок».
У браузерній збірці урок стартує сам за змінною середовища EDU_LESSON.
"""

import bpy

from . import checks_extra, course, ui


def register():
    ui.register()
    checks_extra.register_handlers()
    course.auto_start_from_env()


def unregister():
    course.stop(bpy.context)
    checks_extra.unregister_handlers()
    ui.unregister()
