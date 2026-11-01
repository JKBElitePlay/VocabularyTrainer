const $ = (selector) => document.querySelector(selector);
const state = { folders: [], folderId: null, sessionId: null, mode: null, direction: "de-en", targetQuestions: 10, totalQuestions: 0, question: null, helpUsed: false, matched: new Set(), selectedLeft: null, selectedRight: null };
const practiceSettingsKey = "vokabel-freunde.practice-settings";
let savedPracticeSettings = null;

try {
  const saved = localStorage.getItem(practiceSettingsKey);
  savedPracticeSettings = saved ? JSON.parse(saved) : null;
} catch (error) {
  notice(`Die gespeicherten Lerneinstellungen konnten nicht geladen werden: ${error.message}`, "danger");
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = `Anfrage fehlgeschlagen (${response.status})`;
    try { message = (await response.json()).detail || message; } catch {}
    throw new Error(message);
  }
  if (response.status === 204) return null;
  return response.json();
}

function escapeHtml(value = "") {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[character]);
}

function vocabularyCountLabel(count) {
  return `${count} ${count === 1 ? "Vokabel" : "Vokabeln"}`;
}

function savePracticeSettings() {
  const folderId = Number($("#practice-folder").value) || null;
  savedPracticeSettings = {
    folderId,
    gameMode: $("#game-mode").value,
    answerDirection: $("#answer-direction").value,
    targetQuestions: Number($("#question-count").value),
    onlyBelow90Percent: $("#only-below-90-percent").checked,
    maxCorrectPercent: Number($("#max-correct-percent").value),
    categoryFolderId: folderId,
    categories: [...document.querySelectorAll(".training-category:checked")]
      .map((checkbox) => checkbox.value),
    includeUncategorized: $("#include-uncategorized")?.checked || false,
  };
  try {
    localStorage.setItem(practiceSettingsKey, JSON.stringify(savedPracticeSettings));
  } catch (error) {
    notice(`Die Lerneinstellungen konnten nicht gespeichert werden: ${error.message}`, "danger");
  }
}

function notice(message, kind = "success") {
  const element = $("#notice");
  element.className = `alert alert-${kind}`;
  element.textContent = message;
  window.setTimeout(() => element.classList.add("d-none"), 4500);
}

function showView(name) {
  document.querySelectorAll(".view").forEach((view) => view.classList.add("d-none"));
  $(`#${name}-view`)?.classList.remove("d-none");
  if (name === "practice") loadPracticeFolders();
  if (name === "statistics") loadStatistics();
}

document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => showView(button.dataset.view));
});

async function loadFolders() {
  state.folders = await api("/api/folders");
  const cards = state.folders.map((folder) => `
    <div class="col-md-6 col-lg-4">
      <div class="folder-card h-100">
        <button class="btn p-0 text-start w-100 open-folder" data-id="${folder.id}">
          <span class="fs-2">📘</span><h3 class="h5 mt-2 mb-1">${escapeHtml(folder.name)}</h3>
          <span class="text-secondary">${vocabularyCountLabel(folder.vocabulary_count)}</span>
        </button>
        <div class="d-flex gap-2 mt-3">
          <button class="btn btn-sm btn-outline-primary open-folder" data-id="${folder.id}">Öffnen</button>
          <button class="btn btn-sm btn-outline-danger remove-folder" data-id="${folder.id}">Löschen</button>
        </div>
      </div>
    </div>`).join("");
  $("#folders-list").innerHTML = cards || '<div class="col-12"><p class="text-secondary">Noch keine Mappen angelegt.</p></div>';
  $("#home-folders").innerHTML = state.folders.slice(0, 6).map((folder) => `
    <div class="col-sm-6 col-lg-4"><button class="folder-card w-100 open-folder" data-id="${folder.id}">
      <span class="fs-3">📘</span><strong class="d-block mt-2">${escapeHtml(folder.name)}</strong>
      <span class="text-secondary">${vocabularyCountLabel(folder.vocabulary_count)}</span>
    </button></div>`).join("") || '<div class="col-12"><p class="text-secondary">Lege deine erste Mappe an.</p></div>';
  document.querySelectorAll(".open-folder").forEach((button) => button.addEventListener("click", () => selectFolder(Number(button.dataset.id))));
  document.querySelectorAll(".remove-folder").forEach((button) => button.addEventListener("click", () => deleteFolder(Number(button.dataset.id))));
}

