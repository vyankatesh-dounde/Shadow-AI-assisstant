# Shadow's three-layer architecture

## 1. Animation and presentation (`static/`)

The browser UI, microphone controls, CSS, and `hologram.js` render the
assistant state. This layer sends intent messages but never runs desktop
commands or talks directly to the LLM.

## 2. Functions (`core/`, `ai/`)

Shadow's capabilities live here: AI replies, memory, reminders, TTS, file
indexing, and desktop automation. `core/action_service.py` is the transport-
independent entry point for device/dashboard actions.

## 3. Connections (`server.py`, `integrations/`)

This layer provides HTTP, WebSockets, authentication, client broadcasting, and
periodic events. Future wired, Bluetooth, Wi-Fi, or phone connectors belong in
`integrations/` and should call the function layer, never the UI directly.

```text
browser / microphone / LAN device
               -> connection layer -> function layer
               <- connection layer <- function result
               -> animation/UI state
```
