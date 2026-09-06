import asyncio
import hmac
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from config import (
    ASSISTANT_NAME, HOST, PORT, ENABLE_AUTH, API_TOKEN, ALLOWED_ORIGINS,
)

from core.personality import Personality
from core.brain import process
from core.memory import load_conversation, load_facts, clear_conversation
from core.relationship import load_relationship
from core.reminders import (
    add_reminder, list_reminders, delete_reminder, clear_reminders,
)
from core.time_parser import parse_time
from core.system_status import get_status
from core.tts_service import synthesize
from core.action_service import run_action
from integrations.background_events import broadcast_status, watch_reminders
from integrations.connection_manager import ConnectionManager

BASE_DIR = Path(__file__).resolve().parent
MAX_MESSAGE_CHARS = 4_000


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- startup ----
    if ENABLE_AUTH and API_TOKEN == "change-this-to-a-long-random-secret":
        raise RuntimeError(
            "Set a unique API_TOKEN in config.py before exposing Shadow on a network."
        )
    reminder_task = asyncio.create_task(watch_reminders(manager))
    status_task = asyncio.create_task(broadcast_status(manager))

    print(f"{ASSISTANT_NAME} web server ready.")
    if ENABLE_AUTH:
        print("Auth is ON - devices must supply the API token to connect.")
    else:
        print("⚠️  Auth is OFF - anyone on your network can use this. Set ENABLE_AUTH = True in config.py.")

    yield

    # ---- shutdown ----
    reminder_task.cancel()
    status_task.cancel()
    for t in (reminder_task, status_task):
        try:
            await t
        except asyncio.CancelledError:
            pass


