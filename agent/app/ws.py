import json
from fastapi import WebSocket

clients: list[WebSocket] = []


async def broadcast(event_type: str, data: dict):
    msg = json.dumps({"type": event_type, **data}, default=str)
    dead = []
    for ws in clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.remove(ws)