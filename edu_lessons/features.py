"""Що саме відкриває кожна можливість уроку (feature).

Урок перелічує можливості ("tool.move", "add.cube", "panel.material"...). Для кожної
тут задано, які оператори, меню, інструменти, панелі, властивості й шаблони Blender
стають робочими. Усе інше lock.py малює сірим і вимикає.
"""

PRIMITIVES = ("cube", "cylinder", "torus", "uv_sphere", "cone", "plane")

TOOLS = {
    "tool.select": {"builtin.select", "builtin.select_box", "builtin.select_circle", "builtin.select_lasso"},
    "tool.move": {"builtin.move"},
    "tool.rotate": {"builtin.rotate"},
    "tool.scale": {"builtin.scale"},
    "edit.extrude": {"builtin.extrude_region"},
}

ALWAYS_OPS = {
    "view3d.rotate", "view3d.move", "view3d.zoom", "view3d.dolly", "view3d.view_selected",
    "view3d.view_all", "view3d.select", "view3d.select_box", "view3d.select_circle",
    "view3d.select_lasso", "object.select_all", "ed.undo", "ed.redo", "ed.undo_history",
    "view3d.ndof_orbit", "view3d.ndof_orbit_zoom", "view3d.ndof_pan", "view3d.ndof_all",
    "view3d.zoom_border", "view3d.smoothview", "view3d.view_orbit", "view3d.view_roll",
    "outliner.item_activate", "outliner.select_box", "outliner.item_openclose",
    "outliner.expanded_toggle", "outliner.show_active", "outliner.select_walk",
    "mesh.select_all", "render.view_cancel", "screen.animation_cancel",
}

OPS = {
    "object.delete": {"object.delete"},
    "tool.move": {"transform.translate"},
    "tool.rotate": {"transform.rotate"},
    "tool.scale": {"transform.resize"},
    "view.numpad": {"view3d.view_axis", "view3d.view_persportho"},
    "view.camera": {"view3d.view_camera"},
    "view.shading": {"view3d.toggle_shading"},
    "render.image": {"render.render", "render.view_show"},
    "file.save": {"wm.save_mainfile", "wm.save_as_mainfile"},
    "file.export": {"wm.stl_export"},
    "object.duplicate": {"object.duplicate_move", "object.duplicate"},
    "object.join": {"object.join"},
    "redo.panel": {"screen.redo_last"},
    "mode.edit": {"object.editmode_toggle", "object.mode_set"},
    "edit.select_mode": {"mesh.select_mode"},
    "edit.extrude": {
        "view3d.edit_mesh_extrude_move_normal", "view3d.edit_mesh_extrude_move_shrink_fatten",
        "mesh.extrude_region_move", "mesh.extrude_context_move", "mesh.extrude_region_shrink_fatten",
    },
    "panel.material": {"material.new", "object.material_slot_add"},
    "anim.timeline": {
        "anim.change_frame", "screen.frame_offset", "screen.frame_jump", "screen.keyframe_jump",
        "screen.animation_play", "anim.keyframe_insert", "anim.keyframe_insert_menu",
        "anim.keyframe_delete_v3d",
    },
    **{f"add.{kind}": {f"mesh.primitive_{kind}_add"} for kind in PRIMITIVES},
}

ALWAYS_MENUS = {"VIEW3D_MT_select_object", "VIEW3D_MT_select_edit_mesh"}

MENUS = {
    "object.delete": {"VIEW3D_MT_object"},
    "object.duplicate": {"VIEW3D_MT_object"},
    "object.join": {"VIEW3D_MT_object"},
    "view.numpad": {"VIEW3D_MT_view", "VIEW3D_MT_view_viewpoint"},
    "view.camera": {"VIEW3D_MT_view", "VIEW3D_MT_view_cameras"},
    "view.shading": {"VIEW3D_MT_shading_pie", "VIEW3D_MT_shading_ex_pie"},
    "render.image": {"TOPBAR_MT_render"},
    "file.save": {"TOPBAR_MT_file"},
    "file.export": {"TOPBAR_MT_file", "TOPBAR_MT_file_export"},
    **{f"add.{kind}": {"VIEW3D_MT_add", "VIEW3D_MT_mesh_add"} for kind in PRIMITIVES},
}

# Підменю: щоб підсвітити пункт, підсвічуємо й меню, де він лежить.
MENU_PARENT = {
    "VIEW3D_MT_mesh_add": "VIEW3D_MT_add",
    "VIEW3D_MT_view_viewpoint": "VIEW3D_MT_view",
    "VIEW3D_MT_view_cameras": "VIEW3D_MT_view",
    "TOPBAR_MT_file_export": "TOPBAR_MT_file",
}

# Панелі (вкладки редактора властивостей), які відкриваються цілими.
PANELS = {
    "panel.material": {
        "EEVEE_MATERIAL_PT_context_material", "EEVEE_MATERIAL_PT_surface", "MATERIAL_PT_preview",
        "EEVEE_MATERIAL_PT_settings", "EEVEE_MATERIAL_PT_settings_surface",
    },
}

# Окремі поля: "<тип RNA>.<властивість>".
PROPS = {
    "view.shading": {"View3DShading.type"},
    "anim.timeline": {"Scene.frame_current", "Scene.frame_start", "Scene.frame_end"},
}

# Шаблони Blender (template_*), які відкриваються.
TEMPLATES = {
    "edit.select_mode": {"template_header_3D_mode"},
}

# Клавіші верхнього ряду (не в усіх є цифровий блок): (можливість, клавіша, оператор, властивості).
TOP_ROW_KEYS = (
    ("view.numpad", 'ONE', "view3d.view_axis", {"type": 'FRONT'}),
    ("view.numpad", 'THREE', "view3d.view_axis", {"type": 'RIGHT'}),
    ("view.numpad", 'SEVEN', "view3d.view_axis", {"type": 'TOP'}),
    ("view.numpad", 'FIVE', "view3d.view_persportho", {}),
    ("view.camera", 'ZERO', "view3d.view_camera", {}),
)

# Редактори, поверх яких малюємо тінь, і можливість, яка її знімає.
SHADED_EDITORS = {
    "OUTLINER": None,
    "DOPESHEET_EDITOR": "anim.timeline",
}


def collect(table: dict, features: set, base=()) -> set:
    result = set(base)
    for feature, items in table.items():
        if feature in features:
            result |= items
    return result
