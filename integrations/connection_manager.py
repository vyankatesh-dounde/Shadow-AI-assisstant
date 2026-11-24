"""Connection layer: manage browser and future device WebSocket connections."""

import asyncio
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, message: dict):
        disconnected = []
        async def send(websocket: WebSocket):
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.append(websocket)

        if self.active:
            await asyncio.gather(*(send(websocket) for websocket in tuple(self.active)))
        for websocket in disconnected:
            self.disconnect(websocket)
