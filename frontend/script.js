// ---------------------------------------------------------------------
// Voice Agent frontend logic.
// Click the mic to start recording, click again to stop and send.
// ---------------------------------------------------------------------

const DEFAULT_BACKEND_URL = "http://localhost:8000";

const els = {
  micBtn: document.getElementById("micBtn"),
  statusDot: document.getElementById("statusDot"),
  statusText: document.getElementById("statusText"),
  transcript: document.getElementById("transcript"),
  player: document.getElementById("player"),
  textForm: document.getElementById("textForm"),
  textInput: document.getElementById("textInput"),
  settingsBtn: document.getElementById("settingsBtn"),
  settingsPanel: document.getElementById("settingsPanel"),
  backendUrlInput: document.getElementById("backendUrl"),
  saveSettingsBtn: document.getElementById("saveSettingsBtn"),
  clearHistoryBtn: document.getElementById("clearHistoryBtn"),
};

let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let isBusy = false;
let history = JSON.parse(sessionStorage.getItem("va_history") || "[]");

// ---------------------------------------------------------------------
// Settings (backend URL persisted in localStorage)
// ---------------------------------------------------------------------

function getBackendUrl() {
  return localStorage.getItem("va_backend_url") || DEFAULT_BACKEND_URL;
}

function openSettings() {
  els.backendUrlInput.value = getBackendUrl();
  els.settingsPanel.hidden = false;
}

els.settingsBtn.addEventListener("click", openSettings);

els.saveSettingsBtn.addEventListener("click", () => {
  const url = els.backendUrlInput.value.trim().replace(/\/+$/, "");
  if (url) localStorage.setItem("va_backend_url", url);
  els.settingsPanel.hidden = true;
  checkHealth();
});

els.settingsPanel.addEventListener("click", (e) => {
  if (e.target === els.settingsPanel) els.settingsPanel.hidden = true;
});

els.clearHistoryBtn.addEventListener("click", () => {
  history = [];
  sessionStorage.removeItem("va_history");
  els.transcript.innerHTML = `<div class="empty-state"><p>Tap the mic and say something.</p></div>`;
});

// No first-run prompt — the app just uses DEFAULT_BACKEND_URL
// (http://localhost:8000) until you open Settings and change it yourself.

// ---------------------------------------------------------------------
// Status helpers
// ---------------------------------------------------------------------

function setStatus(text, dotClass) {
  els.statusText.textContent = text;
  els.statusDot.className = "dot" + (dotClass ? ` ${dotClass}` : "");
}

async function checkHealth() {
  try {
    const res = await fetch(`${getBackendUrl()}/api/health`);
    if (!res.ok) throw new Error();
    setStatus("Idle", "ready");
  } catch {
    setStatus("Backend unreachable — check settings", "");
  }
}
checkHealth();

// ---------------------------------------------------------------------
// Transcript rendering
// ---------------------------------------------------------------------

function clearEmptyState() {
  const empty = els.transcript.querySelector(".empty-state");
  if (empty) empty.remove();
}

function addBubble(role, text) {
  clearEmptyState();
  const bubble = document.createElement("div");
  bubble.className = `bubble ${role}`;
  bubble.textContent = text;
  els.transcript.appendChild(bubble);
  els.transcript.scrollTop = els.transcript.scrollHeight;
  return bubble;
}

// ---------------------------------------------------------------------
// Recording
// ---------------------------------------------------------------------

els.micBtn.addEventListener("click", () => {
  if (isBusy) return;
  if (isRecording) {
    stopRecording();
  } else {
    startRecording();
  }
});

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mimeType = MediaRecorder.isTypeSupported("audio/webm")
      ? "audio/webm"
      : "audio/ogg";
    mediaRecorder = new MediaRecorder(stream, { mimeType });
    audioChunks = [];

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };
    mediaRecorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(audioChunks, { type: mimeType });
      sendAudio(blob);
    };

    mediaRecorder.start();
    isRecording = true;
    els.micBtn.classList.add("recording");
    els.micBtn.setAttribute("aria-label", "Stop recording");
    setStatus("Listening… tap to stop", "recording");
  } catch (err) {
    console.error(err);
    setStatus("Microphone access denied", "");
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  isRecording = false;
  els.micBtn.classList.remove("recording");
  els.micBtn.setAttribute("aria-label", "Start recording");
}

// ---------------------------------------------------------------------
// Networking
// ---------------------------------------------------------------------

function setBusy(busy, label) {
  isBusy = busy;
  els.micBtn.classList.toggle("busy", busy);
  els.micBtn.disabled = busy;
  els.textInput.disabled = busy;
  if (busy) setStatus(label || "Thinking…", "busy");
}

async function sendAudio(blob) {
  setBusy(true, "Transcribing…");

  const form = new FormData();
  form.append("audio", blob, "recording.webm");
  form.append("history", JSON.stringify(history));

  try {
    const res = await fetch(`${getBackendUrl()}/api/voice-chat`, {
      method: "POST",
      body: form,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Request failed");

    addBubble("user", data.transcript);
    addBubble("agent", data.reply);
    history = data.history;
    sessionStorage.setItem("va_history", JSON.stringify(history));

    await playAudio(data.audio_base64);
  } catch (err) {
    console.error(err);
    addBubble("error", `⚠ ${err.message}`);
    setBusy(false);
    setStatus("Idle", "ready");
  }
}

async function sendText(message) {
  setBusy(true, "Thinking…");
  addBubble("user", message);

  try {
    const res = await fetch(`${getBackendUrl()}/api/text-chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Request failed");

    addBubble("agent", data.reply);
    history = data.history;
    sessionStorage.setItem("va_history", JSON.stringify(history));

    await playAudio(data.audio_base64);
  } catch (err) {
    console.error(err);
    addBubble("error", `⚠ ${err.message}`);
    setBusy(false);
    setStatus("Idle", "ready");
  }
}

function playAudio(base64) {
  return new Promise((resolve) => {
    els.player.src = `data:audio/mpeg;base64,${base64}`;
    setStatus("Speaking…", "busy");
    els.player.onended = () => {
      setBusy(false);
      setStatus("Idle", "ready");
      resolve();
    };
    els.player.onerror = () => {
      setBusy(false);
      setStatus("Idle", "ready");
      resolve();
    };
    els.player.play().catch(() => {
      setBusy(false);
      setStatus("Idle", "ready");
      resolve();
    });
  });
}

// ---------------------------------------------------------------------
// Typed message fallback
// ---------------------------------------------------------------------

els.textForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const message = els.textInput.value.trim();
  if (!message || isBusy) return;
  els.textInput.value = "";
  sendText(message);
});