app = FastAPI(title=f"{ASSISTANT_NAME} Web", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class NoCacheStaticFiles(StaticFiles):
    """Plain StaticFiles lets browsers cache app.js/style.css
    indefinitely, so a code update can silently keep running the OLD
    file until the person manually hard-refreshes - which looks
    exactly like "the fix didn't work" from the outside. This forces
    a fresh fetch every time instead."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        return response


app.mount("/static", NoCacheStaticFiles(directory=str(BASE_DIR / "static")), name="static")

personality = Personality()
chat_lock = asyncio.Lock()

# =========================================================
# 🔐 AUTH
# =========================================================

def check_token(token: Optional[str]) -> bool:
    if not ENABLE_AUTH:
        return True
    return bool(token) and hmac.compare_digest(token, API_TOKEN)


def require_token(request: Request):
    token = request.headers.get("X-API-Token") or request.query_params.get("token")
    if not check_token(token):
        raise HTTPException(status_code=401, detail="Invalid or missing API token")


# =========================================================
# 🔌 CONNECTION MANAGER (broadcasts to every connected device)
# =========================================================

manager = ConnectionManager()

# =========================================================
# ⚙️ DESKTOP ACTION MAP
# =========================================================

# =========================================================
# 🏠 STATIC PAGES
# =========================================================

@app.get("/")
async def index():
    return FileResponse(str(BASE_DIR / "static" / "index.html"))


# =========================================================
# 💬 REST: CONVERSATION / FACTS
# =========================================================

@app.get("/api/conversation")
async def api_conversation(request: Request):
    require_token(request)
    return load_conversation()


@app.delete("/api/conversation")
async def api_clear_conversation(request: Request):
    require_token(request)
    clear_conversation()
    await manager.broadcast({"type": "conversation_cleared"})
    return {"status": "ok"}


@app.get("/api/facts")
async def api_facts(request: Request):
    require_token(request)
    return load_facts()


@app.get("/api/relationship")
async def api_relationship(request: Request):
    require_token(request)
    return load_relationship()


# =========================================================
# ⏰ REST: REMINDERS
# =========================================================

@app.get("/api/reminders")
async def api_list_reminders(request: Request):
    require_token(request)
    return list_reminders()


@app.post("/api/reminders")
async def api_add_reminder(request: Request):
    require_token(request)
    body = await request.json()
    text = (body.get("text") or "").strip()
    when = (body.get("when") or "").strip()

    if not text:
        raise HTTPException(status_code=400, detail="Reminder text is required")
    if len(text) > MAX_MESSAGE_CHARS:
        raise HTTPException(status_code=400, detail="Reminder text is too long")
    if not when:
        raise HTTPException(status_code=400, detail="Reminder time is required")

    trigger_time = parse_time(when)
    if trigger_time is None:
        raise HTTPException(
            status_code=400,
            detail=f"Couldn't understand the time '{when}'. Try things like "
                   f"'in 10 minutes', 'at 6pm', or 'tomorrow at 8am'.",
        )

    add_reminder(text, trigger_time)
    reminders = list_reminders()
    await manager.broadcast({"type": "reminders_updated", "reminders": reminders})
    return {"status": "ok", "reminders": reminders}


@app.delete("/api/reminders/{reminder_id}")
async def api_delete_reminder(reminder_id: str, request: Request):
    require_token(request)
    delete_reminder(reminder_id)
    reminders = list_reminders()
    await manager.broadcast({"type": "reminders_updated", "reminders": reminders})
    return {"status": "ok", "reminders": reminders}


@app.delete("/api/reminders")
async def api_clear_reminders(request: Request):
    require_token(request)
    clear_reminders()
    await manager.broadcast({"type": "reminders_updated", "reminders": []})
    return {"status": "ok"}


# =========================================================
# 🖥️ REST: SYSTEM STATUS + DESKTOP CONTROL
# =========================================================

@app.get("/api/status")
async def api_status(request: Request):
    require_token(request)
    return get_status()


@app.post("/api/desktop/action")
async def api_desktop_action(request: Request):
    require_token(request)
    body = await request.json()
    action = body.get("action")
    value = body.get("value")
    confirm = bool(body.get("confirm", False))

    if not action:
        raise HTTPException(status_code=400, detail="Missing 'action'")

    result = await run_action(action, value, confirm)
    await manager.broadcast({"type": "desktop_event", "action": action, "value": value, "result": result})
    return result


# =========================================================
# 🔊 REST: ON-DEMAND TTS (used if a client wants Shadow to
# re-speak something, e.g. tapping a message bubble)
# =========================================================

@app.post("/api/tts")
async def api_tts(request: Request):
    require_token(request)
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Missing 'text'")
    if len(text) > MAX_MESSAGE_CHARS:
        raise HTTPException(status_code=400, detail="Text is too long")
    url = await synthesize(text)
    return {"audio_url": url}


# =========================================================
# 🔌 WEBSOCKET: REAL-TIME CHAT + LIVE EVENTS
# =========================================================

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: Optional[str] = Query(default=None)):
    if not check_token(token):
        await ws.close(code=4401)
        return

    await manager.connect(ws)

    try:
        # Greet this device with current state on connect
        await ws.send_json({"type": "conversation", "history": load_conversation()})
        await ws.send_json({"type": "reminders_updated", "reminders": list_reminders()})
        await ws.send_json({"type": "status", **get_status()})

        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")

            if msg_type == "chat":
                text = (data.get("text") or "").strip()
                if not text:
                    continue
                if len(text) > MAX_MESSAGE_CHARS:
                    await ws.send_json({"type": "error", "message": "Message is too long."})
                    continue

                # Let every connected device see the user's message immediately
                await manager.broadcast({"type": "user_message", "text": text})

                # Conversation/memory JSON files are read-modify-written.
                # Serializing turns prevents concurrent clients from losing
                # each other's messages or reminder updates.
                async with chat_lock:
                    reply = await process(text, personality)

                audio_url = None
                try:
                    audio_url = await synthesize(reply)
                except Exception as e:
                    print("TTS error:", e)

                await manager.broadcast({
                    "type": "response",
                    "text": reply,
                    "audio_url": audio_url,
                })

                # brain.py may have just created a reminder from a
                # natural-language request ("remind me to..."); push
                # the current list so it shows up without a refresh.
                await manager.broadcast({
                    "type": "reminders_updated",
                    "reminders": list_reminders(),
                })

            elif msg_type == "action":
                action = data.get("action")
                value = data.get("value")
                confirm = bool(data.get("confirm", False))

                if not action:
                    await ws.send_json({"type": "error", "message": "Missing 'action'"})
                    continue

                result = await run_action(action, value, confirm)
                await manager.broadcast({
                    "type": "desktop_event",
                    "action": action,
                    "value": value,
                    "result": result,
                })

            elif msg_type == "ping":
                await ws.send_json({"type": "pong"})

            else:
                await ws.send_json({"type": "error", "message": f"Unknown message type '{msg_type}'"})

    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception as e:
        print("WebSocket error:", e)
        manager.disconnect(ws)


# =========================================================
# 🔁 BACKGROUND TASKS
# =========================================================

if __name__ == "__main__":
    import uvicorn
    from core.server_control import register_server

    # Windows' default ProactorEventLoop logs a noisy (harmless)
    # "ConnectionResetError ... _call_connection_lost" traceback whenever
    # a browser tab closes/refreshes mid-request (very common with the
    # <audio> tag's range requests). Switching to the selector loop here
    # avoids that log spam. We don't need Proactor's subprocess features
    # for this server, so this trade-off is free.
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Built manually (instead of uvicorn.run(...)) so the "Stop Server"
    # dashboard action can flip server.should_exit and shut this
    # process down gracefully - see core/server_control.py.
    uv_config = uvicorn.Config("server:app", host=HOST, port=PORT, reload=False)
    uv_server = uvicorn.Server(uv_config)
    register_server(uv_server)

    asyncio.run(uv_server.serve())
