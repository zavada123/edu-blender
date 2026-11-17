"""Розмітка в тексті завдань: що натискати і що тягнути видно одразу.

У JSON уроку:
  **Item**          назва кнопки, вкладки, поля чи меню: жирний світло-жовтий;
  [x]червону[/x]    вісь X: жирний червоний, як у Blender (так само [y] зелений, [z] синій);
  [k]Ctrl+S[/k]     клавіша: світла «клавіша» з темним текстом.

Бульбашка в 3D-виді малює це кольором (blf), а панель «Урок» показує той самий текст без розмітки.
"""

import re

import blf
import bpy

from . import shapes

MARKUP = re.compile(r"\*\*(.+?)\*\*|\[([xyzk])\](.+?)\[/\2\]")

UI_COLOR = (1.0, 0.86, 0.5, 1.0)
AXIS_FALLBACK = {"x": (1.0, 0.2, 0.32), "y": (0.55, 0.86, 0.0), "z": (0.16, 0.56, 1.0)}
KEY_BG = (0.87, 0.89, 0.94, 1.0)
KEY_TEXT = (0.08, 0.10, 0.18, 1.0)
KEY_PAD = 4
KEY_RADIUS = 3
BOLD_SHIFT = 0.8
BOLD = {"ui", "x", "y", "z"}


def parse(text: str) -> list:
    """Текст із розміткою → [(шматок, стиль)], стиль None, "ui", "x", "y", "z" або "k"."""
    runs, pos = [], 0
    for match in MARKUP.finditer(text or ""):
        if match.start() > pos:
            runs.append((text[pos:match.start()], None))
        if match.group(1) is not None:
            runs.append((match.group(1), "ui"))
        else:
            runs.append((match.group(3), match.group(2)))
        pos = match.end()
    if pos < len(text or ""):
        runs.append((text[pos:], None))
    return runs


def plain(text: str) -> str:
    """Той самий текст без розмітки: для панелі «Урок» і повідомлень."""
    return "".join(piece for piece, _ in parse(text))


def _words(runs) -> list:
    """Слова для перенесення рядків: кожне слово — шматки без пробілу між ними («**Item**,»)."""
    words, current = [], []
    for text, style in runs:
        parts = [text] if style == "k" else re.split(r"(\s+)", text)
        for part in parts:
            if not part:
                continue
            if style != "k" and part.isspace():
                if current:
                    words.append(current)
                    current = []
                continue
            current.append((part, style))
    if current:
        words.append(current)
    return words


def _piece_width(text, style, s) -> float:
    width = blf.dimensions(0, text)[0]
    if style == "k":
        return width + 2 * KEY_PAD * s
    if style in BOLD:
        return width + BOLD_SHIFT * s
    return width


def _word_width(word, s) -> float:
    return sum(_piece_width(text, style, s) for text, style in word)


def wrap(text: str, width: float, size: float, s: float) -> list:
    """Рядки, кожен — список слів; ширина рядка не більша за width (довге слово йде окремим рядком)."""
    blf.size(0, size)
    space = blf.dimensions(0, " ")[0]
    lines, line, used = [], [], 0.0
    for word in _words(parse(text)):
        w = _word_width(word, s)
        if line and used + space + w > width:
            lines.append(line)
            line, used = [], 0.0
        used += (space if line else 0.0) + w
        line.append(word)
    if line:
        lines.append(line)
    return lines


def _axis_color(axis):
    try:
        theme = bpy.context.preferences.themes[0].user_interface
        return (*getattr(theme, "axis_" + axis), 1.0)
    except (AttributeError, IndexError, TypeError):
        return (*AXIS_FALLBACK[axis], 1.0)


def _color(style, base):
    if style == "ui":
        return UI_COLOR
    if style in AXIS_FALLBACK:
        return _axis_color(style)
    return base


def _draw_piece(text, style, x, y, size, s, base) -> float:
    width = _piece_width(text, style, s)
    if style == "k":
        shapes.fill(shapes.rounded_rect(x, y - size * 0.32, width, size * 1.3, KEY_RADIUS * s), KEY_BG)
        blf.color(0, *KEY_TEXT)
        blf.position(0, x + KEY_PAD * s, y, 0)
        blf.draw(0, text)
        return width
    blf.color(0, *_color(style, base))
    blf.position(0, x, y, 0)
    blf.draw(0, text)
    if style in BOLD:
        blf.position(0, x + BOLD_SHIFT * s, y, 0)
        blf.draw(0, text)
    return width


def draw_lines(lines, x, y, line_h, size, s, base) -> float:
    """Малює рядки з wrap() від базової лінії y вниз. Повертає базову лінію наступного рядка."""
    blf.size(0, size)
    space = blf.dimensions(0, " ")[0]
    for line in lines:
        cursor = x
        for i, word in enumerate(line):
            if i:
                cursor += space
            for text, style in word:
                cursor += _draw_piece(text, style, cursor, y, size, s, base)
        y -= line_h
    return y
