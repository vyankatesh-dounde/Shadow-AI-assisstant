// static/js/app.js
// Shadow dashboard client. Talks to the FastAPI server over a single
// WebSocket for real-time chat + live events, and plain REST for
// one-off reads/writes (reminders CRUD, status polling fallback).

(() => {
  "use strict";

  // If you don't see this line in DevTools > Console after a hard
  // refresh (Ctrl+Shift+R / Cmd+Shift+R), the browser is still
  // serving a cached copy of this file - that's the #1 cause of "I
  // updated the code but nothing changed."
  console.log("[Shadow] app.js build 2026-08-05-wake-fix-3");

  const TOKEN_KEY = "shadow_token";
  const WAKE_KEY = "shadow_wake_enabled";
  const WAKE_WORDS = ["hey shadow", "shadow"];

  const el = (id) => document.getElementById(id);

  const gate = el("gate");
  const gateToken = el("gate-token");
  const gateConnect = el("gate-connect");
  const gateError = el("gate-error");
  const app = el("app");

  const presence = el("presence");
  const connIndicator = el("conn-indicator");
  const wakeToggle = el("wake-toggle");
  const chatScroll = el("chat-scroll");
  const chatEmpty = el("chat-empty");
  const composer = el("composer");
  const chatInput = el("chat-input");
  const micBtn = el("mic-btn");
  const ttsAudio = el("tts-audio");

  const cpuVal = el("cpu-val");
  const cpuFill = el("cpu-fill");
  const memVal = el("mem-val");
  const memFill = el("mem-fill");
  const activeWindowEl = el("active-window");
  const batteryVal = el("battery-val");

  const controlLog = el("control-log");
  const reminderList = el("reminder-list");
  const reminderText = el("reminder-text");
  const reminderWhen = el("reminder-when");
  const reminderAdd = el("reminder-add");
  const reminderError = el("reminder-error");

  const customSelect = el("custom-action-select");
  const customValue = el("custom-action-value");
  const customRun = el("custom-action-run");

  let ws = null;
  let reconnectDelay = 1000;
  let reconnectAttempts = 0;
  const MAX_RECONNECT_ATTEMPTS = 6;

  // =======================================================
  // TOKEN / GATE
  // =======================================================

  function getToken() {
    return localStorage.getItem(TOKEN_KEY) || "";
  }

  function setToken(t) {
    localStorage.setItem(TOKEN_KEY, t);
  }

  function showGate(message) {
    app.classList.add("hidden");
    gate.classList.remove("hidden");
    gateError.textContent = message || "";
  }

  function showApp() {
    gate.classList.add("hidden");
    app.classList.remove("hidden");
  }

  gateConnect.addEventListener("click", () => {
    const t = gateToken.value.trim();
    if (!t) {
      gateError.textContent = "Enter a token to continue.";
      return;
    }
    setToken(t);
    connect();
  });

  gateToken.addEventListener("keydown", (e) => {
    if (e.key === "Enter") gateConnect.click();
  });

  // =======================================================
  // API HELPER
  // =======================================================

  async function api(path, options = {}) {
    const headers = Object.assign(
      { "Content-Type": "application/json", "X-API-Token": getToken() },
      options.headers || {}
    );
    const res = await fetch(path, Object.assign({}, options, { headers }));
    if (res.status === 401) {
      showGate("That token was rejected. Try again.");
      throw new Error("unauthorized");
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Request failed (${res.status})`);
    }
    if (res.status === 204) return null;
    return res.json();
  }

  // =======================================================
  // WEBSOCKET
  // =======================================================

  async function connect() {
    const token = getToken();
    if (!token) {
      showGate();
      return;
    }

    connIndicator.dataset.state = "connecting";
    connIndicator.querySelector(".conn-label").textContent = "connecting…";

    // Pre-flight the token over plain REST first. A WebSocket rejected
    // for a bad token is refused *before* the handshake completes, so
    // the browser can't actually surface our close code - it just
    // reports a generic abnormal closure either way. Checking over
    // REST first means a bad token is unambiguous (a real 401) instead
    // of indistinguishable from a network blip.
    try {
      await api("/api/status");
    } catch (e) {
      if (String(e.message) !== "unauthorized") {
        // server unreachable / still starting up - fall through to
        // the normal WebSocket retry loop below instead of giving up
      } else {
        return; // api() already showed the gate with an error message
      }
    }

    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws?token=${encodeURIComponent(token)}`);

    ws.onopen = () => {
      showApp();
      reconnectDelay = 1000;
      reconnectAttempts = 0;
      connIndicator.dataset.state = "online";
      connIndicator.querySelector(".conn-label").textContent = "online";
      refreshStatusOnce();
    };

    ws.onclose = () => {
      connIndicator.dataset.state = "offline";
      connIndicator.querySelector(".conn-label").textContent = "offline";

      reconnectAttempts += 1;
      if (reconnectAttempts > MAX_RECONNECT_ATTEMPTS) {
        showGate("Can't reach Shadow. Check the server is running, then reconnect.");
        return;
      }

      setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 1.6, 15000);
    };

    ws.onerror = () => {
      try { ws.close(); } catch (e) {}
    };

    ws.onmessage = (evt) => {
      let data;
      try { data = JSON.parse(evt.data); } catch (e) { return; }
      handleMessage(data);
    };
  }

  function send(payload) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(payload));
    }
  }

  function handleMessage(data) {
    switch (data.type) {
      case "conversation":
        renderHistory(data.history || []);
        break;
      case "user_message":
        addBubble("user", data.text);
        break;
      case "response":
        setPresence("idle");
        addBubble("assistant", data.text, data.audio_url);
        playAudio(data.audio_url);
        break;
      case "reminder_due":
        addBubble("system", `⏰ ${data.text}`);
        playAudio(data.audio_url);
        notify("Shadow reminder", data.text);
        break;
      case "reminders_updated":
        renderReminders(data.reminders || []);
        break;
      case "conversation_cleared":
        chatScroll.innerHTML = "";
        chatScroll.appendChild(chatEmpty);
        chatEmpty.classList.remove("hidden");
        break;
      case "status":
        renderStatus(data);
        break;
      case "desktop_event":
        handleDesktopEvent(data);
        break;
      case "error":
        logControl(data.message || "Unknown error", "err");
        break;
      case "pong":
        break;
      default:
        break;
    }
  }

  // =======================================================
  // PRESENCE (the signature ring: idle / listening / thinking / speaking)
  // =======================================================

  function setPresence(state) {
    presence.dataset.state = state;
  }

  function playAudio(url) {
    if (!url) return;
    setPresence("speaking");
    ttsAudio.src = url;
    ttsAudio.play().catch(() => {});
    ttsAudio.onended = () => setPresence("idle");
  }

  // =======================================================
  // CHAT
  // =======================================================

  function renderHistory(history) {
    chatScroll.innerHTML = "";
    if (!history.length) {
      chatScroll.appendChild(chatEmpty);
      chatEmpty.classList.remove("hidden");
      return;
    }
    history.forEach((m) => addBubble(m.role === "assistant" ? "assistant" : "user", m.content, null, false));
    scrollToBottom();
  }

  function addBubble(role, text, audioUrl, autoScroll = true) {
    chatEmpty.classList.add("hidden");
    const div = document.createElement("div");
    div.className = `msg ${role}`;
    div.textContent = text;
    if (role === "assistant") {
      div.title = "Tap to replay";
      div.addEventListener("click", () => {
        if (audioUrl) {
          playAudio(audioUrl);
        } else {
          api("/api/tts", { method: "POST", body: JSON.stringify({ text }) })
            .then((r) => playAudio(r.audio_url))
            .catch(() => {});
        }
      });
    }
    chatScroll.appendChild(div);
    if (autoScroll) scrollToBottom();
  }

  function scrollToBottom() {
    chatScroll.scrollTop = chatScroll.scrollHeight;
  }

  function sendChat(text) {
    const trimmed = (text || "").trim();
    if (!trimmed) return;
    setPresence("thinking");
    send({ type: "chat", text: trimmed });
  }

  composer.addEventListener("submit", (e) => {
    e.preventDefault();
    sendChat(chatInput.value);
    chatInput.value = "";
  });

  // =======================================================
  // VOICE INPUT — wake word ("hey shadow" / "shadow") +
  // manual push-to-talk, both via the browser's Web Speech API.
  //
  // One SpeechRecognition instance is shared between modes:
  //   "wake"          - continuous, listens quietly in the background
  //                     for the wake word
  //   "active"        - single-shot, captures the actual command
  //                     right after the wake word (or a manual mic tap)
  //   "transitioning" - a short in-between state while the previous
  //                     session is still winding down (see note below)
  //
  // IMPORTANT: recognizer.stop() is asynchronous - the browser can
  // still deliver one or more trailing result events for the OLD
  // utterance after stop() is called and before onend actually fires.
  // Switching voiceMode to "active" immediately when the wake word is
  // heard used to mean those trailing "shadow" results were re-read
  // as if they were the *command* and sent straight to the LLM. Mode
  // changes are now only applied inside onstart/onend, driven by a
  // `pendingMode` request, so a session is never reinterpreted mid-flight.
  // =======================================================

  const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognizer = null;
  let voiceMode = "off"; // "off" | "wake" | "active" | "transitioning"
  let recognizerRunning = false;
  let pendingMode = null;
  let wakeEnabled = localStorage.getItem(WAKE_KEY) === "1";

  const GREET_KEY = "shadow_last_greeting_date";
  const WAKE_ACK = "Yes?";

  // `onDone` fires once the utterance has actually finished playing
  // through the speakers - callers use this to hold off reopening the
  // mic until Shadow is done talking (see announceWake below). Without
  // this, the mic used to reopen the instant speak() was CALLED, not
  // once the audio actually finished, so it was listening while
  // Shadow's own greeting/ack was still coming out of the speakers.
  function speakLocal(text, onDone) {
    const finish = () => { if (onDone) onDone(); };

    if (!("speechSynthesis" in window)) {
      finish();
      return;
    }

    try {
      window.speechSynthesis.cancel(); // don't stack up acknowledgments

      const utter = new SpeechSynthesisUtterance(text);
      let settled = false;
      const settle = () => {
        if (settled) return;
        settled = true;
        finish();
      };

      utter.onend = settle;
      utter.onerror = settle;
      // Safety net: some browsers (notably Chrome, if the tab loses
      // focus mid-utterance) occasionally never fire onend at all.
      // Without this the mic would just stay closed forever waiting
      // for a callback that's never coming.
      setTimeout(settle, 4000);

      window.speechSynthesis.speak(utter);
    } catch (e) {
      finish();
    }
  }

  // Greets once per calendar day the first time the wake word fires;
  // every other time, a short acknowledgment so you know Shadow heard
  // you. `onDone` fires only after the line has finished being
  // spoken - callers should wait for it before opening the mic again,
  // or the mic ends up listening to Shadow's own voice.
  function announceWake(onDone) {
    const today = new Date().toDateString();
    let line;
    if (localStorage.getItem(GREET_KEY) !== today) {
      localStorage.setItem(GREET_KEY, today);
      const hour = new Date().getHours();
      const part = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
      line = `${part}. How can I help?`;
    } else {
      line = WAKE_ACK;
    }
    addBubble("system", line);
    speakLocal(line, onDone);
  }

  function updateWakeUI() {
    const label = wakeToggle.querySelector(".wake-label");
    if (!SpeechRecognitionImpl) {
      wakeToggle.dataset.state = "blocked";
      label.textContent = "voice not supported";
      return;
    }
    if (voiceMode === "active") {
      wakeToggle.dataset.state = "listening";
      label.textContent = "listening…";
    } else if (wakeEnabled) {
      wakeToggle.dataset.state = "on";
      label.textContent = "wake word: on";
    } else {
      wakeToggle.dataset.state = "off";
      label.textContent = "wake word: off";
    }
  }

  if (SpeechRecognitionImpl) {
    recognizer = new SpeechRecognitionImpl();
    recognizer.lang = "en-US";
    recognizer.maxAlternatives = 1;

    // Actually configures + starts the recognizer for `mode`. Only
    // ever called from onstart/onend, never directly from onresult,
    // so a session is never reconfigured while it's still finishing.
    function applyMode(mode) {
      console.debug("[Shadow][voice] mode ->", mode);
      voiceMode = mode;
      if (mode === "off") {
        updateWakeUI();
        return;
      }
      recognizer.continuous = mode === "wake";
      recognizer.interimResults = mode === "wake";
      try {
        recognizer.start();
      } catch (e) {
        // Rare: browser says it's already running. Let the next
        // onend retry rather than crash here.
      }
      updateWakeUI();
    }

    // Requests a mode switch. If a session is currently running, it's
    // stopped first and the new mode is applied once onend confirms
    // the old session is fully done - never before.
    function requestMode(mode) {
      pendingMode = mode;
      if (recognizerRunning) {
        try { recognizer.stop(); } catch (e) {}
      } else {
        pendingMode = null;
        applyMode(mode);
      }
    }

    recognizer.onstart = () => {
      recognizerRunning = true;
      if (voiceMode === "active") {
        micBtn.classList.add("recording");
        setPresence("listening");
      }
      updateWakeUI();
    };

    recognizer.onend = () => {
      recognizerRunning = false;
      micBtn.classList.remove("recording");
      if (voiceMode === "active" && presence.dataset.state === "listening") setPresence("idle");

      // Browsers also stop recognition on their own after a pause in
      // speech even in continuous mode, so re-arm using whatever was
      // requested, or fall back to wake/off based on the toggle.
      const next = pendingMode !== null ? pendingMode : (wakeEnabled ? "wake" : "off");
      pendingMode = null;
      applyMode(next);
    };

    recognizer.onerror = (e) => {
      micBtn.classList.remove("recording");
      setPresence("idle");
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        // Mic permission denied - stop trying, don't loop forever.
        wakeEnabled = false;
        localStorage.setItem(WAKE_KEY, "0");
        pendingMode = "off";
        wakeToggle.dataset.state = "blocked";
        wakeToggle.querySelector(".wake-label").textContent = "mic blocked";
      }
      // other errors (e.g. "no-speech") are recovered by onend's restart
    };

    recognizer.onresult = (event) => {
      if (voiceMode === "active") {
        const transcript = event.results[event.results.length - 1][0].transcript.trim();
        console.debug("[Shadow][active] command captured:", transcript);
        if (transcript) {
          sendChat(transcript);
        }
        // Mark as transitioning right away so any trailing result
        // events the browser still delivers for THIS SAME utterance
        // aren't read again as a second command.
        voiceMode = "transitioning";
        requestMode(wakeEnabled ? "wake" : "off");
        return;
      }

      if (voiceMode === "wake") {
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript.toLowerCase();
          console.debug("[Shadow][wake] heard:", transcript);
          const hit = WAKE_WORDS.find((w) => transcript.includes(w));
          if (!hit) continue;

          const after = transcript.slice(transcript.indexOf(hit) + hit.length).trim();
          console.debug("[Shadow][wake] wake word matched:", hit, "| remainder:", JSON.stringify(after));

          // Mark as transitioning immediately - same reasoning as
          // above: this SAME utterance can keep producing trailing
          // result events after we've decided what to do with it.
          voiceMode = "transitioning";

          if (after.length > 2) {
            // Wake word + command in the same breath, e.g.
            // "hey shadow what time is it" - just send it.
            sendChat(after);
            requestMode(wakeEnabled ? "wake" : "off");
          } else {
            // Just "shadow" alone - acknowledge, THEN open the mic
            // for the actual command, once the acknowledgment has
            // actually finished playing. Opening it any earlier meant
            // the mic was live while Shadow's own "Yes?" / greeting
            // was still coming out of the speakers - it would pick
            // that up (or error out on the overlap) and miss your
            // real command entirely.
            console.debug("[Shadow][wake] acknowledging, then opening mic for command…");
            announceWake(() => {
              console.debug("[Shadow][wake] ack finished, mic opening now");
              requestMode("active");
            });
          }
          break;
        }
      }
      // "transitioning": deliberately ignored - see comment above.
    };

    micBtn.addEventListener("click", () => {
      if (voiceMode === "active") {
        try { recognizer.stop(); } catch (e) {}
        return;
      }
      requestMode("active");
    });

    wakeToggle.addEventListener("click", () => {
      wakeEnabled = !wakeEnabled;
      localStorage.setItem(WAKE_KEY, wakeEnabled ? "1" : "0");
      requestMode(wakeEnabled ? "wake" : "off");
    });

    if (wakeEnabled) requestMode("wake");
    updateWakeUI();
  } else {
    micBtn.disabled = true;
    micBtn.title = "Voice input isn't supported in this browser — try Chrome or Edge.";
    wakeToggle.disabled = true;
    wakeToggle.title = "Voice input isn't supported in this browser.";
    wakeToggle.dataset.state = "blocked";
  }

  // =======================================================
  // SYSTEM STATUS
  // =======================================================

  function renderStatus(data) {
    if (typeof data.cpu === "number") {
      cpuVal.textContent = `${Math.round(data.cpu)}%`;
      cpuFill.style.width = `${Math.round(data.cpu)}%`;
    }
    if (typeof data.memory === "number") {
      memVal.textContent = `${Math.round(data.memory)}%`;
      memFill.style.width = `${Math.round(data.memory)}%`;
    }
    activeWindowEl.textContent = data.active_window || "–";
    batteryVal.textContent = data.battery != null ? `${data.battery}%` : "n/a";
  }

  async function refreshStatusOnce() {
    try {
      const data = await api("/api/status");
      renderStatus(data);
    } catch (e) {}
  }

  // =======================================================
  // DESKTOP CONTROL
  // =======================================================

  function logControl(text, cls) {
    const li = document.createElement("li");
    li.textContent = text;
    if (cls) li.className = cls;
    controlLog.prepend(li);
    while (controlLog.children.length > 20) controlLog.removeChild(controlLog.lastChild);
  }

  function handleDesktopEvent(data) {
    const result = data.result || {};
    if (result.status === "confirm_required") {
      showConfirm(data.action, data.value);
      return;
    }
    if (result.status === "error") {
      logControl(`✕ ${data.action}: ${result.result}`, "err");
    } else {
      logControl(`✓ ${result.result || data.action}`, "ok");
    }
  }

  function runAction(action, value, confirm = false) {
    send({ type: "action", action, value, confirm });
  }

  document.querySelectorAll(".action-grid button").forEach((btn) => {
    btn.addEventListener("click", () => {
      runAction(btn.dataset.action, btn.dataset.value || null, false);
    });
  });

  customRun.addEventListener("click", () => {
    const action = customSelect.value;
    const value = customValue.value.trim();
    runAction(action, value || null, false);
  });

  // ---- confirm modal for dangerous / lifecycle actions ----
  const ACTION_LABELS = {
    stop_server: "stop the server",
    restart: "restart the PC",
    sleep_pc: "put the PC to sleep",
    close: "close that app",
  };

  function showConfirm(action, value) {
    const label = ACTION_LABELS[action] || action.replace(/_/g, " ");
    const overlay = document.createElement("div");
    overlay.className = "confirm-overlay";
    overlay.innerHTML = `
      <div class="confirm-card">
        <h2>Confirm: ${label}</h2>
        <p>${action === "stop_server"
          ? "This stops Shadow's server on this PC (not the PC itself). Every connected device will disconnect."
          : "This will affect the host PC directly."} Are you sure?</p>
        <div class="confirm-actions">
          <button class="confirm-no">Cancel</button>
          <button class="confirm-yes">Yes, ${label}</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    overlay.querySelector(".confirm-no").addEventListener("click", () => overlay.remove());
    overlay.querySelector(".confirm-yes").addEventListener("click", () => {
      runAction(action, value, true);
      overlay.remove();
    });
  }

  // =======================================================
  // REMINDERS
  // =======================================================

  function setReminderError(msg) {
    if (!msg) {
      reminderError.classList.add("hidden");
      reminderError.textContent = "";
      return;
    }
    reminderError.textContent = msg;
    reminderError.classList.remove("hidden");
  }

  function renderReminders(reminders) {
    reminderList.innerHTML = "";
    if (!reminders.length) {
      const li = document.createElement("li");
      li.className = "empty-hint";
      li.textContent = "No reminders yet.";
      reminderList.appendChild(li);
      return;
    }
    reminders.forEach((r) => {
      const li = document.createElement("li");
      li.className = "reminder-item";
      const when = new Date(r.time * 1000);
      li.innerHTML = `
        <div>
          <span class="r-text"></span>
          <span class="r-time"></span>
        </div>
        <button title="Delete">✕</button>
      `;
      li.querySelector(".r-text").textContent = r.text;
      li.querySelector(".r-time").textContent = when.toLocaleString();
      li.querySelector("button").addEventListener("click", async () => {
        try {
          await api(`/api/reminders/${encodeURIComponent(r.id)}`, { method: "DELETE" });
        } catch (e) {
          logControl(`Couldn't delete reminder: ${e.message}`, "err");
        }
      });
      reminderList.appendChild(li);
    });
  }

  reminderAdd.addEventListener("click", async () => {
    const text = reminderText.value.trim();
    const when = reminderWhen.value.trim();

    setReminderError(null);
    if (!text) {
      setReminderError("Enter what to remind you about.");
      return;
    }
    if (!when) {
      setReminderError("Enter when — e.g. 'in 10 minutes' or 'at 6pm'.");
      return;
    }

    reminderAdd.disabled = true;
    try {
      await api("/api/reminders", { method: "POST", body: JSON.stringify({ text, when }) });
      reminderText.value = "";
      reminderWhen.value = "";
      // reminders_updated will arrive over the WebSocket and re-render
      // the list; if the socket happens to be down, fall back to a
      // direct fetch so the new reminder still shows up.
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        try {
          renderReminders(await api("/api/reminders"));
        } catch (e) {}
      }
    } catch (e) {
      setReminderError(e.message || "Couldn't add that reminder.");
    } finally {
      reminderAdd.disabled = false;
    }
  });

  [reminderText, reminderWhen].forEach((input) => {
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") reminderAdd.click();
    });
    input.addEventListener("input", () => setReminderError(null));
  });

  // =======================================================
  // NOTIFICATIONS
  // =======================================================

  function notify(title, body) {
    if (!("Notification" in window)) return;
    if (Notification.permission === "granted") {
      new Notification(title, { body });
    } else if (Notification.permission !== "denied") {
      Notification.requestPermission();
    }
  }

  // =======================================================
  // MOBILE TAB SWITCHING
  // =======================================================

  const tabBtns = document.querySelectorAll(".tab-btn");
  const panels = document.querySelectorAll(".panel");

  function setActivePanel(name) {
    panels.forEach((p) => p.dataset.active = String(p.dataset.panelName === name));
    tabBtns.forEach((b) => b.classList.toggle("active", b.dataset.panel === name));
  }

  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => setActivePanel(btn.dataset.panel));
  });

  setActivePanel("chat");

  // =======================================================
  // BOOT
  // =======================================================

  if (getToken()) {
    connect();
  } else {
    showGate();
  }
})();
