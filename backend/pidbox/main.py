"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pidbox.api import analysis, sessions, settings, sysid, ws
from pidbox.session import session_manager


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    session_manager.cleanup()


app = FastAPI(
    title="PIDToolBox API",
    version="0.1.33",
    description="Python backend for multirotor PID tuning log analysis",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(sysid.router, prefix="/api/analysis/sysid", tags=["sysid"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(ws.router, prefix="/api/ws", tags=["websocket"])


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.6"}
