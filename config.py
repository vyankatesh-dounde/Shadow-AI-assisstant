ASSISTANT_NAME = "Shadow"

DEFAULT_MODE = "assistant"

VOICE = "en-US-BrianNeural"
VOICE_PITCH = "-2Hz"
USE_RVC_VOICE = False

OLLAMA_MODEL = "phi3"
OLLAMA_URL = "http://localhost:11434/api/generate"

# Words that wake the dashboard's microphone out of passive listening.
# Used by static/js/app.js (kept here too so server + client agree).
WAKE_WORDS = ["hey shadow", "shadow"]

# ====
# 🌐 WEB SERVER SETTINGS
# ====

HOST = "127.0.0.1"
PORT = 8000
# Simple shared-secret auth. Every browser tab must supply this token once
# (it's then cached in that browser's localStorage).
# CHANGE THIS before using Shadow on any network you don't fully trust -
# it must NOT be left as an IP address or any other guessable default.
#
ENABLE_AUTH = False

# Set this to a long, random secret before starting the server.
# The server deliberately refuses to start while this placeholder remains.
API_TOKEN = "change-me-shadow-2026"

# CORS origins allowed to talk to the API. "*" is convenient for a closed
# home LAN; tighten this if you expose the server more broadly.
# Keep this same-origin by default. Add explicit origins only if you host
# the dashboard behind another trusted domain.
ALLOWED_ORIGINS = ["*"]

# Actions that require an explicit confirmation flag from the client
# before core/desktop_control.py (or core/server_control.py) will run
# them. "stop_server" replaces the old "shutdown" action - it stops
# THIS process, not the Windows PC.
CONFIRM_REQUIRED_ACTIONS = {"stop_server", "restart", "sleep_shadow", "sleep_pc", "close"}

# How often (seconds) the server checks for due reminders and pushes
# them to all connected clients.
REMINDER_POLL_INTERVAL = 2
# How often (seconds) the server broadcasts system status (CPU/RAM/active window).
STATUS_BROADCAST_INTERVAL = 3