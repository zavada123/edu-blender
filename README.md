# edu-blender

Покрокові уроки 3D-моделювання у **справжньому Blender** для 9 класу (§4.2–4.5) на eduprostir.com.
Додаток ховає зайві меню й кнопки і відкриває інструменти по одному, з поясненням, що кожен робить.

## Що всередині

- `edu_lessons/` — розширення Blender 5.3 (Python):
  - `lock.py` — спрощений інтерфейс: 3D-вид на весь екран, власні верхня панель і заголовок, лише дозволені інструменти на панелі ліворуч, вимкнені гарячі клавіші закритих операцій, сховані вкладки бічної панелі. Режим вчителя повертає повний Blender.
  - `course.py`, `checks.py` — перебіг уроку і перевірки кроків (виділення, огляд, наявність тіла, вид збоку, розташування/обертання/масштаб).
  - `ui.py` — панель «Урок», меню «Додати» і «Вигляд», власна панель «Трансформація».
  - `bridge.py` — події для сторінки: рядок `EDU_EVENT {json}` у stdout (у браузерній збірці це `Module.print`).
  - `lessons/*.json` — уроки. Новий урок додається без програмування.
- `tools/gui_walkthrough.py` — прохід уроку у вікні Blender зі знімками екрана.
- `tools/lock_test.py` — перевірка, що Tab/G заблоковані в уроці і працюють у режимі вчителя.

## Спробувати в настільному Blender 5.3

1. Зібрати zip: `blender --command extension build --source-dir edu_lessons --output-dir dist`.
2. Blender → Edit → Preferences → Get Extensions → ⌄ → Install from Disk → `dist/edu_lessons-0.1.0.zip`.
3. У 3D-виді натиснути N, вкладка «Урок», вибрати урок.

## Браузерна збірка

Працює поверх [heyputer/blender-wasm](https://github.com/heyputer/blender-wasm) (Blender 5.3, WebAssembly + WebGPU, GPL).
Сторінка передає `--python-expr` із кодом додатка і змінну `EDU_LESSON`; рядки `EDU_EVENT` повертаються в `Module.print`.
Сторінці потрібні заголовки `Cross-Origin-Opener-Policy: same-origin` і `Cross-Origin-Embedder-Policy: require-corp`.

## Тестова сторінка (GitHub Pages)

`web/` — сторінка, яка завантажує браузерний Blender і запускає урок: `index.html` показує список уроків,
`index.html?lesson=lesson1` відкриває урок (`&step=N` — з певного кроку).
`boot.js` передає додаток через `--python-expr`, ловить рядки `EDU_EVENT` і пересилає їх сайту
через `BroadcastChannel("edu-blender")` та `window.opener.postMessage`.
GitHub Pages не ставить заголовки COOP/COEP, тому їх додає `coi-serviceworker.js`.

Локально: `python tools/build_web.py && cd web && python -m http.server 8000`.
Розгортання: `.github/workflows/pages.yml` (Settings → Pages → Source: GitHub Actions).
Сторонні файли й ліцензії: `web/NOTICE.md`.

## Перевірки

```bash
# Linux без екрана: Xvfb :99 &, далі
XDG_RUNTIME_DIR=/tmp/xdg DISPLAY=:99 EDU_WALK=lesson1 EDU_SHOTS=out \
  blender --factory-startup -p 0 0 1400 860 --python tools/gui_walkthrough.py
XDG_RUNTIME_DIR=/tmp/xdg DISPLAY=:99 \
  blender --factory-startup --enable-event-simulate -p 0 0 1400 860 --python tools/lock_test.py
```

Ліцензія: GPL-3.0-or-later (як і Blender).
