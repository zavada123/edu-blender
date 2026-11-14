"""Події для сторінки сайту.

У браузерній збірці Blender кожен рядок stdout потрапляє в Module.print на сторінці,
тож рядок із префіксом EDU_EVENT і JSON після нього сторінка розбирає як подію.
У настільному Blender ці рядки просто видно в консолі.
"""

import json

PREFIX = "EDU_EVENT "


def emit(kind: str, **data) -> None:
    payload = {"type": kind, **data}
    print(PREFIX + json.dumps(payload, ensure_ascii=False), flush=True)
