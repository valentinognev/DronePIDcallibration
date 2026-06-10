"""System identification API (format-agnostic, uses parsed session logs)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from pidbox.api.schemas import (
    SysIdCapabilitiesRequest,
    SysIdDefaultsRequest,
    SysIdPreviewRequest,
    SysIdRunRequest,
)
from pidbox.core.sysid.log_adapter import capabilities, defaults_from_log
from pidbox.core.sysid.pipeline import preview_excitation, run_sysid
from pidbox.session import session_manager

router = APIRouter()


def _logs_for_indices(
    session_id: str,
    file_indices: list[int],
    log_idx: int = 0,
) -> list:
    if not file_indices:
        raise HTTPException(status_code=400, detail="file_indices must not be empty")
    logs = []
    for fi in file_indices:
        try:
            logs.append(session_manager.get_log(session_id, fi, log_idx))
        except (KeyError, IndexError) as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    return logs


@router.post("/capabilities")
def sysid_capabilities(req: SysIdCapabilitiesRequest) -> dict:
    try:
        log = session_manager.get_log(req.session_id, req.file_idx, req.log_idx)
        return capabilities(log)
    except (KeyError, IndexError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/defaults")
def sysid_defaults(req: SysIdDefaultsRequest) -> dict:
    try:
        log = session_manager.get_log(req.session_id, req.file_idx, req.log_idx)
        return defaults_from_log(log)
    except (KeyError, IndexError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/preview")
def sysid_preview(req: SysIdPreviewRequest) -> dict:
    logs = _logs_for_indices(req.session_id, req.file_indices, req.log_idx)
    try:
        return preview_excitation(logs, req.model.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/run")
def sysid_run(req: SysIdRunRequest) -> dict:
    logs = _logs_for_indices(req.session_id, req.file_indices, req.log_idx)
    try:
        return run_sysid(
            logs,
            req.file_indices,
            req.model.model_dump(),
            exponents=req.exponents,
            separate_motors=req.separate_motors,
            timeframes_thrust=[tf.model_dump() for tf in req.timeframes_thrust],
            timeframes_inertia_rp=[tf.model_dump() for tf in req.timeframes_inertia_rp],
            timeframes_inertia_yaw=[tf.model_dump() for tf in req.timeframes_inertia_yaw],
            t_m_steps=req.t_m_steps,
            t_m_min=req.t_m_min,
            t_m_max=req.t_m_max,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