async function selectFolder(id) {
  const folder = state.folders.find((item) => item.id === id);
  if (!folder) return;
  state.folderId = id;
  $("#selected-folder-name").textContent = folder.name;
  $("#folder-detail").classList.remove("d-none");
  await loadWords();
  showView("folders");
  $("#folder-detail").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function loadWords() {
  if (!state.folderId) return;
  const words = await api(`/api/folders/${state.folderId}/vocabulary`);
  $("#word-list").innerHTML = words.map((word) => `
    <tr>
      <td>${escapeHtml(word.german)}</td><td>${escapeHtml(word.english)}</td>
      <td>${escapeHtml(word.category || "–")}</td>
      <td>${word.correct_count} / ${word.wrong_count}</td>
      <td class="text-end text-nowrap">
        <button class="btn btn-sm btn-outline-secondary edit-word" data-id="${word.id}">Bearbeiten</button>
        <button class="btn btn-sm btn-outline-danger delete-word" data-id="${word.id}">Löschen</button>
      </td>
    </tr>`).join("");
  $("#empty-words").classList.toggle("d-none", words.length > 0);
  document.querySelectorAll(".edit-word").forEach((button) => button.addEventListener("click", () => editWord(Number(button.dataset.id))));
  document.querySelectorAll(".delete-word").forEach((button) => button.addEventListener("click", () => deleteWord(Number(button.dataset.id))));
  await loadFolders();
  const selected = state.folders.find((item) => item.id === state.folderId);
  if (selected) $("#selected-folder-name").textContent = selected.name;
}

function openDialog(title, fields, onSave) {
  const dialog = document.createElement("dialog");
  dialog.className = "border-0 rounded-4 p-4 shadow";
  dialog.style.width = "min(560px, 94vw)";
  dialog.innerHTML = `<form method="dialog">
    <h2 class="h4 mb-3">${escapeHtml(title)}</h2>
    ${fields.map((field) => `<label class="form-label w-100">${escapeHtml(field.label)}
      ${field.multiline
        ? `<textarea class="form-control mb-3" name="${field.name}" maxlength="${field.max || 2000}" rows="3">${escapeHtml(field.value || "")}</textarea>`
        : `<input class="form-control mb-3" name="${field.name}" maxlength="${field.max || 250}" value="${escapeHtml(field.value || "")}" ${field.required ? "required" : ""}>`}
    </label>`).join("")}
    <div class="d-flex justify-content-end gap-2"><button class="btn btn-outline-secondary" value="cancel">Abbrechen</button>
    <button class="btn btn-primary" value="save">Speichern</button></div>
  </form>`;
  document.body.append(dialog);
  dialog.addEventListener("close", async () => {
    if (dialog.returnValue === "save") {
      const data = Object.fromEntries(new FormData(dialog.querySelector("form")).entries());
      try { await onSave(data); } catch (error) { notice(error.message, "danger"); }
    }
    dialog.remove();
  });
  dialog.showModal();
}

$("#add-folder").addEventListener("click", () => openDialog("Neue Vokabelmappe", [
  { name: "name", label: "Name", required: true, max: 120 }
], async (data) => {
  await api("/api/folders", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
  await loadFolders();
  notice("Deine neue Mappe ist bereit!");
}));

$("#rename-folder").addEventListener("click", () => {
  const folder = state.folders.find((item) => item.id === state.folderId);
  openDialog("Mappe umbenennen", [{ name: "name", label: "Name", value: folder?.name, required: true, max: 120 }], async (data) => {
    await api(`/api/folders/${state.folderId}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
    await loadFolders();
    $("#selected-folder-name").textContent = data.name;
  });
});

async function deleteFolder(id) {
  const folder = state.folders.find((item) => item.id === id);
  if (!window.confirm(`"${folder?.name}" und alle Vokabeln wirklich löschen?`)) return;
  try {
    await api(`/api/folders/${id}`, { method: "DELETE" });
    if (state.folderId === id) {
      state.folderId = null;
      $("#folder-detail").classList.add("d-none");
    }
    await loadFolders();
    notice("Mappe gelöscht.");
  } catch (error) { notice(error.message, "danger"); }
}

$("#add-word").addEventListener("click", () => editWord(null));

async function editWord(id) {
  let word = {};
  if (id) word = (await api(`/api/folders/${state.folderId}/vocabulary`)).find((item) => item.id === id) || {};
  openDialog(id ? "Vokabel bearbeiten" : "Neue Vokabel", [
    { name: "german", label: "Deutsch", value: word.german, required: true },
    { name: "english", label: "Englisch", value: word.english, required: true },
    { name: "category", label: "Kategorie", value: word.category, max: 120 },
    { name: "hint", label: "Hinweis", value: word.hint, max: 500 },
    { name: "example_sentence", label: "Beispielsatz", value: word.example_sentence, multiline: true }
  ], async (data) => {
    await api(id ? `/api/vocabulary/${id}` : `/api/folders/${state.folderId}/vocabulary`, {
      method: id ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    });
    await loadWords();
    notice(id ? "Vokabel gespeichert." : "Vokabel hinzugefügt.");
  });
}

async function deleteWord(id) {
  if (!window.confirm("Diese Vokabel wirklich löschen?")) return;
  try {
    await api(`/api/vocabulary/${id}`, { method: "DELETE" });
    await loadWords();
    notice("Vokabel gelöscht.");
  } catch (error) { notice(error.message, "danger"); }
}

$("#export-csv").addEventListener("click", () => {
  window.location.href = `/api/folders/${state.folderId}/export`;
});

$("#csv-file").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    const form = new FormData();
    form.append("file", file);
    const preview = await api(`/api/folders/${state.folderId}/import/preview`, { method: "POST", body: form });
    const box = $("#import-preview");
    box.classList.remove("d-none");
    box.innerHTML = `<div class="alert alert-info">
      <strong>Vorschau:</strong> ${preview.found} Zeilen, ${preview.valid} importierbar,
      ${preview.duplicates} Duplikate, ${preview.errors.length} fehlerhaft.
      ${preview.errors.slice(0, 5).map((item) => `<div>Zeile ${item.line}: ${escapeHtml(item.message)}</div>`).join("")}
      <div class="mt-2 d-flex gap-2"><button id="confirm-import" class="btn btn-sm btn-primary">Importieren</button>
      <button id="cancel-import" class="btn btn-sm btn-outline-secondary">Abbrechen</button></div>
    </div>`;
    $("#confirm-import").addEventListener("click", async () => {
      const result = await api(`/api/folders/${state.folderId}/import`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ rows: preview.rows })
      });
      box.classList.add("d-none");
      await loadWords();
      notice(`${result.imported} Vokabeln importiert, ${result.duplicates} Duplikate übersprungen.`);
    });
    $("#cancel-import").addEventListener("click", () => box.classList.add("d-none"));
  } catch (error) { notice(error.message, "danger"); }
  event.target.value = "";
});

async function loadPracticeFolders() {
  await loadFolders();
  const select = $("#practice-folder");
  select.innerHTML = state.folders.map((folder) => `<option value="${folder.id}">${escapeHtml(folder.name)} (${vocabularyCountLabel(folder.vocabulary_count)})</option>`).join("");
  if (!state.folders.length) select.innerHTML = '<option value="">Erstelle zuerst eine Mappe</option>';
  const savedFolderExists = state.folders.some(
    (folder) => folder.id === savedPracticeSettings?.folderId
  );
  if (savedFolderExists) select.value = String(savedPracticeSettings.folderId);
  if (["de-en", "en-de", "flashcards", "matching"].includes(savedPracticeSettings?.gameMode)) {
    $("#game-mode").value = savedPracticeSettings.gameMode;
  }
  if (["de-en", "en-de"].includes(savedPracticeSettings?.answerDirection)) {
    $("#answer-direction").value = savedPracticeSettings.answerDirection;
  }
  if ([10, 20, 30, 50, 75, 100].includes(savedPracticeSettings?.targetQuestions)) {
    $("#question-count").value = String(savedPracticeSettings.targetQuestions);
  }
  $("#only-below-90-percent").checked = savedPracticeSettings?.onlyBelow90Percent === true;
  if (Number.isInteger(savedPracticeSettings?.maxCorrectPercent)
    && savedPracticeSettings.maxCorrectPercent >= 1
    && savedPracticeSettings.maxCorrectPercent <= 100) {
    $("#max-correct-percent").value = String(savedPracticeSettings.maxCorrectPercent);
  }
  $("#max-correct-percent-value").value = `${$("#max-correct-percent").value} %`;
  $("#correct-percent-setting").classList.toggle(
    "d-none", !$("#only-below-90-percent").checked
  );
  $("#question-count-setting").classList.remove("d-none");
  $("#flashcard-direction").classList.toggle("d-none", $("#game-mode").value !== "flashcards");
  $("#practice-categories").classList.toggle("d-none", !state.folders.length);
  if (state.folders.length) {
    await loadPracticeCategories();
    savePracticeSettings();
  }
}

$("#practice-folder").addEventListener("change", () => {
  loadPracticeCategories()
    .then(savePracticeSettings)
    .catch((error) => notice(error.message, "danger"));
});

async function loadPracticeCategories() {
  const folderId = Number($("#practice-folder").value);
  const options = $("#category-options");
  if (!folderId) {
    $("#practice-categories").classList.add("d-none");
    options.innerHTML = "";
    return;
  }
  const data = await api(`/api/folders/${folderId}/categories`);
  const restoreCategories = savedPracticeSettings?.categoryFolderId === folderId;
  const selectedCategories = new Set(
    restoreCategories && Array.isArray(savedPracticeSettings.categories)
      ? savedPracticeSettings.categories
      : data.categories.map((category) => category.name)
  );
  const categoryOptions = data.categories.map((category) => `
    <label class="form-check d-flex justify-content-between align-items-center">
      <span><input class="form-check-input training-category" type="checkbox" value="${escapeHtml(category.name)}" ${selectedCategories.has(category.name) ? "checked" : ""}>
      <span class="form-check-label ms-1">${escapeHtml(category.name)}</span></span>
      <span class="badge text-bg-light">${vocabularyCountLabel(category.count)}</span>
    </label>`).join("");
  const uncategorizedOption = data.uncategorized_count ? `
    <label class="form-check d-flex justify-content-between align-items-center">
      <span><input id="include-uncategorized" class="form-check-input" type="checkbox" ${!restoreCategories || savedPracticeSettings?.includeUncategorized ? "checked" : ""}>
      <span class="form-check-label ms-1">Ohne Kategorie</span></span>
      <span class="badge text-bg-light">${vocabularyCountLabel(data.uncategorized_count)}</span>
    </label>` : "";
  options.innerHTML = categoryOptions + uncategorizedOption
    || '<p class="small text-secondary mb-0">In dieser Mappe gibt es keine Vokabeln.</p>';
  options.querySelectorAll("input").forEach((checkbox) => {
    checkbox.addEventListener("change", () => {
      updateCategoryCount();
      savePracticeSettings();
    });
  });
  $("#practice-categories").classList.remove("d-none");
  updateCategoryCount();
}

function updateCategoryCount() {
  const count = state.folders
    .find((folder) => folder.id === Number($("#practice-folder").value))?.vocabulary_count || 0;
  const availableCount = [...$("#category-options").querySelectorAll("label")]
    .filter((label) => label.querySelector("input")?.checked)
    .reduce((sum, label) => sum + Number(label.querySelector(".badge").textContent.split(" ")[0]), 0);
  $("#category-count-summary").textContent =
    `${availableCount} von ${count} Vokabeln ausgewählt.`;
  $("#start-practice").disabled = availableCount === 0;
}

$("#game-mode").addEventListener("change", () => {
  $("#flashcard-direction").classList.toggle("d-none", $("#game-mode").value !== "flashcards");
  savePracticeSettings();
});

$("#answer-direction").addEventListener("change", savePracticeSettings);
$("#question-count").addEventListener("change", savePracticeSettings);
$("#only-below-90-percent").addEventListener("change", (event) => {
  $("#correct-percent-setting").classList.toggle("d-none", !event.target.checked);
  savePracticeSettings();
});
$("#max-correct-percent").addEventListener("input", (event) => {
  $("#max-correct-percent-value").value = `${event.target.value} %`;
  savePracticeSettings();
});

$("#start-practice").addEventListener("click", async () => {
  try {
    const folderId = Number($("#practice-folder").value);
    const mode = $("#game-mode").value;
    const direction = $("#answer-direction").value;
    const targetQuestions = Number($("#question-count").value);
    const categories = [...document.querySelectorAll(".training-category:checked")]
      .map((checkbox) => checkbox.value);
    const includeUncategorized = $("#include-uncategorized")?.checked || false;
    const session = await api("/api/training", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        folder_id: folderId,
        game_mode: mode,
        answer_direction: direction,
        target_questions: targetQuestions,
        only_below_90_percent: $("#only-below-90-percent").checked,
        max_correct_percent: Number($("#max-correct-percent").value),
        categories,
        include_uncategorized: includeUncategorized
      })
    });
    state.sessionId = session.id;
    state.mode = mode;
    state.direction = session.answer_direction;
    state.targetQuestions = session.target_questions;
    state.totalQuestions = session.total_questions;
    $("#practice-setup").classList.add("d-none");
    if (mode === "matching") await loadMatchingRound();
    else await loadQuestion();
  } catch (error) { notice(error.message, "danger"); }
});

async function loadQuestion() {
  state.question = await api(`/api/training/${state.sessionId}/question`);
  if (state.question.complete) {
    await finishTraining();
    return;
  }
  state.helpUsed = false;
  const flashcards = state.mode === "flashcards";
  const progress = state.totalQuestions >= state.targetQuestions
    ? "Wiederholung"
    : `Frage ${state.totalQuestions + 1} / ${state.targetQuestions}`;
  $("#training-area").classList.remove("d-none");
  $("#training-area").innerHTML = `<div class="card question-card p-4 p-md-5">
    <div class="d-flex justify-content-between"><span class="badge text-bg-light">${progress}</span><button id="stop-training" class="btn btn-sm btn-outline-secondary rounded-pill">Beenden</button></div>
    <p class="eyebrow mt-4">${state.question.translation === "de-en" ? "Deutsch → Englisch" : "Englisch → Deutsch"}</p>
    <div class="prompt-word">${escapeHtml(state.question.prompt)}</div>
    <div id="flashcard-answer" class="fs-3 fw-bold mt-3 d-none"></div>
    <div id="answer-controls" class="${flashcards ? "d-none" : ""}">
      <input id="answer-input" class="form-control form-control-lg text-center mt-4" autocomplete="off" placeholder="Deine Antwort">
      <button id="submit-answer" class="btn btn-primary btn-lg rounded-pill mt-3 px-5">Prüfen</button>
    </div>
    <div id="flashcard-controls" class="${flashcards ? "" : "d-none"}">
      <button id="reveal-card" class="btn btn-primary btn-lg rounded-pill mt-4 px-5">Lösung anzeigen</button>
      <div id="rate-card" class="d-none mt-3 d-flex justify-content-center gap-2">
        <button class="btn btn-success rounded-pill" data-rating="correct">Gewusst ✓</button>
        <button class="btn btn-outline-danger rounded-pill" data-rating="wrong">Nicht gewusst</button>
      </div>
    </div>
    <div class="d-flex flex-wrap justify-content-center gap-2 mt-3" id="help-buttons">
      <button class="btn btn-sm btn-outline-secondary rounded-pill" data-help="letter">Erster Buchstabe</button>
      <button class="btn btn-sm btn-outline-secondary rounded-pill" data-help="length">Wortlänge</button>
      <button class="btn btn-sm btn-outline-secondary rounded-pill" data-help="example">Beispielsatz</button>
      <button class="btn btn-sm btn-outline-secondary rounded-pill" data-help="partial">Teil-Lösung</button>
    </div>
    <div id="help-output" class="mt-3 fw-bold text-secondary"></div>
    <div id="answer-feedback" class="mt-3"></div>
  </div>`;
  $("#stop-training").addEventListener("click", finishTraining);
  document.querySelectorAll("[data-help]").forEach((button) => button.addEventListener("click", () => showHelp(button.dataset.help)));
  if (flashcards) {
    $("#help-buttons").classList.add("d-none");
    $("#reveal-card").addEventListener("click", revealCard);
    document.querySelectorAll("[data-rating]").forEach((button) => button.addEventListener("click", () => submitAnswer("", button.dataset.rating)));
  } else {
    $("#submit-answer").addEventListener("click", () => submitAnswer($("#answer-input").value));
    $("#answer-input").addEventListener("keydown", (event) => { if (event.key === "Enter") submitAnswer($("#answer-input").value); });
    $("#answer-input").focus();
  }
}

function showHelp(kind) {
  state.helpUsed = true;
  const question = state.question;
  const values = {
    letter: `${question.first_letter} _ …`,
    length: `${question.word_length} Buchstaben`,
    example: question.example_sentence || "Für dieses Wort gibt es keinen Beispielsatz.",
    partial: question.partial_hint
  };
  $("#help-output").textContent = values[kind];
}

async function revealCard() {
  const solution = await api(`/api/training/${state.sessionId}/solution/${state.question.vocabulary_id}`);
  $("#flashcard-answer").textContent = solution.answer;
  $("#flashcard-answer").classList.remove("d-none");
  $("#reveal-card").classList.add("d-none");
  $("#rate-card").classList.remove("d-none");
}

async function submitAnswer(answer, resultType = null) {
  const buttons = document.querySelectorAll("#training-area button");
  buttons.forEach((button) => { button.disabled = true; });
  try {
    const result = await api(`/api/training/${state.sessionId}/answers`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        vocabulary_id: state.question.vocabulary_id, answer, result_type: resultType, help_used: state.helpUsed
      })
    });
    state.totalQuestions = result.total_questions;
    $("#answer-feedback").innerHTML = `<div class="alert ${result.result_type === "correct" ? "alert-success" : result.result_type === "partial" ? "alert-warning" : "alert-danger"}">
      <strong>${escapeHtml(result.message)}</strong> ${escapeHtml(result.expected_answer)} · ${result.points} Punkt${result.points === 1 ? "" : "e"}
    </div>${result.complete ? "<p>Runde abgeschlossen!</p>" : '<button id="next-question" class="btn btn-primary rounded-pill px-4">Nächste Frage →</button>'}`;
    $("#answer-controls").classList.add("d-none");
    $("#flashcard-controls").classList.add("d-none");
    $("#help-buttons").classList.add("d-none");
    $("#help-output").textContent = "";
    if (result.complete) {
      window.setTimeout(finishTraining, 900);
    } else {
      $("#next-question").addEventListener("click", loadQuestion);
      $("#next-question").disabled = false;
    }
  } catch (error) {
    buttons.forEach((button) => { button.disabled = false; });
    notice(error.message, "danger");
  }
}

async function finishTraining() {
  try {
    const summary = await api(`/api/training/${state.sessionId}`);
    const questionSummary = summary.total_questions > summary.target_questions
      ? `${summary.total_questions} Fragen, davon ${summary.total_questions - summary.target_questions} Wiederholungen`
      : `${summary.total_questions} / ${summary.target_questions} Fragen`;
    $("#training-area").innerHTML = `<div class="card question-card p-5 text-center">
      <div class="display-3">🎉</div><h2 class="mt-3">Toll gemacht!</h2>
      <p>${questionSummary} · ${summary.correct_answers} richtig · ${summary.partial_answers} fast richtig · ${summary.wrong_answers} falsch</p>
      <strong>${summary.score} Punkte</strong><br><button class="btn btn-primary rounded-pill mt-4" id="practice-again">Nochmal üben</button>
    </div>`;
    $("#practice-again").addEventListener("click", () => {
      $("#training-area").classList.add("d-none");
      $("#practice-setup").classList.remove("d-none");
      state.sessionId = null;
    });
    await loadStatistics();
  } catch (error) { notice(error.message, "danger"); }
}

async function loadMatchingRound() {
  const round = await api(`/api/training/${state.sessionId}/matching`);
  if (round.complete || round.left.length === 0) {
    await finishTraining();
    return;
  }
  state.matched = new Set();
  state.selectedLeft = null;
  state.selectedRight = null;
  const progress = state.totalQuestions >= state.targetQuestions
    ? "Wiederholung"
    : `${state.totalQuestions} / ${state.targetQuestions}`;
  $("#training-area").classList.remove("d-none");
  $("#training-area").innerHTML = `<div class="card question-card p-4">
    <div class="d-flex justify-content-between"><h2 class="h4">Finde die passenden Wörter</h2><span>${progress}</span><button id="stop-training" class="btn btn-sm btn-outline-secondary rounded-pill">Beenden</button></div>
    <div class="row g-3 mt-2"><div class="col-6"><div class="d-grid gap-2">${round.left.map((item) => `<button class="pair-button left-pair" data-id="${item.id}">${escapeHtml(item.text)}</button>`).join("")}</div></div>
    <div class="col-6"><div class="d-grid gap-2">${round.right.map((item) => `<button class="pair-button right-pair" data-id="${item.id}">${escapeHtml(item.text)}</button>`).join("")}</div></div></div>
    <div id="match-feedback" class="mt-3"></div>
  </div>`;
  $("#stop-training").addEventListener("click", finishTraining);
  document.querySelectorAll(".left-pair").forEach((button) => button.addEventListener("click", () => selectPair("left", button)));
  document.querySelectorAll(".right-pair").forEach((button) => button.addEventListener("click", () => selectPair("right", button)));
}

async function selectPair(side, button) {
  const selector = side === "left" ? ".left-pair" : ".right-pair";
  document.querySelectorAll(selector).forEach((item) => item.classList.remove("selected"));
  button.classList.add("selected");
  state[side === "left" ? "selectedLeft" : "selectedRight"] = button;
  if (!state.selectedLeft || !state.selectedRight) return;
  const left = state.selectedLeft;
  const right = state.selectedRight;
  const correct = left.dataset.id === right.dataset.id;
  try {
    const result = await api(`/api/training/${state.sessionId}/answers`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ vocabulary_id: Number(left.dataset.id), answer: "", result_type: correct ? "correct" : "wrong" })
    });
    state.totalQuestions = result.total_questions;
    if (result.complete) {
      await finishTraining();
      return;
    }
    if (correct) {
      left.classList.add("matched");
      right.classList.add("matched");
      state.matched.add(left.dataset.id);
      $("#match-feedback").textContent = "Super, gefunden! ✨";
    } else {
      $("#match-feedback").textContent = "Fast! Versuch es nochmal.";
      window.setTimeout(() => { left.classList.remove("selected"); right.classList.remove("selected"); }, 500);
    }
    state.selectedLeft = null;
    state.selectedRight = null;
    if (state.matched.size === document.querySelectorAll(".left-pair").length) {
      $("#match-feedback").innerHTML = 'Alle gefunden! <button id="next-match-round" class="btn btn-primary rounded-pill ms-2">Neue Runde</button>';
      $("#next-match-round").addEventListener("click", loadMatchingRound);
    }
  } catch (error) { notice(error.message, "danger"); }
}

async function loadStatistics() {
  const data = await api("/api/statistics");
  const stats = [
    ["📖", data.learned_vocabulary, "gelernte Vokabeln"],
    ["✅", data.correct_answers, "richtige Antworten"],
    ["💡", data.partial_answers, "Teiltreffer"],
    ["🎯", `${data.success_rate}%`, "Erfolgsquote"],
    ["🔥", data.streak_days, "Tage Lernserie"]
  ];
  $("#stat-cards").innerHTML = stats.map(([icon, value, label]) => `<div class="col-6 col-lg"><div class="stat-card"><span>${icon}</span><strong>${value}</strong><span>${label}</span></div></div>`).join("");
  $("#history-list").innerHTML = data.history.length
    ? data.history.slice(-10).reverse().map((item) => `<div class="d-flex justify-content-between border-bottom py-2"><span>${new Date(`${item.date}T12:00:00`).toLocaleDateString("de-DE")}</span><strong>${item.answers} Antworten</strong></div>`).join("")
    : '<p class="text-secondary">Hier erscheinen deine Lerntage.</p>';
  const badgeNames = { bronze: "🥉 Bronze", silver: "🥈 Silber", gold: "🥇 Gold", diamond: "💎 Diamant" };
  const badgeCounts = data.badges.reduce((counts, badge) => ({ ...counts, [badge.badge_type]: (counts[badge.badge_type] || 0) + 1 }), {});
  $("#badge-list").innerHTML = Object.entries(badgeNames).map(([key, name]) => `<div class="d-flex justify-content-between border-bottom py-2"><span>${name}</span><strong>${badgeCounts[key] || 0}</strong></div>`).join("");
  $("#difficult-list").innerHTML = data.difficult_words.length
    ? data.difficult_words.slice(0, 10).map((word) => `<div class="d-flex justify-content-between border-bottom py-2"><span>${escapeHtml(word.german)} <span class="text-secondary">(${escapeHtml(word.english)})</span></span><strong>${Math.round(word.error_rate * 100)}% Fehler</strong></div>`).join("")
    : '<p class="text-secondary">Noch keine Wörter zum Wiederholen.</p>';
  $("#favorite-list").innerHTML = data.favorite_words.length
    ? data.favorite_words.slice(0, 10).map((word) => `<div class="d-flex justify-content-between border-bottom py-2"><span>${escapeHtml(word.german)} <span class="text-secondary">(${escapeHtml(word.english)})</span></span><strong>${word.correct_count}× richtig</strong></div>`).join("")
    : '<p class="text-secondary">Deine Lieblingswörter kommen bald.</p>';
}

loadFolders().catch((error) => notice(error.message, "danger"));
