# Shadow — Web Edition

Shadow as a real-time, LAN-accessible web app. Run one server on your
main PC; open the dashboard from your phone, tablet, or any other
laptop on the same Wi-Fi — no installs on those devices, no build
tooling, just a browser.

## What's new in this update

1. **Wake word** — say "Shadow" or "Hey Shadow" and the dashboard
   starts listening for a command, no more tapping the mic button
   first. Toggle it with the pill next to the connection indicator in
   the top bar (state is remembered per-browser). You can still tap
   the mic button any time for push-to-talk.
   - Fixed a race where the wake word itself ("shadow") could get sent
     straight to the LLM instead of being swallowed as the trigger -
     `recognizer.stop()` is asynchronous, so a trailing result from the
     wake-word utterance could still land after mode had already
     switched to "listening for a command". Mode changes now only
     happen from `onstart`/`onend`, never mid-utterance.
   - Shadow now greets you once a day ("Good morning/afternoon/evening.
     How can I help?") the first time you say the wake word, and gives
     a short acknowledgment ("Yes?", "Go ahead.", …) every other time -
     spoken instantly via the browser's built-in speech synthesis so
     there's no server round-trip before you start talking.
2. **"Stop Server" replaces "Shutdown"** — the old Shutdown button ran
   Windows' `shutdown /s /t 5` and turned off the whole PC. It now
   only stops the Shadow server process itself (`core/server_control.py`),
   leaving the PC running. Restart/Sleep still control the PC and still
   require confirmation.
3. **Real package layout** — `core/`, `ai/`, `integrations/`, `static/`,
   and `memory/` are now actual folders instead of a flat file dump
   (see layout below), matching what the imports already expected.
4. **Dead code removed**:
   - Duplicate daily-summary functions in `core/memory.py` (the
     `integrations/daily_memory.py` copy is the one that's actually
     used) — and the "what happened yesterday" feature is now wired
     up correctly, since nothing ever called `save_daily_summary()`
     before.
   - Unreachable branches in `core/skills.py` (time/date/app-opening
     could never fire the way `brain.py` called them).
   - The unused `keyboard` dependency in `requirements.txt`.
   - A **safety bug**: any chat message merely containing the word
     "restart" or "shutdown" used to restart/shut down the PC with
     zero confirmation. Those phrases now just point you to the
     dashboard's Power panel, which always asks first.
5. **"Add reminder" fixed** — `core/time_parser.py` only understood a
   few rigid phrasings before (e.g. "tomorrow 8 am" worked but
   "tomorrow at 8am" didn't). It now handles "in 10 minutes", "5 min",
   "at 6pm", "6:30pm", "18:30", "noon"/"midnight", "tomorrow at 8am",
   etc. Failures also now show an inline error right under the
   reminder form instead of only logging to the Control panel (which
   isn't visible while you're on the Reminders tab on mobile).

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

Requires Ollama running locally with the `phi3` model pulled
(`ollama pull phi3`).

## 2. Set your access token

Open `config.py` and change:

```python
API_TOKEN = "change-me-shadow-2026"
```

to something only you know. Every device has to enter this once (it's
then cached in that browser's `localStorage`). Set `ENABLE_AUTH = False`
only if you're on a network you fully trust and want to skip this.

## 3. Run the server

```bash
python server.py
```

You'll see something like:

```
Shadow web server ready.
Auth is ON - devices must supply the API token to connect.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## 4. Connect from any device

- On the same PC: open `http://localhost:8000`
- On your phone/another laptop: find this PC's LAN IP
  (Windows: `ipconfig`, look for "IPv4 Address", e.g. `192.168.1.23`),
  then open `http://192.168.1.23:8000` in a browser on the same Wi-Fi.
- Enter the access token once. You're in.

Voice input (wake word or manual mic) needs a Speech-API-capable
browser (Chrome or Edge work well; Safari support is limited). Text
input always works everywhere.

## Project layout

```
shadow/
  server.py                FastAPI app: REST + WebSocket + background tasks
  config.py                Assistant + web server settings (host, port, token)
  requirements.txt
  core/
    brain.py                Routes a message through skills/desktop control/AI
    memory.py                Short-term conversation + long-term facts (JSON)
    reminders.py
    desktop_control.py       App/window/volume control (Windows)
    server_control.py        NEW: stops the Shadow server itself (not the OS)
    system_status.py         CPU/RAM/active-window for the dashboard
    tts_service.py           Generates browser-playable mp3s via edge-tts
    relationship.py
    time_parser.py           Parses reminder "when" strings - now more forgiving
    file_indexer.py
    math_engine.py
    personality.py
    memory_extractor.py
    skills.py                Quick-answer skills only: math / time / date
  ai/
    llm.py                   Ollama call (runs in a thread so it never
                              blocks other connected devices)
  integrations/
    memory_integration.py
    daily_memory.py
  static/
    index.html               Dashboard shell
    css/style.css            Dark console theme, signature "presence" ring
    js/app.js                WebSocket client, wake word + voice input,
                              reminders, desktop controls
    audio/                   Generated TTS clips (auto-cleaned after 10 min)
  memory/                    JSON data files (conversation, facts, reminders, ...)
```

## How the pieces talk to each other

- **Chat**: browser sends `{"type":"chat","text":"..."}` over the
  WebSocket (typed, tapped mic, or triggered by the wake word) →
  server runs `core.brain.process()` → broadcasts the reply (+ a TTS
  audio URL) to **every** connected device, so all your screens stay
  in sync.
- **Reminders**: a background task polls `get_due_reminders()` every
  couple seconds and pushes any that fire to all devices, with a
  spoken TTS clip. Adding one from the dashboard now surfaces parse
  errors inline instead of only in the (easy-to-miss) control log.
- **Desktop control**: buttons in the "Quick actions" / "Power" panels
  send `{"type":"action","action":"open","value":"chrome"}`. Actions
  in `CONFIRM_REQUIRED_ACTIONS` (`stop_server` / `restart` / `sleep_pc`
  / `close`) come back as `confirm_required` first — the browser shows
  a confirmation dialog, and only resends with `confirm:true` if you
  approve.
- **Status**: CPU/RAM/active window broadcast every few seconds via
  `core/system_status.py` (uses `psutil` + `pygetwindow`).

## Known limitation worth knowing about

The web dashboard is the only interface now — there's no separate
always-listening desktop process to worry about racing with it, since
`memory/*.json` is only ever written by this one server process.

## Next steps to build on this

- Add a proper login (per-device name/avatar) instead of one shared token
- Push notifications for reminders when the tab isn't focused (Web Push)
- A "who's connected" panel so you can see which devices are live
- Per-device pairing-code auth instead of the shared-secret token, if
  you want tighter per-device control
"# Shadow-AI-assisstant" 
"# Shadow-AI-assisstant" 
=======
# Shadow-AI-assisstant
Shadow is a locally-hosted, voice-activated AI assistant you're building that runs entirely on your own Windows PC and is accessible from any device on your home network — phone, tablet, laptop — through a browser, with no installs needed on those other devices.
>>>>>>> 2d86bee20ac872666b1427d50322d9f9e69e35af
"# Shadow-AI-assisstant" 
"# Shadow-AI-assisstant" 
"# Shadow-AI-assisstant" 
"# Shadow-AI-assisstant" 
"# Shadow-AI-assisstant" 
