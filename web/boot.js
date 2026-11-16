// Запуск браузерного Blender з додатком уроків.
//
// 1. ?lesson=<id> вибирає урок; без нього показуємо список уроків.
// 2. Додаток (edu_lessons.zip) передаємо Blender через --python-expr,
//    урок через змінну середовища EDU_LESSON.
// 3. Рядки "EDU_EVENT {json}" зі stdout Blender показуємо на смужці прогресу
//    і пересилаємо сайту: BroadcastChannel("edu-blender") і window.opener.postMessage.
(function () {
  "use strict";

  const params = new URLSearchParams(location.search);
  const lessonId = params.get("lesson");
  const stepParam = params.get("step");
  const channel = "BroadcastChannel" in window ? new BroadcastChannel("edu-blender") : null;
  const badge = document.getElementById("edu-progress");
  const finishCard = document.getElementById("edu-finish");
  const DONE_KEY = "edu-blender-done";
  let allLessons = [];
  let currentLesson = null;

  // Пройдені уроки пам'ятаємо в цьому браузері: у списку вони з галочкою.
  function loadDone() {
    try {
      const value = JSON.parse(localStorage.getItem(DONE_KEY) || "[]");
      return Array.isArray(value) ? value.filter(isValidId) : [];
    } catch (err) {
      return [];
    }
  }

  function markDone(id) {
    try {
      const done = loadDone();
      if (!done.includes(id)) localStorage.setItem(DONE_KEY, JSON.stringify(done.concat(id)));
    } catch (err) {
      // Приватне вікно чи заборонене сховище: урок пройдено, лише галочки в списку не буде.
    }
  }

  function lessonHref(id) {
    return "?lesson=" + encodeURIComponent(id);
  }

  // Що робити після уроку: наступний урок або, після останнього, список уроків.
  function showFinish() {
    if (!currentLesson) return;
    markDone(currentLesson.id);
    const index = allLessons.findIndex((item) => item.id === currentLesson.id);
    const next = index >= 0 ? allLessons[index + 1] : undefined;
    const text = document.getElementById("edu-finish-text");
    const nextLink = document.getElementById("edu-finish-next");
    if (next) {
      text.textContent = "Далі: " + next.title + ".";
      nextLink.href = lessonHref(next.id);
      nextLink.textContent = "Наступний урок";
      nextLink.hidden = false;
    } else {
      text.textContent = "Це був останній урок. Курс пройдено!";
      nextLink.hidden = true;
    }
    finishCard.hidden = false;
    badge.hidden = true;
  }

  function isValidId(value) {
    return /^[a-z0-9_]{1,40}$/.test(value || "");
  }

  async function loadLessons() {
    const response = await fetch("lessons.json", { cache: "no-cache" });
    if (!response.ok) throw new Error("lessons.json: " + response.status);
    return response.json();
  }

  function stepsWord(n) {
    const tail = n % 100;
    if (tail >= 11 && tail <= 14) return "кроків";
    if (n % 10 === 1) return "крок";
    if (n % 10 >= 2 && n % 10 <= 4) return "кроки";
    return "кроків";
  }

  function showLessonList(lessons) {
    const list = document.getElementById("lesson-list");
    const done = loadDone();
    const nextId = (lessons.find((item) => !done.includes(item.id)) || {}).id;
    for (const lesson of lessons) {
      const link = document.createElement("a");
      link.className = "lesson-link";
      if (done.includes(lesson.id)) link.classList.add("done");
      if (lesson.id === nextId && done.length > 0) link.classList.add("next");
      link.href = lessonHref(lesson.id);
      link.textContent = (done.includes(lesson.id) ? "✓ " : "") + lesson.title;
      const steps = document.createElement("span");
      steps.textContent = lesson.steps + " " + stepsWord(lesson.steps);
      link.appendChild(steps);
      list.appendChild(link);
    }
    list.hidden = false;
    document.getElementById("stage-card").hidden = true;
  }

  function toBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = "";
    for (let i = 0; i < bytes.length; i += 0x8000) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    }
    return btoa(binary);
  }

  function pythonBootstrap(zipBase64) {
    return [
      "import base64, io, sys, zipfile",
      "import bpy",
      "bpy.context.preferences.view.show_splash = False",
      "zipfile.ZipFile(io.BytesIO(base64.b64decode('" + zipBase64 + "'))).extractall('/tmp/edu')",
      "sys.path.insert(0, '/tmp/edu')",
      "import edu_lessons",
      "edu_lessons.register()",
      "print('EDU_EVENT {\"type\": \"addon_ready\"}', flush=True)",
    ].join("\n");
  }

  function publish(event) {
    const message = Object.assign({ source: "edu-blender" }, event);
    if (channel) channel.postMessage(message);
    if (window.opener) window.opener.postMessage(message, "*");
    window.dispatchEvent(new CustomEvent("edu-event", { detail: message }));
  }

  function showBadge(event) {
    if (event.type === "lesson_start") {
      badge.textContent = "Крок 1 з " + event.steps;
    } else if (event.type === "step_done") {
      badge.textContent = event.step >= event.of ? "Усі кроки виконано" : "Крок " + (event.step + 1) + " з " + event.of;
    } else if (event.type === "lesson_done") {
      showFinish();
      return;
    } else {
      return;
    }
    badge.hidden = false;
  }

  function handleLine(text) {
    if (typeof text !== "string") return;
    const start = text.indexOf("EDU_EVENT ");
    if (start < 0) return;
    try {
      const event = JSON.parse(text.slice(start + "EDU_EVENT ".length));
      showBadge(event);
      publish(event);
    } catch (err) {
      // Рядок обрізано або це не JSON: подію пропускаємо, Blender працює далі.
      console.warn("EDU_EVENT parse error", err);
    }
  }

  function watchConsole() {
    const original = console.log.bind(console);
    console.log = function (...args) {
      if (args.length) handleLine(args[0]);
      original(...args);
    };
  }

  function startBlender(zipBase64, lesson) {
    const env = { EDU_LESSON: lesson.id };
    if (stepParam && /^\d{1,2}$/.test(stepParam)) env.EDU_STEP = stepParam;
    window.__BARGS = ["--python-expr", pythonBootstrap(zipBase64)];
    window.__CAPENV = env;
    watchConsole();
    const script = document.createElement("script");
    script.type = "module";
    script.src = "assets/loader.js";
    document.body.appendChild(script);
  }

  function fail(message) {
    const status = document.getElementById("splash-status");
    status.textContent = message;
    status.classList.add("error");
  }

  async function main() {
    if (!window.crossOriginIsolated) {
      // coi-serviceworker перезавантажить сторінку. Якщо ні, браузер застарий.
      setTimeout(() => {
        if (!window.crossOriginIsolated) fail("Браузер не підтримує потрібний режим. Відкрий сторінку в новому Chrome або Edge.");
      }, 4000);
      return;
    }
    const lessons = await loadLessons();
    allLessons = lessons;
    const lesson = isValidId(lessonId) && lessons.find((item) => item.id === lessonId);
    if (!lesson) {
      showLessonList(lessons);
      return;
    }
    currentLesson = lesson;
    const title = document.getElementById("lesson-title");
    title.textContent = lesson.title;
    title.hidden = false;
    document.title = lesson.title + " · Едупростір";
    const response = await fetch("edu_lessons.zip", { cache: "no-cache" });
    if (!response.ok) throw new Error("edu_lessons.zip: " + response.status);
    startBlender(toBase64(await response.arrayBuffer()), lesson);
  }

  main().catch((err) => fail("Не вдалося запустити урок: " + err.message));
})();
