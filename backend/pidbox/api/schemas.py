"""Pydantic request/response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    firmware: str = "betaflight"


class SessionResponse(BaseModel):
    session_id: str
    firmware: str


class FileInfo(BaseModel):
    file_id: str
    original_name: str
    log_count: int
    log_names: list[str]


class EpochUpdate(BaseModel):
    epoch_start: float
    epoch_end: float


class TraceRequest(BaseModel):
    file_idx: int = 0
    log_idx: int = 0
    axes: list[int] = Field(default=[0, 1, 2])
    traces: list[str] = Field(
        default=["gyro", "setpoint", "pterm", "iterm", "dterm", "throttle", "motor_0", "motor_1", "motor_2", "motor_3"]
    )
    smooth_factor: int = 1
    epoch_start: float | None = None
    epoch_end: float | None = None


class SpectrumRequest(BaseModel):
    session_id: str
    file_indices: list[int] = Field(default=[0])
    log_idx: int = 0
    axes: list[int] = Field(default=[0, 1, 2])
    traces: list[str] = Field(default=["gyro", "gyro_pf"])
    psd: bool = True
    sub100hz: bool = True
    epoch_start: float | None = None
    epoch_end: float | None = None


class StepResponseRequest(BaseModel):
    session_id: str
    file_indices: list[int] = Field(default=[0])
    log_idx: int = 0
    axes: list[int] = Field(default=[0, 1, 2])
    signals: list[str] = Field(default=["rate"])
    smooth_factor: int = 1
    y_correction: bool = True
    epoch_start: float | None = None
    epoch_end: float | None = None


class ThrottleSpectrumRequest(BaseModel):
    session_id: str
    file_idx: int = 0
    log_idx: int = 0
    trace: str = "gyro"
    axis: int = 0
    psd: bool = True
    epoch_start: float | None = None
    epoch_end: float | None = None


class TimeFreqRequest(BaseModel):
    session_id: str
    file_idx: int = 0
    log_idx: int = 0
    trace: str = "gyro"
    axis: int = 0
    smooth_factor: int = 1
    subsample_factor: int = 1
    epoch_start: float | None = None
    epoch_end: float | None = None


class FilterSimRequest(BaseModel):
    looprate_hz: float = 8000
    lpf_cutoffs: list[float] = Field(default=[250, 500])
    notch_configs: list[list[float]] = Field(default=[[100, 500], [200, 500], [300, 500], [500, 500]])


class StatsRequest(BaseModel):
    session_id: str
    file_idx: int = 0
    log_idx: int = 0
    axis: int = 0
    epoch_start: float | None = None
    epoch_end: float | None = None


class ChirpRequest(BaseModel):
    session_id: str
    file_idx: int = 0
    log_idx: int = 0
    axis: int = 0


class SetupInfoRequest(BaseModel):
    session_id: str
    file_idx_a: int = 0
    file_idx_b: int = 1
    log_idx_a: int = 0
    log_idx_b: int = 0
    differences_only: bool = False


class UserSettings(BaseModel):
    firmware: str = "betaflight"
    theme: str = "dark"
    log_viewer_single_panel: bool = False
    plot_r: bool = True
    plot_p: bool = True
    plot_y: bool = True
    line_smooth: int = 1
    line_width: int = 3
    y_scale: float = 500


class AnalysisResult(BaseModel):
    data: dict[str, Any]
