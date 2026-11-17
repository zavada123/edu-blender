// Клавіші браузера на сторінці Blender: node --test tools/browser_guard_test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const { isBrowserShortcut, installBrowserGuard } = require("../web/browser-guard.js");

const press = (code, key, mods = {}) => ({ code, key, ctrl: false, shift: false, alt: false, ...mods });

test("Ctrl+S, Ctrl+P, Ctrl+O and Ctrl+U are browser shortcuts", () => {
  for (const code of ["KeyS", "KeyP", "KeyO", "KeyU"]) assert.equal(isBrowserShortcut(press(code, code.slice(3).toLowerCase(), { ctrl: true })), true, code);
});

test("F12, F5 and the developer tools keys are browser shortcuts, F11 is not", () => {
  assert.equal(isBrowserShortcut(press("F12", "F12")), true);
  assert.equal(isBrowserShortcut(press("F5", "F5")), true);
  assert.equal(isBrowserShortcut(press("KeyI", "I", { ctrl: true, shift: true })), true);
  assert.equal(isBrowserShortcut(press("F11", "F11")), false);
});

test("Blender keys without a browser action stay free", () => {
  assert.equal(isBrowserShortcut(press("KeyZ", "z", { ctrl: true })), false);
  assert.equal(isBrowserShortcut(press("KeyC", "c", { ctrl: true })), false);
  assert.equal(isBrowserShortcut(press("KeyG", "g")), false);
  assert.equal(isBrowserShortcut(press("Tab", "Tab")), false);
});

const fakeWindow = () => {
  const listeners = {};
  const canvas = { id: "canvas" };
  return {
    canvas,
    listeners,
    document: { getElementById: (id) => (id === "canvas" ? canvas : null) },
    addEventListener: (type, fn) => { listeners[type] = fn; },
    removeEventListener: (type) => { delete listeners[type]; },
  };
};
const event = (fields) => ({ ...fields, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } });

test("the guard cancels only the browser action of Ctrl+S and F12, not the event", () => {
  const win = fakeWindow();
  installBrowserGuard(win);
  const save = event({ key: "s", code: "KeyS", ctrlKey: true });
  win.listeners.keydown(save);
  assert.equal(save.defaultPrevented, true);
  const render = event({ key: "F12", code: "F12" });
  win.listeners.keydown(render);
  assert.equal(render.defaultPrevented, true);
  const undo = event({ key: "z", code: "KeyZ", ctrlKey: true });
  win.listeners.keydown(undo);
  assert.equal(undo.defaultPrevented, false);
});

test("the browser menu does not open on the Blender canvas", () => {
  const win = fakeWindow();
  installBrowserGuard(win);
  const onCanvas = event({ target: win.canvas });
  win.listeners.contextmenu(onCanvas);
  assert.equal(onCanvas.defaultPrevented, true);
  const elsewhere = event({ target: {} });
  win.listeners.contextmenu(elsewhere);
  assert.equal(elsewhere.defaultPrevented, false);
});

test("a dropped file does not replace the page", () => {
  const win = fakeWindow();
  installBrowserGuard(win);
  const drop = event({ dataTransfer: { types: ["Files"] } });
  win.listeners.drop(drop);
  assert.equal(drop.defaultPrevented, true);
});

test("the remover takes the listeners off", () => {
  const win = fakeWindow();
  installBrowserGuard(win)();
  assert.deepEqual(Object.keys(win.listeners), []);
});
