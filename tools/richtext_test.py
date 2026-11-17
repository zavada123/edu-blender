"""Перевірка розмітки підказок: розбір, текст без розмітки, перенесення рядків і тексти всіх уроків.

Запуск: blender --background --factory-startup --python tools/richtext_test.py
Код виходу 0 — усе гаразд, 1 — є помилки (їх видно в рядках FAIL).
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from edu_lessons import course, richtext  # noqa: E402

failures = []


def check(name, condition):
    print(("ok   " if condition else "FAIL ") + name)
    if not condition:
        failures.append(name)


def test_parse_styles():
    runs = richtext.parse("Тягни [x]червону стрілку[/x] у **Item**, натисни [k]Ctrl+S[/k].")
    check("parse: стилі по порядку", [style for _, style in runs] == [None, "x", None, "ui", None, "k", None])
    check("parse: текст осі", runs[1] == ("червону стрілку", "x"))


def test_plain():
    check("plain: без розмітки", richtext.plain("[z]Синя[/z] **Move** і [k]G[/k]") == "Синя Move і G")
    check("plain: звичайний текст не змінюється", richtext.plain("Клацни по кубу.") == "Клацни по кубу.")
    check("plain: порожній", richtext.plain("") == "")


def test_wrap_keeps_punctuation_with_word():
    lines = richtext.wrap("Відкрий **Item**, далі **Transform**.", 10_000, 14, 1.0)
    words = [word for line in lines for word in line]
    check("wrap: усе в одному рядку", len(lines) == 1)
    check("wrap: кома лишається біля Item", words[1] == [("Item", "ui"), (",", None)])


def test_wrap_respects_width():
    text = "Тягни [x]червону стрілку (вісь X)[/x] праворуч, поки **Location X** не стане більшим за 0,9."
    lines = richtext.wrap(text, 120, 14, 1.0)
    check("wrap: вузька бульбашка дає кілька рядків", len(lines) > 2)
    rebuilt = " ".join("".join(piece for piece, _ in word) for line in lines for word in line)
    check("wrap: жодне слово не загубилося", rebuilt == richtext.plain(text))


def test_lessons_markup_is_balanced():
    leftovers = re.compile(r"\*\*|\[/?[xyzk]\]")
    tokens_ok = re.compile(r"^(tool|menu|op|prop|template|panel|hud|area|gizmo|ptab):\S+$")
    for lesson in course.available_lessons():
        for i, step in enumerate(lesson["steps"], start=1):
            where = f"{lesson['id']} крок {i}"
            for field, text in (("task", step["task"]), ("tip", step.get("tip", "")),
                                ("hint", step.get("check", {}).get("hint") or "")):
                check(f"{where}: {field} без зайвих позначок", not leftovers.search(richtext.plain(text)))
            for token in step.get("highlight", []):
                check(f"{where}: ціль {token}", bool(tokens_ok.match(token)))


for test in (test_parse_styles, test_plain, test_wrap_keeps_punctuation_with_word, test_wrap_respects_width,
             test_lessons_markup_is_balanced):
    test()

print("EDU_RICHTEXT", "FAILED" if failures else "PASSED", len(failures))
sys.exit(1 if failures else 0)
