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
    parse_warnings: list[str] = Field(default_factory=list)


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


class OverlayCapabilitiesRequest(BaseModel):
    session_id: str
    file_indices: list[int] = Field(default=[0])
    log_idx: int = 0
    rpm_estimate: bool = False
    rpm_multiplier: float = Field(default=2.1, gt=0)
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
    smooth_factor: int = Field(default=1, ge=0, le=5)
    rpm_notch_mode: str = "off"
    dyn_notch_mode: str = "off"
    rpm_motors: list[int] = Field(default=[0, 1, 2, 3])
    rpm_estimate: bool = False
    rpm_multiplier: float = Field(default=2.1, gt=0)
    include_motor_noise: bool = False
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


class SysIdModel(BaseModel):
    mass: float = Field(gt=0)
    gravity: float = 9.81
    inertia_ratio: float = Field(default=1.832, gt=0)
    rotor_positions: list[list[float]] = Field(
        description="4 rotors × [x, y, z] in FLU frame (m)",
        min_length=4,
        max_length=4,
    )
    rotor_thrust_directions: list[list[float]] = Field(min_length=4, max_length=4)
    rotor_torque_directions: list[list[float]] = Field(min_length=4, max_length=4)


class SysIdTimeframe(BaseModel):
    file_idx: int = Field(ge=0)
    start: float = Field(ge=0)
    end: float = Field(gt=0)


class SysIdDefaultsRequest(BaseModel):
    session_id: str
    file_idx: int = 0
    log_idx: int = 0


class SysIdCapabilitiesRequest(BaseModel):
    session_id: str
    file_idx: int = 0
    log_idx: int = 0


class SysIdPreviewRequest(BaseModel):
    session_id: str
    file_indices: list[int] = Field(default=[0])
    log_idx: int = 0
    model: SysIdModel


class SysIdRunRequest(BaseModel):
    session_id: str
    file_indices: list[int] = Field(default=[0])
    log_idx: int = 0
    model: SysIdModel
    exponents: list[int] = Field(default=[0, 1, 2])
    separate_motors: bool = False
    timeframes_thrust: list[SysIdTimeframe]
    timeframes_inertia_rp: list[SysIdTimeframe]
    timeframes_inertia_yaw: list[SysIdTimeframe]
    t_m_steps: int = Field(default=100, ge=10, le=500)
    t_m_min: float = Field(default=0.001, gt=0)
    t_m_max: float = Field(default=0.2, gt=0)
