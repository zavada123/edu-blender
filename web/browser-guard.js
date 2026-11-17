// Клавіші браузера на сторінці Blender: Ctrl+S, F12 та інші мають іти в Blender, а не в браузер.
//
// Чому окремо від сайту: на eduprostir.com тренажери захищає TrainerGuard (mriya-study, lib/browser-guard.ts),
// а сторінка /blender/ відкривається сама, без нього. До того ж браузерний Blender працює в окремому потоці:
// Emscripten пересилає натискання в потік Blender і не скасовує дію браузера (`e.preventDefault()` у
// blender.js стоїть лише в гілці без потоку). Тому Ctrl+S зберігав сторінку, а F12 відкривав інструменти розробника.
//
// Тут скасовуємо лише дію браузера: подія далі йде в Blender, і він сам робить збереження, рендер тощо.
// Ctrl+W, Ctrl+T, Ctrl+N і Ctrl+Tab сторінка зупинити не може. Інструменти розробника лишаються в меню браузера.
(function (root) {
  "use strict";

  // Ті самі клавіші, що й у lib/browser-guard.ts сайту.
  /** Ctrl+літера: закладка, адресний рядок, пошук, історія, завантаження, відкрити, друк, оновити, зберегти, код. */
  const CTRL_CODES = new Set(["KeyD", "KeyE", "KeyF", "KeyG", "KeyH", "KeyJ", "KeyK", "KeyL", "KeyO", "KeyP", "KeyR", "KeyS", "KeyU"]);
  /** Ctrl+Shift+літера: інструменти розробника (I, J, C), очищення історії, закладки, жорстке оновлення. */
  const CTRL_SHIFT_CODES = new Set(["KeyI", "KeyJ", "KeyC", "KeyB", "KeyO", "KeyR", "Delete"]);
  /** Alt+стрілка й Alt+Home: назад, уперед і домашня сторінка. */
  const ALT_CODES = new Set(["ArrowLeft", "ArrowRight", "Home"]);
  /** F11 лишається: вікно браузера на весь екран допомагає працювати в Blender. */
  const FREE_FUNCTION_KEYS = new Set(["F11"]);

  function isBrowserShortcut(press) {
    if (/^F\d{1,2}$/.test(press.key)) return !FREE_FUNCTION_KEYS.has(press.key);
    if (press.ctrl && press.shift) return CTRL_SHIFT_CODES.has(press.code);
    if (press.ctrl && !press.alt) return CTRL_CODES.has(press.code);
    if (press.alt && !press.ctrl) return ALT_CODES.has(press.code);
    return false;
  }

  function pressOf(event) {
    return { key: event.key, code: event.code, ctrl: event.ctrlKey || event.metaKey, shift: event.shiftKey, alt: event.altKey };
  }

  const carriesFiles = (event) => Boolean(event.dataTransfer && Array.from(event.dataTransfer.types).includes("Files"));

  /** Скасовує дії браузера на всій сторінці `win`: тут увесь екран і є тренажером. Повертає функцію, що знімає слухачів. */
  function installBrowserGuard(win) {
    const canvas = () => win.document.getElementById("canvas");
    // Фаза перехоплення на window: спрацьовує першою, і жоден обробник не зупинить подію раніше.
    const onKeyDown = (event) => {
      if (isBrowserShortcut(pressOf(event))) event.preventDefault();
    };
    // Права кнопка в Blender відкриває його власне меню, а не меню браузера.
    const onContextMenu = (event) => {
      if (event.target === canvas()) event.preventDefault();
    };
    // Файл, кинутий на сторінку, браузер відкрив би замість Blender, і незбережена робота пропала б.
    const onDragOver = (event) => {
      if (!carriesFiles(event)) return;
      event.preventDefault();
      if (event.dataTransfer) event.dataTransfer.dropEffect = "none";
    };
    const onDrop = (event) => {
      if (carriesFiles(event)) event.preventDefault();
    };
    win.addEventListener("keydown", onKeyDown, true);
    win.addEventListener("contextmenu", onContextMenu, true);
    win.addEventListener("dragover", onDragOver);
    win.addEventListener("drop", onDrop);
    return () => {
      win.removeEventListener("keydown", onKeyDown, true);
      win.removeEventListener("contextmenu", onContextMenu, true);
      win.removeEventListener("dragover", onDragOver);
      win.removeEventListener("drop", onDrop);
    };
  }

  if (typeof module === "object" && module.exports) module.exports = { isBrowserShortcut, installBrowserGuard };
  else installBrowserGuard(root);
})(typeof window === "undefined" ? globalThis : window);
