"""Function layer: execute assistant capabilities independent of HTTP/WebSockets."""

import asyncio

from config import CONFIRM_REQUIRED_ACTIONS
from core.desktop_control import (
    cancel_shutdown, close_app, close_window, minimize_all, open_app,
    open_smart, open_website, play_pause, restart, search_google, sleep_pc,
    show_all_windows, switch_window, switch_window_back, type_text,
    volume_down, volume_up,
)
from core.file_indexer import build_index, open_indexed
from core.server_control import stop_server


def _run_desktop_action(action: str, value):
    """Run a short synchronous desktop action."""
    actions = {
        "open": lambda: open_app(value or ""), "open_website": lambda: open_website(value or ""),
        "search": lambda: search_google(value or ""), "close": lambda: close_app(value or ""),
        "close_window": close_window, "switch_window": switch_window,
        "switch_window_back": switch_window_back, "show_all_windows": show_all_windows,
        "minimize_all": minimize_all, "volume_up": volume_up, "volume_down": volume_down,
        "type_text": lambda: type_text(value or ""), "play_pause": play_pause,
        "restart": restart, "sleep_pc": sleep_pc, "cancel_shutdown": cancel_shutdown,
    }
    handler = actions.get(action)
    return handler() if handler else None


async def run_action(action: str, value, confirm: bool) -> dict:
    """Validate and run an action without HTTP, WebSocket, or UI concerns."""
    if action in CONFIRM_REQUIRED_ACTIONS and not confirm:
        return {"status": "confirm_required", "action": action, "value": value}
    if action == "stop_server":
        return {"status": "ok", "result": await stop_server()}
    if action == "open_smart":
        result = await asyncio.to_thread(open_smart, value or "")
    elif action == "open_indexed":
        result = await asyncio.to_thread(open_indexed, value or "")
    elif action == "index_files":
        result = await asyncio.to_thread(build_index)
    else:
        result = await asyncio.to_thread(_run_desktop_action, action, value)
    if result is None:
        return {"status": "error", "result": f"Unknown action '{action}'"}
    return {"status": "ok", "result": result}
