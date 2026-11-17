"""Прості фігури для підказок поверх Blender: заокруглені прямокутники, рамки, трикутники."""

import math

import gpu
from gpu_extras.batch import batch_for_shader


def _outline(x, y, w, h, r, segments=6):
    r = max(0.0, min(r, w / 2, h / 2))
    corners = ((x + w - r, y + h - r, 0), (x + r, y + h - r, 90), (x + r, y + r, 180), (x + w - r, y + r, 270))
    points = []
    for cx, cy, start in corners:
        for i in range(segments + 1):
            angle = math.radians(start + 90 * i / segments)
            points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return points


def rounded_rect(x, y, w, h, r):
    """Трикутники заповненого прямокутника із заокругленими кутами."""
    outline = _outline(x, y, w, h, r)
    center = (x + w / 2, y + h / 2)
    tris = []
    for i in range(len(outline)):
        tris += [center, outline[i], outline[(i + 1) % len(outline)]]
    return tris


def ring(x, y, w, h, r, thickness):
    """Трикутники рамки товщиною thickness уздовж краю прямокутника."""
    outer = _outline(x, y, w, h, r)
    inner = _outline(x + thickness, y + thickness, w - 2 * thickness, h - 2 * thickness, max(0.0, r - thickness))
    tris = []
    for i in range(len(outer)):
        j = (i + 1) % len(outer)
        tris += [outer[i], outer[j], inner[i], inner[i], outer[j], inner[j]]
    return tris


def fill(tris, color) -> None:
    if not tris:
        return
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'TRIS', {"pos": tris})
    shader.uniform_float("color", color)
    gpu.state.blend_set('ALPHA')
    batch.draw(shader)
    gpu.state.blend_set('NONE')


def arrow_to(side, tip, size):
    """Трикутник з вершиною в tip; side — звідки він іде: left, right, top, bottom."""
    tx, ty = tip
    if side == "left":
        return [(tx - size, ty - size), (tx - size, ty + size), (tx, ty)]
    if side == "right":
        return [(tx + size, ty - size), (tx + size, ty + size), (tx, ty)]
    if side == "top":
        return [(tx - size, ty + size), (tx + size, ty + size), (tx, ty)]
    return [(tx - size, ty - size), (tx + size, ty - size), (tx, ty)]
