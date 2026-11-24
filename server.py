import asyncio 
import hmac
import re
import sys
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from config import (
    ASSISTANT_NAME, HOST, PORT, ENABLE_AUTH, API_TOKEN, ALLOWED_ORIGINS,
    CHAT_RATE_LIMIT_MAX_MESSAGES, CHAT_RATE_LIMIT_WINDOW_SECONDS,
    STATIC_CACHE_CONTROL,
)
from core.personality import Personality
from core.brain import agent, process
from agent.schemas import AgentState
from core.memory import load_conversation, load_facts, clear_conversation
from core.memory import load_relationship
from core.reminders import (
    add_reminder, list_reminders, delete_reminder, clear_reminders,
)
from core.reminders import parse_time
from core.system_status import get_status
from core.tts_service import synthesize
from core.action_service import run_action
from integrations.events import broadcast_status, watch_reminders, ConnectionManager
from integrations.webrtc_audio import (
    close_all_audio_sessions,
    close_audio_session,
    create_audio_session,
    finish_audio_session,
    stream_tts_to_session,
)
from memory.storage import rebuild_file_index

BASE_DIR = Path(__file__).resolve().parent
MAX_MESSAGE_CHARS = 4_000

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- startup ----

    if ENABLE_AUTH and API_TOKEN == "change-me-shadow-2026":
        raise RuntimeError(
            "Set a unique API_TOKEN in config.py before exposing Shadow on a network."
        )
    if HOST not in {"127.0.0.1", "localhost", "::1"} and not ENABLE_AUTH:
        raise RuntimeError("ENABLE_AUTH must be True when HOST is not local-only.")
    reminder_task = asyncio.create_task(watch_reminders(manager))
    status_task = asyncio.create_task(broadcast_status(manager))
    asyncio.create_task(asyncio.to_thread(rebuild_file_index))

    print(f"{ASSISTANT_NAME} web server ready.")
    if ENABLE_AUTH:
        print("Auth is ON - devices must supply the API token to connect.")
    else:
        print("WARNING: Auth is OFF - anyone on your network can use this. Set ENABLE_AUTH = True in config.py.")

    yield

    # ---- shutdown ----
    reminder_task.cancel()
    status_task.cancel()
    for t in (reminder_task, status_task):
        try:
            await t
        except asyncio.CancelledError:
            pass
    await close_all_audio_sessions()


app = FastAPI(title=f"{ASSISTANT_NAME} Web", lifespan=lifespan)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), geolocation=(), payment=()"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Token"],
)

