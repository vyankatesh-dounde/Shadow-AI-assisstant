# core/server_control.py
#
# Replaces the old "shutdown" desktop action. That used to call
# `shutdown /s /t 5` and turn off the whole Windows PC, which is not
# what people expect from a "Shutdown" button in a web dashboard.
# This instead stops the local server.py process (the thing hosting
# this dashboard) - the PC itself is left alone.

import asyncio
import os
import signal

_server = None  # the running uvicorn.Server instance, set by server.py


def register_server(server):
    """Called once from server.py's __main__ block so this module can
    ask uvicorn to exit gracefully instead of killing the process."""
    global _server
    _server = server


def request_stop():
    """Flip uvicorn's graceful-exit flag if we have a reference to the
    server; otherwise fall back to signalling this process directly.
    Either way this only ever affects the Shadow server process, never
    the host OS."""
    if _server is not None:
        _server.should_exit = True
    else:
        os.kill(os.getpid(), signal.SIGTERM)


async def stop_server(delay: float = 1.0) -> str:
    """Schedule the server to stop shortly after this returns, so the
    caller (an HTTP/WebSocket handler) has time to send its response
    and the broadcast reaches every connected browser first."""

    async def _delayed_stop():
        await asyncio.sleep(delay)
        request_stop()

    asyncio.create_task(_delayed_stop())
    return "Stopping the Shadow server. This dashboard will disconnect."
