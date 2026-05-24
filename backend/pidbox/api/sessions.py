"""Session management API routes."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from pidbox.api.schemas import (
    CreateSessionRequest,
    EpochUpdate,
    FileInfo,
    SessionResponse,
    TraceRequest,
)
from pidbox.core.loader import list_firmwares
from pidbox.core.traces import extract_log_viewer_traces, list_available_traces
from pidbox.session import session_manager

router = APIRouter()


@router.get("/firmwares")
def get_firmwares():
    return list_firmwares()


@router.post("", response_model=SessionResponse)
def create_session(req: CreateSessionRequest):
    session = session_manager.create(firmware=req.firmware)
    return SessionResponse(session_id=session.session_id, firmware=session.firmware)


@router.get("/{session_id}")
def get_session(session_id: str):
    try:
        session = session_manager.get(session_id)
    except KeyError:
        raise HTTPException(404, "Session not found")
    files = [
        FileInfo(
            file_id=f.file_id,
            original_name=f.original_name,
            log_count=len(f.logs),
            log_names=[log.name for log in f.logs],
        )
        for f in session.files
    ]
    return {"session_id": session_id, "firmware": session.firmware, "files": files}


@router.delete("/{session_id}")
def delete_session(session_id: str):
    try:
        session_manager.delete(session_id)
    except KeyError:
        raise HTTPException(404, "Session not found")
    return {"ok": True}


@router.post("/{session_id}/files")
async def upload_file(
    session_id: str,
    file: UploadFile = File(...),
):
    try:
        content = await file.read()
        sf = session_manager.add_file(
            session_id,
            file.filename or "upload.bbl",
            content,
        )
    except KeyError:
        raise HTTPException(404, "Session not found")
    except Exception as e:
        raise HTTPException(400, str(e))

    return FileInfo(
        file_id=sf.file_id,
        original_name=sf.original_name,
        log_count=len(sf.logs),
        log_names=[log.name for log in sf.logs],
    )


@router.patch("/{session_id}/files/{file_idx}/logs/{log_idx}/epoch")
def update_epoch(
    session_id: str,
    file_idx: int,
    log_idx: int,
    req: EpochUpdate,
):
    try:
        session_manager.set_epoch(session_id, file_idx, log_idx, req.epoch_start, req.epoch_end)
    except KeyError:
        raise HTTPException(404, "Session not found")
    except IndexError:
        raise HTTPException(404, "File or log not found")
    return {"epoch_start": req.epoch_start, "epoch_end": req.epoch_end}


@router.post("/{session_id}/traces")
def get_traces(session_id: str, req: TraceRequest):
    try:
        session = session_manager.get(session_id)
        log = session_manager.get_log(session_id, req.file_idx, req.log_idx)
        sf = session.files[req.file_idx]
        epoch_start = req.epoch_start if req.epoch_start is not None else sf.epoch_start[req.log_idx]
        epoch_end = req.epoch_end if req.epoch_end is not None else sf.epoch_end[req.log_idx]
    except KeyError:
        raise HTTPException(404, "Session not found")
    except IndexError:
        raise HTTPException(404, "File or log not found")

    data = extract_log_viewer_traces(
        log,
        epoch_start,
        epoch_end,
        req.axes,
        req.traces,
        smooth_factor=req.smooth_factor,
    )
    data["available_traces"] = list_available_traces(log.dataframe)
    # #region agent log
    import json, time
    with open("/home/valentin/Projects/PIDToolBox/.cursor/debug-93a084.log", "a") as _f:
        _f.write(json.dumps({"sessionId": "93a084", "location": "sessions.py:get_traces", "message": "trace response", "data": {"roll_keys": [t["key"] for t in data["panels"].get("roll", [])], "available": data["available_traces"], "requested": req.traces, "gyro_col_exists": "gyroADC_0_" in log.dataframe.columns}, "timestamp": int(time.time() * 1000), "hypothesisId": "H5"}) + "\n")
    # #endregion
    return data


@router.get("/{session_id}/files/{file_idx}/logs/{log_idx}/setup")
def get_setup_info(session_id: str, file_idx: int, log_idx: int):
    try:
        log = session_manager.get_log(session_id, file_idx, log_idx)
    except KeyError:
        raise HTTPException(404, "Session not found")
    except IndexError:
        raise HTTPException(404, "File or log not found")

    return {
        "name": log.name,
        "setup_info": [{"key": k, "value": v} for k, v in log.setup_info],
        "roll_pidf": log.roll_pidf,
        "pitch_pidf": log.pitch_pidf,
        "yaw_pidf": log.yaw_pidf,
        "fw_type": log.fw_type,
        "lograte_khz": log.lograte_khz,
    }
