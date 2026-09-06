# Shadow

Shadow is a locally hosted Windows assistant with a browser dashboard, voice input, reminders, local Ollama replies, and a Three.js hologram.

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Pull the configured Ollama model: `ollama pull phi3`
3. In `config.py`, replace `API_TOKEN` with a long random secret.
4. Start the server: `python server.py`
5. Open `http://localhost:8000`, or the PC's LAN IP from a trusted device.

The server refuses to start with the placeholder token. It binds to all interfaces by default, so keep authentication enabled and do not share the token outside your trusted network.

## Notes

- Chat, wake-word recognition, and reminder creation are available in the dashboard. Browser speech recognition works best in Chrome or Edge.
- Desktop and power controls are available through the authenticated API and require confirmation where an action can close, restart, sleep, or stop something.
- Web results use DuckDuckGo's instant-answer endpoint. The assistant never sends keyboard shortcuts or reads the clipboard to search.
- The 3D hologram imports Three.js from jsDelivr; it needs internet access on first load. Chat remains usable if that renderer cannot load.
