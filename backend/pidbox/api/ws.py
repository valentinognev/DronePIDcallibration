"""WebSocket for long-running analysis progress."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/progress/{task_id}")
async def progress_ws(websocket: WebSocket, task_id: str):
    await websocket.accept()
    try:
        for pct in range(0, 101, 10):
            await websocket.send_text(json.dumps({"task_id": task_id, "progress": pct}))
            await asyncio.sleep(0.05)
        await websocket.send_text(json.dumps({"task_id": task_id, "progress": 100, "done": True}))
    except WebSocketDisconnect:
        pass
