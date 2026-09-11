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

  console.log("[Shadow] app.js build 2026-09-05-3d-hologram-layer-fix");

  console.log("[Shadow] app.js build 2026-08-12-recognizer-error-fix");


  const TOKEN_KEY = "shadow_token";
  const WAKE_KEY = "shadow_wake_enabled";
  const WAKE_WORDS = ["hey shadow", "shadow"];

  const el = (id) => document.getElementById(id);

  const gate = el("gate");
  const gateToken = el("gate-token");
  const gateConnect = el("gate-connect");
  const gateError = el("gate-error");
  const app = el("app");



  const connIndicator = el("conn-indicator");
  const wakeToggle = el("wake-toggle");
  const chatScroll = el("chat-scroll");
  const chatEmpty = el("chat-empty");
  const composer = el("composer");
  const chatInput = el("chat-input");
  const micBtn = el("mic-btn");
  const ttsAudio = el("tts-audio");

  const powerActions = document.querySelector(".power-actions");

  const coreCanvas = el("core-canvas");
  const chatCorner = el("chat-corner");
  const cornerToggle = el("corner-toggle");


  const cpuVal = el("cpu-val");
  const cpuFill = el("cpu-fill");
  const memVal = el("mem-val");
  const memFill = el("mem-fill");
  const activeWindowEl = el("active-window");
  const batteryVal = el("battery-val");
  const uptimeVal = el("uptime-val");

  const controlLog = el("control-log");
  const relationshipLevel = el("relationship-level");
  const relationshipPoints = el("relationship-points");
  const relationshipProgress = el("relationship-progress");
  const relationshipLast = el("relationship-last");

  let ws = null;
  let reconnectDelay = 1000;
  let reconnectAttempts = 0;
  const MAX_RECONNECT_ATTEMPTS = 6;

  // ======
  // TOKEN / GATE
  // ======

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

    setToken(t);
    connect();
  });

  gateToken.addEventListener("keydown", (e) => {
    if (e.key === "Enter") gateConnect.click();
  });

  // ======
  // API HELPER
  // ======

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

  // ======
  // WEBSOCKET
  // ======

  async function connect() {
    const token = getToken();


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

      if (core) core.resize();


      reconnectDelay = 1000;
      reconnectAttempts = 0;
      connIndicator.dataset.state = "online";
      connIndicator.querySelector(".conn-label").textContent = "online";


      refreshStatusOnce();
      refreshInsights();

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
        refreshInsights();
        break;
      case "reminder_due":

        // Reminders can still be created by chat ("remind me to…"),
        // so the due-alert still surfaces here even without a
        // dedicated reminders panel.


        addBubble("system", `⏰ ${data.text}`);
        playAudio(data.audio_url);
        notify("Shadow reminder", data.text);
        break;


      case "reminders_updated":
        break;

      case "conversation_cleared":
        chatScroll.innerHTML = "";
        chatScroll.appendChild(chatEmpty);
        chatEmpty.classList.remove("hidden");
        break;

      case "error":
        console.error("[Shadow]", data.message || "Unknown error");
        logControl(data.message || "Unknown error", "err");
        break;
      case "status":
        renderStatus(data);
        break;
      case "desktop_event":
        handleDesktopEvent(data);
        break;
      case "pong":
        break;
      default:
        break;
    }
  }

  // ======

  // 3D HOLOGRAPHIC CORE
  // ======
  // The previous 2D canvas globe has been replaced with the standalone
  // WebGL hologram prototype. It is loaded as a module so the rest of
  // Shadow's application/client code stays unchanged.

  let core = null;

  async function initHologram() {
    if (!coreCanvas) return;

    try {
      const module = await import("/static/js/hologram.js");
      core = module.createHologram(coreCanvas, {
        stage: el("core-stage"),
      });
      core.setState(presenceState);
      core.resize();
    } catch (error) {
      console.error("[Shadow] 3D hologram failed to initialize", error);
      coreCanvas.dataset.error = "true";
      const fallback = document.createElement("p");
      fallback.className = "core-fallback";
      fallback.textContent = "3D visual unavailable — chat is still ready.";
      coreCanvas.parentElement?.appendChild(fallback);
      coreCanvas.title = "3D hologram failed to initialize — check the browser console.";
    }
  }

  // Hologram initialization is triggered after presenceState is defined.

  // ======
  // CORNERED CHAT — collapsed pill by default; expands whenever a
  // new message is added (see addBubble below), and can be toggled
  // manually by tapping the pill.
  // ======

  if (cornerToggle && chatCorner) {
    cornerToggle.addEventListener("click", () => {
      const expanded = chatCorner.dataset.expanded === "true";
      chatCorner.dataset.expanded = String(!expanded);
    });
  }

  // ======
  // PRESENCE — no visible ring anymore (the core canvas itself
  // reacts to state via core.setState), but the current state is
  // still tracked here since a couple of voice-flow checks below
  // need to know whether we're currently "listening".
  // ======

  let presenceState = "idle";

  initHologram();

  function setPresence(state) {
    presenceState = state;
    if (core) core.setState(state);
  }

  // PRESENCE + TTS AUDIO
  // ======

  // -------------------------------------------------------
  // TTS AUDIO STATE
  // -------------------------------------------------------

  let audioUnlocked = false;
  let pendingAudioUrl = null;
  let audioRetryTimer = null;

  // -------------------------------------------------------
  // UNLOCK AUDIO
  // -------------------------------------------------------
  //
  // Chrome requires a user interaction before some kinds of
  // programmatic audio playback are allowed.
  //
  // We unlock Shadow's audio element after the user's first
  // click/touch/key interaction.
  //

  function unlockTtsAudio() {
    if (audioUnlocked || !ttsAudio) return;

    try {
      // Temporarily remove the source.
      const oldSrc = ttsAudio.src;

      ttsAudio.removeAttribute("src");
      ttsAudio.load();

      const promise = ttsAudio.play();

      if (promise && typeof promise.then === "function") {

        promise
          .then(() => {

            ttsAudio.pause();
            ttsAudio.currentTime = 0;

            audioUnlocked = true;

            if (oldSrc) {
              ttsAudio.src = oldSrc;
            }

            console.debug("[Shadow][audio] audio unlocked");

            flushPendingAudio();
          })
          .catch((error) => {

            console.debug(
              "[Shadow][audio] unlock waiting for user gesture:",
              error
            );

          });
      }

    } catch (error) {

      console.debug(
        "[Shadow][audio] unlock error:",
        error
      );
    }
  }


  // -------------------------------------------------------
  // RETRY QUEUE
  // -------------------------------------------------------

  function scheduleAudioRetry() {

    if (audioRetryTimer) {
      return;
    }

    audioRetryTimer = setTimeout(() => {

      audioRetryTimer = null;

      if (!pendingAudioUrl) {
        return;
      }

      // Try immediately if the Shadow tab is visible.
      if (!document.hidden) {
        const url = pendingAudioUrl;

        pendingAudioUrl = null;

        playAudio(url);
      }

    }, 700);
  }


  function flushPendingAudio() {

    if (!pendingAudioUrl) {
      return;
    }

    const url = pendingAudioUrl;

    pendingAudioUrl = null;

    playAudio(url);
  }


  // -------------------------------------------------------
  // USER INTERACTION → UNLOCK AUDIO
  // -------------------------------------------------------

  ["pointerdown", "keydown", "touchstart"].forEach((eventName) => {

    window.addEventListener(
      eventName,
      unlockTtsAudio,
      {
        capture: true,
        passive: true
      }
    );

  });


  // -------------------------------------------------------
  // PAGE VISIBILITY
  // -------------------------------------------------------

  document.addEventListener(
    "visibilitychange",
    () => {

      console.debug(
        "[Shadow][audio] visibility:",
        document.visibilityState
      );

      if (!document.hidden) {
        flushPendingAudio();
      }

    }
  );


  // -------------------------------------------------------
  // WINDOW FOCUS
  // -------------------------------------------------------

  window.addEventListener(
    "focus",
    () => {

      console.debug("[Shadow][audio] Shadow window focused");

      flushPendingAudio();

    }
  );


  // -------------------------------------------------------
  // MAIN PLAY AUDIO FUNCTION
  // -------------------------------------------------------

  function playAudio(url, onDone) {

    if (!url) {
      console.debug("[Shadow][audio] No audio URL");
      if (onDone) onDone();
      return;
    }

    console.debug(
      "[Shadow][audio] attempting playback:",
      url
    );

    pendingAudioUrl = url;

    setPresence("speaking");


    try {

      // ---------------------------------------------------
      // CLEAN OLD EVENTS
      // ---------------------------------------------------

      ttsAudio.onended = null;
      ttsAudio.onerror = null;


      // ---------------------------------------------------
      // PLAYBACK FINISHED
      // ---------------------------------------------------

      ttsAudio.onended = () => {

        console.debug(
          "[Shadow][audio] playback finished"
        );

        if (pendingAudioUrl === url) {
          pendingAudioUrl = null;
        }

        setPresence("idle");
        if (onDone) onDone();
      };


      // ---------------------------------------------------
      // PLAYBACK ERROR
      // ---------------------------------------------------

      ttsAudio.onerror = () => {

        console.warn(
          "[Shadow][audio] audio element error:",
          ttsAudio.error
        );

        // Don't permanently keep a broken URL.
        if (pendingAudioUrl === url) {
          pendingAudioUrl = null;
        }

        setPresence("idle");
        if (onDone) onDone();
      };


      // ---------------------------------------------------
      // LOAD AUDIO
      // ---------------------------------------------------

      ttsAudio.src = url;

      ttsAudio.load();


      // ---------------------------------------------------
      // START PLAYBACK
      // ---------------------------------------------------

      const promise = ttsAudio.play();


      // Modern Chrome returns a Promise from play().
      if (promise && typeof promise.then === "function") {

        promise

          .then(() => {

            console.debug(
              "[Shadow][audio] playback started successfully"
            );

            audioUnlocked = true;

            if (pendingAudioUrl === url) {
              pendingAudioUrl = null;
            }

          })

          .catch((error) => {

            console.warn(
              "[Shadow][audio] play() failed:",
              error.name,
              error.message
            );


            // Keep the audio URL so we can retry.
            pendingAudioUrl = url;


            // If this was an autoplay restriction,
            // playback will be retried after interaction.
            if (
              error.name === "NotAllowedError" ||
              error.name === "AbortError"
            ) {

              console.warn(
                "[Shadow][audio] Chrome blocked automatic playback"
              );

            }


            scheduleAudioRetry();

          });

      }

    } catch (error) {

      console.error(
        "[Shadow][audio] unexpected playback error:",
        error
      );

      pendingAudioUrl = url;

      scheduleAudioRetry();
    }

  }

  // ======
  // CHAT
  // ======

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


  // Solo Leveling "system window" style bubble: a small angular
  // notification label above the message body, rendered inside the
  // cornered chat panel. New messages auto-expand the corner so they
  // aren't missed while it's collapsed.
  const MSG_LABELS = { user: "YOU · INPUT", assistant: "SHADOW · RESPONSE", system: "SYSTEM · ALERT" };

  function addBubble(role, text, audioUrl, autoScroll = true) {
    chatEmpty.classList.add("hidden");
    if (chatCorner) chatCorner.dataset.expanded = "true";

    const div = document.createElement("div");
    div.className = `msg ${role}`;

    const label = document.createElement("span");
    label.className = "msg-label";
    label.textContent = MSG_LABELS[role] || "LOG";
    div.appendChild(label);

    const body = document.createElement("span");
    body.className = "msg-body";
    body.textContent = text;
    div.appendChild(body);

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


  const CONFIRM_ACTIONS = new Set(["restart", "sleep_shadow", "stop_server", "close"]);
  [powerActions].filter(Boolean).forEach((actionGroup) => {
    actionGroup.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-action]");
      if (!button) return;
      const action = button.dataset.action;
      const value = button.dataset.value || "";
      const label = button.getAttribute("aria-label") || button.title || action;
      const confirm = CONFIRM_ACTIONS.has(action)
        ? window.confirm(`Confirm: ${label}?`)
        : false;
      if (CONFIRM_ACTIONS.has(action) && !confirm) return;
      send({ type: "action", action, value, confirm });
    });
  });



  // ======
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
  // ======

  const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognizer = null;
  let voiceMode = "off"; // "off" | "wake" | "active" | "transitioning"
  let recognizerRunning = false;
  let pendingMode = null;

  let finishingSession = false;
  let requestingMicrophone = false;


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
    api("/api/tts", { method: "POST", body: JSON.stringify({ text: line }) })
      .then((result) => playAudio(result.audio_url, onDone))
      .catch(() => {
        // Do not use the browser's default voice: all Shadow speech should
        // come from the same server-side Raphael voice path.
        if (onDone) onDone();
      });
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


  function setVoiceProblem(message) {
    wakeEnabled = false;
    localStorage.setItem(WAKE_KEY, "0");
    voiceMode = "off";
    pendingMode = "off";
    wakeToggle.dataset.state = "blocked";
    wakeToggle.querySelector(".wake-label").textContent = message;
  }

  // SpeechRecognition does not reliably show Chrome's microphone prompt
  // itself. Ask for the microphone from the actual button click first;
  // this both grants permission for recognition and gives a useful status
  // when the page is opened from an insecure LAN address.
  async function requestMicrophone() {
    if (!navigator.mediaDevices?.getUserMedia) {
      setVoiceProblem("mic needs localhost/HTTPS");
      return false;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
      return true;
    } catch (error) {
      console.warn("[Shadow][voice] microphone unavailable:", error);
      setVoiceProblem("mic blocked or unavailable");
      return false;
    }
  }

  async function startVoiceFromGesture(mode) {
    if (requestingMicrophone) return;
    requestingMicrophone = true;
    wakeToggle.dataset.state = "listening";
    wakeToggle.querySelector(".wake-label").textContent = "requesting mic…";
    const allowed = await requestMicrophone();
    requestingMicrophone = false;
    if (!allowed) return;

    if (mode === "wake") {
      wakeEnabled = true;
      localStorage.setItem(WAKE_KEY, "1");
    }
    requestMode(mode);
  }



  // Extracted out of onresult so both the wake-word matcher below and
  // any future caller can check EVERY alternative the recognizer
  // returned, not just the top guess. Previously maxAlternatives = 3
  // was set but nothing ever read alternatives [1] or [2], so it had
  // no actual effect on wake-word recognition - a slightly-misheard
  // top guess (e.g. "shadows" instead of "shadow") could fail to
  // match even though a lower-ranked alternative was correct.
  function findWakeWordInResult(result) {
    for (let a = 0; a < result.length; a++) {
      const transcript = (result[a].transcript || "").toLowerCase();
      const hit = WAKE_WORDS.find((w) => transcript.includes(w));
      if (hit) {
        const after = transcript.slice(transcript.indexOf(hit) + hit.length).trim();
        return { hit, after, transcript };
      }
    }
    return null;
  }

  if (SpeechRecognitionImpl) {
    recognizer = new SpeechRecognitionImpl();
    recognizer.lang = "en-US";
    recognizer.maxAlternatives = 3;

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

      // Keep manual capture alive through the short pauses that Chrome
      // commonly inserts before it emits a final transcript. The active
      // result handler still submits one final command and switches back
      // to wake/off mode, while an explicit mic click still stops it.
      recognizer.continuous = mode === "wake";

      recognizer.interimResults = mode === "wake";
      try {
        recognizer.start();
      } catch (e) {
        // Rare: browser says it's already running. Let the next
        // onend (or onerror, now that it also re-arms - see below)
        // retry rather than crash here.
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

    // Shared "the session is actually over" logic. Both onend AND
    // onerror (for error types that don't fire onend) call this so
    // recognizerRunning is guaranteed to get reset and the recognizer
    // gets re-armed into whatever mode was requested (or the
    // wake/off default). Before this fix, onerror never touched
    // recognizerRunning at all - only onend did - so for any browser
    // error type that fires onerror WITHOUT a following onend, the
    // flag stayed stuck at true forever. requestMode() would then
    // call .stop() on a recognizer that had already stopped, onend
    // would never fire to clear the flag, and both the wake toggle
    // and the mic button became permanently unresponsive until the
    // page was reloaded.
    function finishSession() {

      // Chrome can emit both `error` and `end` for one recognition
      // session.  Starting again from each handler races two calls to
      // recognizer.start(), leaving the recognizer silently stopped.
      // Coalesce those callbacks and re-arm it only once.
      if (finishingSession) return;
      finishingSession = true;
      recognizerRunning = false;
      micBtn.classList.remove("recording");
      if (voiceMode === "active" && presenceState === "listening") setPresence("idle");

      // Give the browser time to finish tearing down the previous
      // SpeechRecognition session before starting the next one.
      setTimeout(() => {
        const next = pendingMode !== null
          ? pendingMode
          : (voiceMode === "active" ? "active" : (wakeEnabled ? "wake" : "off"));
        pendingMode = null;
        finishingSession = false;
        applyMode(next);
      }, 100);
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
      // Browsers also stop recognition on their own after a pause in
      // speech even in continuous mode, so re-arm using whatever was
      // requested, or fall back to wake/off based on the toggle.
      finishSession();
    };

    recognizer.onerror = (e) => {
      setPresence("idle");

      console.warn("[Shadow][voice] recognition error:", e.error);



      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        // Mic permission denied - stop trying, don't loop forever.
        wakeEnabled = false;
        localStorage.setItem(WAKE_KEY, "0");
        pendingMode = "off";
        wakeToggle.dataset.state = "blocked";
        wakeToggle.querySelector(".wake-label").textContent = "mic blocked";

      } else if (e.error === "audio-capture") {
        setVoiceProblem("no microphone found");
      } else if (e.error === "network") {
        // Chrome's recognition engine needs a network connection. Do not
        // endlessly restart it; a new mic/wake click can retry later.
        setVoiceProblem("speech service offline");


      }

      // FIXED: previously this handler never reset recognizerRunning
      // or re-armed the recognizer - it relied entirely on onend to
      // do that, but some error types (this varies by browser) never
      // fire onend at all. That left recognizerRunning stuck at
      // `true`, so every future requestMode() call tried to stop an
      // already-stopped recognizer and nothing ever restarted -
      // effectively bricking wake word and the mic button until a
      // full page reload. onerror now always finishes the session
      // itself instead of assuming onend will follow.
      //
      // "no-speech" and other benign/transient errors just fall
      // through to the same recovery path - finishSession() re-arms
      // wake mode (or off) automatically.
      finishSession();
    };

    recognizer.onresult = (event) => {
      if (voiceMode === "active") {

        const result = event.results[event.results.length - 1];
        // A command must be final before it is sent. This keeps a
        // partial phrase from being submitted as an incomplete request.
        if (!result.isFinal) return;
        const transcript = result[0].transcript.trim();

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

          // Wake recognition uses interim results for responsiveness,
          // but acting on one cuts off phrases such as "Hey Shadow,
          // what time is it?" as soon as the first two words arrive.
          // Wait for the finalized phrase so its command is preserved.
          if (!event.results[i].isFinal) continue;


          // Check every alternative the recognizer offered for this
          // result, not just the top guess - this is what
          // maxAlternatives is actually for. A noisy environment can
          // easily make "shadow" the model's 2nd or 3rd guess instead
          // of its 1st.
          const found = findWakeWordInResult(event.results[i]);
          if (!found) continue;

          const { hit, after } = found;
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

        requestMode(wakeEnabled ? "wake" : "off");
        return;
      }
      startVoiceFromGesture("active");
    });

    wakeToggle.addEventListener("click", () => {
      if (wakeEnabled) {
        wakeEnabled = false;
        localStorage.setItem(WAKE_KEY, "0");
        requestMode("off");
      } else {
        startVoiceFromGesture("wake");
      }
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

  // ======


  // SYSTEM STATUS
  // ======

  function renderStatus(data) {
    if (typeof data.cpu === "number") {
      if (cpuVal) cpuVal.textContent = `${Math.round(data.cpu)}%`;
      if (cpuFill) cpuFill.style.width = `${Math.round(data.cpu)}%`;
    }
    if (typeof data.memory === "number") {
      if (memVal) memVal.textContent = `${Math.round(data.memory)}%`;
      if (memFill) memFill.style.width = `${Math.round(data.memory)}%`;
    }
    if (activeWindowEl) activeWindowEl.textContent = data.active_window || "–";
    if (batteryVal) batteryVal.textContent = data.battery != null ? `${data.battery}%` : "n/a";
    if (uptimeVal) uptimeVal.textContent = formatUptime(data.uptime_seconds);
  }

  function formatUptime(seconds) {
    if (!Number.isFinite(seconds)) return "--";
    const minutes = Math.floor(seconds / 60);
    const days = Math.floor(minutes / 1440);
    const hours = Math.floor((minutes % 1440) / 60);
    const rest = minutes % 60;
    return days ? `${days}d ${hours}h` : `${hours}h ${rest}m`;
  }

  async function refreshStatusOnce() {
    try {
      const data = await api("/api/status");
      renderStatus(data);
    } catch (e) {}
  }

  async function refreshInsights() {
    try {
      const relationship = await api("/api/relationship");
      renderRelationship(relationship);
    } catch (e) {
      console.debug("[Shadow] insight refresh failed:", e.message);
    }
  }

  function renderRelationship(data) {
    if (!data) return;
    const level = Number(data.level) || 1;
    const points = Number(data.points) || 0;
    if (relationshipLevel) relationshipLevel.textContent = `LVL ${level}`;
    if (relationshipPoints) relationshipPoints.textContent = points;
    if (relationshipProgress) relationshipProgress.style.width = `${Math.min(100, (points % 50) * 2)}%`;
    if (relationshipLast && data.last_interaction) {
      relationshipLast.textContent = `Last contact ${new Date(data.last_interaction).toLocaleString()}`;
    }
  }

  // ======
  // DESKTOP CONTROL
  // ======

  function logControl(text, cls) {
    const li = document.createElement("li");
    li.textContent = text;
    if (cls) li.className = cls;
    if (!controlLog) return;
    controlLog.querySelector(".empty-hint")?.remove();
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
      if (data.action === "sleep_shadow") {
        setPresence("idle");
        addBubble("system", "Shadow task stopped.");
      }
      logControl(`✓ ${result.result || data.action}`, "ok");
    }
  }

  function runAction(action, value, confirm = false) {
    send({ type: "action", action, value, confirm });
  }

  // ---- confirm modal for dangerous / lifecycle actions ----
  const ACTION_LABELS = {
    stop_server: "stop the server",
    restart: "restart the PC",
    sleep_shadow: "stop the current Shadow task",
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

  // ======

  // NOTIFICATIONS
  // ======

  function notify(title, body) {
    if (!("Notification" in window)) return;
    if (Notification.permission === "granted") {
      new Notification(title, { body });
    } else if (Notification.permission !== "denied") {
      Notification.requestPermission();
    }
  }

  // ======

  // BOOT
  // ======

  connect();

})();