class NoCacheStaticFiles(StaticFiles):
    """Plain StaticFiles lets browsers cache app.js/style.css
    indefinitely, so a code update can silently keep running the OLD
    file until the person manually hard-refreshes - which looks
    exactly like "the fix didn't work" from the outside. This forces
    a fresh fetch every time instead."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = STATIC_CACHE_CONTROL
        return response


app.mount("/static", NoCacheStaticFiles(directory=str(BASE_DIR / "static")), name="static")
personality = Personality()
chat_lock = asyncio.Lock()

# =
# 🔐 AUTH
# =

def check_token(token: Optional[str]) -> bool:
    if not ENABLE_AUTH:
        return True
 
    return bool(token) and hmac.compare_digest(token, API_TOKEN)


def origin_allowed(origin: Optional[str]) -> bool:
    return not origin or "*" in ALLOWED_ORIGINS or origin in ALLOWED_ORIGINS


def chat_rate_limited(message_times, now: Optional[float] = None) -> bool:
    now = time.monotonic() if now is None else now
    while message_times and now - message_times[0] > CHAT_RATE_LIMIT_WINDOW_SECONDS:
        message_times.popleft()
    if len(message_times) >= CHAT_RATE_LIMIT_MAX_MESSAGES:
        return True
    message_times.append(now)
    return False

def require_token(request: Request):
    token = request.headers.get("X-API-Token") or request.query_params.get("token")
    if not check_token(token):
        raise HTTPException(status_code=401, detail="Invalid or missing API token")

manager = ConnectionManager()
active_chat_tasks: set[asyncio.Task] = set()


def cancel_active_chat_tasks() -> int:
    cancelled = 0
    for task in tuple(active_chat_tasks):
        if not task.done():
            task.cancel()
            cancelled += 1
    return cancelled


async def broadcast_agent_state():
    await manager.broadcast({
        "type": "agent_state",
        "state": agent.conversation.state.state.value,
    })

# =
# 🏠 STATIC PAGES
# =

@app.get("/")
async def index():
    return FileResponse(
        str(BASE_DIR / "static" / "index.html"),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )

# =
# 💬 REST: CONVERSATION / FACTS
# =

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


# =
# ⏰ REST: REMINDERS
# =

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

# =
# 🖥️ REST: SYSTEM STATUS + DESKTOP CONTROL
# =

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

    result = await run_action(action, value, confirm, cancel_active_chat_tasks)
    await manager.broadcast({"type": "desktop_event", "action": action, "value": value, "result": result})
    return result

# =
# 🔊 REST: ON-DEMAND TTS (used if a client wants Shadow to
# re-speak something, e.g. tapping a message bubble)
# =

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


@app.post("/api/webrtc/offer")
async def api_webrtc_offer(request: Request):
    require_token(request)
    try:
        return await create_audio_session(await request.json())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.delete("/api/webrtc/{session_id}")
async def api_webrtc_close(session_id: str, request: Request):
    require_token(request)
    await close_audio_session(session_id)
    return {"status": "closed"}


def _speech_segments(buffer: str, final: bool = False) -> tuple[list[str], str]:
    segments = []
    start = 0
    for index, character in enumerate(buffer):
        if character in ".!?。！？" and (
            index + 1 == len(buffer) or buffer[index + 1].isspace()
        ):
            segment = buffer[start:index + 1].strip()
            if segment:
                segments.append(segment)
            start = index + 1
        elif index - start >= 180 and character.isspace():
            segment = buffer[start:index].strip()
            if segment:
                segments.append(segment)
            start = index + 1

    remaining = buffer[start:]
    if final and remaining.strip():
        segments.append(remaining.strip())
        remaining = ""
    return segments, remaining


# =
# 🔌 WEBSOCKET: REAL-TIME CHAT + LIVE EVENTS
# =

async def handle_chat_message(text: str, audio_session_id: str | None = None):
    await manager.broadcast({"type": "user_message", "text": text})
    agent.conversation.update(state=AgentState.THINKING)
    await broadcast_agent_state()

    stream_started = False
    speech_started = False
    speech_buffer = ""
    speech_queue: asyncio.Queue[str | None] = asyncio.Queue()
    speech_task = None

    if audio_session_id:
        async def synthesize_queued_speech():
            nonlocal speech_started
            while True:
                segment = await speech_queue.get()
                if segment is None:
                    return
                try:
                    streamed = await stream_tts_to_session(audio_session_id, segment)
                    if streamed and not speech_started:
                        speech_started = True
                        await manager.broadcast({
                            "type": "webrtc_audio_started",
                            "session_id": audio_session_id,
                        })
                except Exception as error:
                    print("WebRTC TTS error:", error)

        speech_task = asyncio.create_task(synthesize_queued_speech())

    async def on_chunk(chunk: str):
        nonlocal stream_started, speech_buffer
        if not chunk:
            return
        if not stream_started:
            await manager.broadcast({"type": "response_start", "text": ""})
            stream_started = True
        await manager.broadcast({"type": "response_chunk", "text": chunk})
        if speech_task:
            speech_buffer += chunk
            segments, speech_buffer = _speech_segments(speech_buffer)
            for segment in segments:
                speech_queue.put_nowait(segment)

    try:
        async with chat_lock:
            reply = await process(text, personality, on_chunk=on_chunk)
    except asyncio.CancelledError:
        if speech_task:
            speech_task.cancel()
        if audio_session_id:
            finish_audio_session(audio_session_id)
        agent.conversation.update(state=AgentState.IDLE)
        await broadcast_agent_state()
        raise

    if speech_task:
        segments, speech_buffer = _speech_segments(speech_buffer, final=True)
        for segment in segments:
            speech_queue.put_nowait(segment)
        speech_queue.put_nowait(None)
        await speech_task
        finish_audio_session(audio_session_id)

    audio_url = None
    if not speech_started:
        try:
            audio_url = await synthesize(reply)
        except Exception as e:
            print("TTS error:", e)

    if stream_started:
        await manager.broadcast({
            "type": "response_end",
            "text": reply,
            "audio_url": audio_url,
        })
    else:
        await manager.broadcast({
            "type": "response",
            "text": reply,
            "audio_url": audio_url,
        })
    await broadcast_agent_state()
    await manager.broadcast({
        "type": "reminders_updated",
        "reminders": list_reminders(),
    })

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: Optional[str] = Query(default=None)):
    if not origin_allowed(ws.headers.get("origin")):
        await ws.close(code=4403)
        return
    if not check_token(token):
        await ws.close(code=4401)
        return

    await manager.connect(ws)
    message_times = deque()

    try:
        # Greet this device with current state on connect
        await ws.send_json({"type": "conversation", "history": load_conversation()})
        await ws.send_json({"type": "reminders_updated", "reminders": list_reminders()})
        await ws.send_json({"type": "status", **get_status()})
        await ws.send_json({
            "type": "agent_state",
            "state": agent.conversation.state.state.value,
        })

        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")

            if msg_type == "chat":
                text = (data.get("text") or "").strip()
                audio_session_id = data.get("audio_session_id")
                if not isinstance(audio_session_id, str):
                    audio_session_id = None
                if not text:
                    continue
                if len(text) > MAX_MESSAGE_CHARS:
                    await ws.send_json({"type": "error", "message": "Message is too long."})
                    continue

                if chat_rate_limited(message_times):
                    await ws.send_json({"type": "error", "message": "Too many messages. Please wait a moment."})
                    continue

                cancel_active_chat_tasks()
                task = asyncio.create_task(handle_chat_message(text, audio_session_id))
                active_chat_tasks.add(task)
                task.add_done_callback(active_chat_tasks.discard)



            elif msg_type == "cancel":
                cancelled = cancel_active_chat_tasks()
                agent.conversation.reset()
                await broadcast_agent_state()
                await ws.send_json({
                    "type": "cancelled",
                    "cancelled_tasks": cancelled,
                })

            elif msg_type == "action":
                action = data.get("action")
                value = data.get("value")
                confirm = bool(data.get("confirm", False))

                if not action:
                    await ws.send_json({"type": "error", "message": "Missing 'action'"})
                    continue

                result = await run_action(action, value, confirm, cancel_active_chat_tasks)
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

if __name__ == "__main__":
    import uvicorn
    import webbrowser

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

    async def serve_and_open_dashboard():
        serve_task = asyncio.create_task(uv_server.serve())
        while not uv_server.started and not serve_task.done():
            await asyncio.sleep(0.1)

        if uv_server.started:
            browser_host = HOST if HOST not in {"0.0.0.0", "::"} else "127.0.0.1"
            if ":" in browser_host:
                browser_host = f"[{browser_host}]"
            dashboard_url = f"http://{browser_host}:{PORT}"
            print(f"Opening Shadow dashboard: {dashboard_url}")
            try:
                opened = await asyncio.to_thread(webbrowser.open, dashboard_url)
                if not opened:
                    print("Could not open a browser automatically. Use the URL above.")
            except webbrowser.Error as error:
                print(f"Could not open a browser automatically: {error}")

        await serve_task

    asyncio.run(serve_and_open_dashboard())
