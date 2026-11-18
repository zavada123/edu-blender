# edu-blender

Покрокові уроки 3D-моделювання у **справжньому Blender** для 9 класу (§4.2–4.5) на eduprostir.com.
Додаток ховає зайві меню й кнопки і відкриває інструменти по одному, з поясненням, що кожен робить.

## Що всередині

- `edu_lessons/` — розширення Blender 5.3 (Python):
  - `lock.py` — урок у повному інтерфейсі Blender: усе на своїх місцях, але кнопки закритих операцій сірі й не натискаються (обгортка `draw()` усіх Python-меню, заголовків і панелей), закриті інструменти на панелі ліворуч вимкнені, гарячі клавіші закритих операцій не працюють, Outliner і Timeline притінені. Кнопку, яку треба натиснути, підсвічено (`highlight` у кроці уроку). Клавіші 1/3/7/5 верхнього ряду дають вигляди. Режим вчителя повертає звичайний Blender.
  - `coach.py` — бульбашка з завданням і стрілкою біля потрібної кнопки просто в 3D-виді.
  - `overlay.py` — жовті рамки навколо цілей поза полотном 3D-виду: ярлик **Item** бічної панелі (а коли вкладку відкрито, потрібне поле Transform) і вкладки редактора властивостей (`ptab:OBJECT`, `ptab:MATERIAL`). Положення рахується з розкладки Blender, масштабу інтерфейсу і прокрутки, тож рамка стоїть на місці за будь-якого розміру вікна.
  - `richtext.py` — розмітка тексту завдань: `**Item**` назва кнопки чи поля (жирний жовтий), `[x]червону стрілку[/x]`, `[y]…[/y]`, `[z]…[/z]` колір осі, як у Blender, `[k]Ctrl+S[/k]` клавіша. Бульбашка малює кольором, панель «Урок» показує текст без розмітки.
  - `features.py` — що саме відкриває кожна можливість уроку (оператори, меню, інструменти, панелі, поля).
  - `course.py`, `checks.py`, `checks_extra.py` — перебіг уроку і перевірки кроків: виділення, огляд, вид збоку, розташування/обертання/масштаб, рендер, збереження, експорт STL, копії й об'єднання, режим редагування, видавлювання, матеріали, ключові кадри, відтворення.
  - `ui.py` — панель «Урок» і власна панель Transform (вбудовану, написану на C, з Python не вимкнути).
  - `bridge.py` — події для сторінки: рядок `EDU_EVENT {json}` у stdout (у браузерній збірці це `Module.print`).
  - `lessons/*.json` — уроки. Новий урок додається без програмування. Зараз їх 7:
    1. Знайомство зі сценою (6 кроків). 2. Збираємо брелок (4). 3. Вигляди, камера і рендер (7).
    4. Копії та об'єднання (7). 5. Режим редагування: піраміда (7). 6. Матеріали: колір і метал (8).
    7. Анімація і файл для друку (7).
- `tools/gui_walkthrough.py` — прохід уроку у вікні Blender зі знімками екрана.
- `tools/hint_shots.py` — знімки підказки кожного кроку (бульбашка, стрілка, рамки) для перевірки на різних розмірах вікна й масштабах (`EDU_UI_SCALE`).
- `tools/lock_test.py` — перевірка, що Tab/G заблоковані в уроці, клавіша 1 дає вигляд спереду, а в режимі вчителя все працює.

## Спробувати в настільному Blender 5.3

1. Зібрати zip: `blender --command extension build --source-dir edu_lessons --output-dir dist`.
2. Blender → Edit → Preferences → Get Extensions → ⌄ → Install from Disk → `dist/edu_lessons-0.1.0.zip`.
3. У 3D-виді натиснути N, вкладка «Урок», вибрати урок.

## Браузерна збірка

Працює поверх [heyputer/blender-wasm](https://github.com/heyputer/blender-wasm) (Blender 5.3, WebAssembly + WebGPU, GPL-2.0-or-later).
Сторінка передає `--python-expr` із кодом додатка і змінну `EDU_LESSON`; рядки `EDU_EVENT` повертаються в `Module.print`.
Сторінці потрібні заголовки `Cross-Origin-Opener-Policy: same-origin` і `Cross-Origin-Embedder-Policy: require-corp`.

## Тестова сторінка (GitHub Pages)

`web/` — сторінка, яка завантажує браузерний Blender і запускає урок: `index.html` показує список уроків,
`index.html?lesson=lesson1` відкриває урок (`&step=N` — з певного кроку), `index.html?lesson=free` — вільний режим: повний Blender без уроку.
`boot.js` передає додаток через `--python-expr`, ловить рядки `EDU_EVENT` і пересилає їх сайту
через `BroadcastChannel("edu-blender")` та `window.opener.postMessage`.
GitHub Pages не ставить заголовки COOP/COEP, тому їх додає `coi-serviceworker.js`.
`browser-guard.js` віддає Blender клавіші, які інакше забрав би браузер: Ctrl+S зберігає проєкт, а не сторінку, F12 робить рендер, а не відкриває інструменти розробника (так само Ctrl+P/O/F/U, F1–F10, Ctrl+Shift+I і права кнопка на полотні). Браузерний Blender працює в окремому потоці, і Emscripten сам дію браузера не скасовує.

Пройдені уроки мають галочку в списку. Гість пам'ятає їх лише в браузері (`localStorage`, `edu-blender-done`).
На сайті (`/blender/`) учень, що увійшов, має свій список (`edu-blender-done:<id учня>`) і той самий список в акаунті:
`GET`/`PUT /api/student/trainer-solved` з `trainer: "blender"`. Так пройдені уроки бачить учитель класу.
Список гостя в акаунт не йде. На GitHub Pages API немає, і сторінка працює як для гостя.

Локально: `python tools/build_web.py && cd web && python -m http.server 8000`.
Розгортання: `.github/workflows/pages.yml` (Settings → Pages → Source: GitHub Actions).
Сторонні файли й ліцензії: `web/NOTICE.md`.

## Перевірки

```bash
node --test tools/browser_guard_test.js   # клавіші браузера на сторінці
# Linux без екрана: Xvfb :99 &, далі
XDG_RUNTIME_DIR=/tmp/xdg DISPLAY=:99 EDU_WALK=lesson1 EDU_SHOTS=out \
  blender --factory-startup -p 0 0 1400 860 --python tools/gui_walkthrough.py
XDG_RUNTIME_DIR=/tmp/xdg DISPLAY=:99 \
  blender --factory-startup --enable-event-simulate -p 0 0 1400 860 --python tools/lock_test.py
```

## Ліцензія

Код додатка й сторінки: GPL-3.0-or-later, як і Blender ([LICENSE](LICENSE)). Це означає, що змінену версію можна поширювати лише під тією ж ліцензією і разом із вихідним кодом.
Сторонні файли мають власні ліцензії: браузерний Blender з heyputer/blender-wasm — GPL-2.0-or-later, coi-serviceworker — MIT (див. [`web/NOTICE.md`](web/NOTICE.md)).

Назва й логотип Blender — торгові марки Blender Foundation. Цей проєкт не пов'язаний з Blender Foundation і не є офіційним продуктом Blender.
