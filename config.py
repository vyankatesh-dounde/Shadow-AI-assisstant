ASSISTANT_NAME = "Shadow"

DEFAULT_MODE = "assistant"

VOICE = "en-US-GuyNeural"
VOICE_PITCH = "-2Hz"

OLLAMA_MODEL = "phi3"
OLLAMA_URL = "http://localhost:11434/api/generate"

# Words that wake the dashboard's microphone out of passive listening.
# Used by static/js/app.js (kept here too so server + client agree).
WAKE_WORDS = ["hey shadow", "shadow"]

# =========================
# 🌐 WEB SERVER SETTINGS
# =========================

# Listen on all interfaces so devices on the same Wi-Fi/LAN can reach it.
# Access it from another device using this machine's LAN IP, e.g. http://192.168.1.23:8000
#
# FIXED: this was previously set to 127.0.0.1, which only accepts
# connections FROM this same PC - no phone/laptop on the LAN could
# ever reach the dashboard, contradicting the whole "accessible across
# a home network via browser" design. It must be 0.0.0.0 for LAN
# access to actually work.
HOST = "0.0.0.0"
PORT = 8000

# Simple shared-secret auth. Every browser tab must supply this token once
# (it's then cached in that browser's localStorage).
# CHANGE THIS before using Shadow on any network you don't fully trust -
# it must NOT be left as an IP address or any other guessable default.
#
# NOTE: now that HOST is 0.0.0.0, this server is reachable by anything
# on your LAN, not just this PC. Strongly consider setting
# ENABLE_AUTH = True and changing API_TOKEN below before relying on
# HOST = "0.0.0.0" outside a fully trusted home network.
ENABLE_AUTH = False
API_TOKEN = "change-me-shadow-2026"

# CORS origins allowed to talk to the API. "*" is convenient for a closed
# home LAN; tighten this if you expose the server more broadly.
ALLOWED_ORIGINS = ["*"]

# Actions that require an explicit confirmation flag from the client
# before core/desktop_control.py (or core/server_control.py) will run
# them. "stop_server" replaces the old "shutdown" action - it stops
# THIS process, not the Windows PC.
CONFIRM_REQUIRED_ACTIONS = {"stop_server", "restart", "sleep_pc", "close"}

# How often (seconds) the server checks for due reminders and pushes
# them to all connected clients.
REMINDER_POLL_INTERVAL = 2

# How often (seconds) the server broadcasts system status (CPU/RAM/active window).
STATUS_BROADCAST_INTERVAL = 3