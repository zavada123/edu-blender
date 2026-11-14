"""Готує файли додатка для браузерної сторінки web/.

Створює web/edu_lessons.zip (пакет edu_lessons/ для --python-expr) і
web/lessons.json (список уроків для стартової сторінки).
"""

import json
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "edu_lessons"
WEB = ROOT / "web"


def build_zip() -> pathlib.Path:
    target = WEB / "edu_lessons.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACKAGE.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, path.relative_to(ROOT).as_posix())
    return target


def build_lessons() -> pathlib.Path:
    lessons = []
    for path in sorted((PACKAGE / "lessons").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        lessons.append({"id": path.stem, "title": data["title"], "steps": len(data["steps"])})
    target = WEB / "lessons.json"
    target.write_text(json.dumps(lessons, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    for built in (build_zip(), build_lessons()):
        print("built", built.relative_to(ROOT), built.stat().st_size, "bytes")
