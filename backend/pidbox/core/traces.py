"""Trace extraction for log viewer and analysis tools."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from pidbox.config import DOWNSAMPLE_MULTIPLIER, US2SEC
from pidbox.core.parsers.base import LoadedLog
from pidbox.core.parsers.common import downsample_trace, slice_epoch
from pidbox.core.smoothing import smooth_by_factor

AXIS_NAMES = ("roll", "pitch", "yaw")
AXIS_SUFFIX = ("0", "1", "2")

TRACE_DEFS: dict[str, dict[str, Any]] = {
    "gyro": {"col": "gyroADC_{axis}_", "label": "Gyro", "color": "#ffffff"},
    "gyro_pf": {"col": "axisDpf_{axis}_", "label": "Gyro(pf)", "color": "#999999"},
    "pterm": {"col": "axisP_{axis}_", "label": "P-term", "color": "#00b300"},
    "iterm": {"col": "axisI_{axis}_", "label": "I-term", "color": "#1a66cc"},
    "dterm_pf": {"col": "axisDpf_{axis}_", "label": "D-term(pf)", "color": "#ccb31a"},
    "dterm": {"col": "axisD_{axis}_", "label": "D-term", "color": "#ff9900"},
    "fterm": {"col": "axisF_{axis}_", "label": "F-term", "color": "#ff33cc"},
    "setpoint": {"col": "setpoint_{axis}_", "label": "Set point", "color": "#ff0000"},
    "pidsum": {"col": "pidsum_{axis}_", "label": "PID sum", "color": "#9933cc"},
    "piderr": {"col": "piderr_{axis}_", "label": "PID error", "color": "#00cccc"},
    "throttle": {
        "col": "setpoint_3_",
        "alt_cols": ["rcCommand_3_", "rcData_3_"],
        "label": "Throttle",
        "color": "#ffffff",
        "axis": None,
    },
    "motor_0": {"col": "eRPM_0_", "alt_cols": ["motor_0_"], "label": "Motor 1 (RPM)", "color": "#e60000"},
    "motor_1": {"col": "eRPM_1_", "alt_cols": ["motor_1_"], "label": "Motor 2 (RPM)", "color": "#ff9900"},
    "motor_2": {"col": "eRPM_2_", "alt_cols": ["motor_2_"], "label": "Motor 3 (RPM)", "color": "#0099ff"},
    "motor_3": {"col": "eRPM_3_", "alt_cols": ["motor_3_"], "label": "Motor 4 (RPM)", "color": "#00cccc"},
    "motor_in_0": {"col": "motor_in_0_", "label": "Motor 1 in", "color": "#ff6666"},
    "motor_in_1": {"col": "motor_in_1_", "label": "Motor 2 in", "color": "#ffaa66"},
    "motor_in_2": {"col": "motor_in_2_", "label": "Motor 3 in", "color": "#66aaff"},
    "motor_in_3": {"col": "motor_in_3_", "label": "Motor 4 in", "color": "#66ffcc"},
    "debug": {"col": "debug_{axis}_", "label": "Debug", "color": "#ff0000"},
    "accel": {"col": "accel_{axis}_", "label": "Accel", "color": "#cccc00"},
    "attitude": {
        "axis_cols": ["att_roll_", "att_pitch_", "att_yaw_"],
        "label": "Attitude",
        "color": "#66ccff",
    },
    "attitude_sp": {
        "axis_cols": ["att_sp_roll_", "att_sp_pitch_", "att_sp_yaw_"],
        "label": "Att setpoint",
        "color": "#ff6666",
    },
    "velocity": {"col": "vel_{axis}_", "label": "Velocity", "color": "#00cccc"},
    "velocity_sp": {"col": "vel_sp_{axis}_", "label": "Vel setpoint", "color": "#cc6600"},
}


def _is_per_axis(defn: dict[str, Any]) -> bool:
    return "{axis}" in defn.get("col", "")


def _uses_axis_cols(defn: dict[str, Any]) -> bool:
    return "axis_cols" in defn


def _col_name(trace_key: str, axis_idx: int | None) -> str | None:
    defn = TRACE_DEFS.get(trace_key)
    if not defn:
        return None
    if _uses_axis_cols(defn):
        if axis_idx is None:
            return None
        return defn["axis_cols"][axis_idx]
    if not _is_per_axis(defn):
        return defn["col"]
    if axis_idx is None:
        return None
    return defn["col"].format(axis=axis_idx)


def _resolve_col(df: pd.DataFrame, trace_key: str, axis_idx: int | None) -> str | None:
    defn = TRACE_DEFS.get(trace_key)
    if not defn:
        return None
    if _uses_axis_cols(defn):
        if axis_idx is None:
            return None
        col = defn["axis_cols"][axis_idx]
        return col if col in df.columns else None
    if not _is_per_axis(defn):
        candidates = [defn["col"]] + defn.get("alt_cols", [])
        for c in candidates:
            if c in df.columns:
                return c
        return None
    if axis_idx is None:
        return None
    col = defn["col"].format(axis=axis_idx)
    return col if col in df.columns else None


def _scale_trace_values(trace_key: str, col: str, y: np.ndarray) -> np.ndarray:
    """Convert raw blackbox columns to log-viewer units (PIDscope conventions)."""
    if trace_key == "throttle":
        if col == "setpoint_3_":
            return y / 10.0
        if col in ("rcCommand_3_", "rcData_3_"):
            return (y - 1000.0) / 10.0
    return y


def _motor_trace_index(trace_key: str) -> int | None:
    if trace_key.startswith("motor_in_"):
        suffix = trace_key[len("motor_in_") :]
        return int(suffix) if suffix.isdigit() else None
    if trace_key.startswith("motor_"):
        suffix = trace_key[len("motor_") :]
        return int(suffix) if suffix.isdigit() else None
    return None


def _motor_trace_yaxis(trace_key: str, col: str) -> str:
    if trace_key.startswith("motor_in_"):
        return "y"
    if trace_key.startswith("motor_") and col.startswith("eRPM_"):
        return "y2"
    return "y"


def get_trace(
    df: pd.DataFrame,
    trace_key: str,
    axis_idx: int = 0,
) -> np.ndarray | None:
    col = _resolve_col(df, trace_key, axis_idx if trace_key != "throttle" else None)
    if col is None:
        return None
    y = df[col].values.astype(float)
    return _scale_trace_values(trace_key, col, y)


def _full_time_range(log: LoadedLog) -> list[float]:
    t0_us = log.dataframe["time_us"].iloc[0]
    full_t_sec = (log.dataframe["time_us"] - t0_us) / US2SEC
    return [float(full_t_sec.iloc[0]), float(full_t_sec.iloc[-1])]


def _trace_metadata(log: LoadedLog) -> dict[str, Any]:
    return {
        "name": log.name,
        "fw_type": log.fw_type,
        "roll_pidf": log.roll_pidf,
        "pitch_pidf": log.pitch_pidf,
        "yaw_pidf": log.yaw_pidf,
        "debug_mode": log.debug_mode,
    }


def _empty_epoch_trace_response(
    log: LoadedLog,
    epoch_start: float,
    epoch_end: float,
    axes: list[int],
) -> dict[str, Any]:
    panels = {AXIS_NAMES[axis_idx]: [] for axis_idx in axes}
    return {
        "time_range": [epoch_start, epoch_end],
        "full_time_range": _full_time_range(log),
        "epoch": [epoch_start, epoch_end],
        "lograte_khz": log.lograte_khz,
        "panels": panels,
        "motor_panel": [],
        "motor_panel_units": {"throttle": "percent", "motors": "percent"},
        "metadata": _trace_metadata(log),
    }


def extract_log_viewer_traces(
    log: LoadedLog,
    epoch_start: float,
    epoch_end: float,
    axes: list[int],
    trace_keys: list[str],
    smooth_factor: int = 1,
    downsample: bool = True,
) -> dict[str, Any]:
    """Extract time-series traces for log viewer."""
    df = slice_epoch(log.dataframe, epoch_start, epoch_end)
    if df.empty:
        return _empty_epoch_trace_response(log, epoch_start, epoch_end, axes)
    t0 = df["time_us"].iloc[0]
    time_sec = ((df["time_us"] - t0) / US2SEC).values

    factor = int(log.lograte_khz * DOWNSAMPLE_MULTIPLIER) if downsample else 1

    panels: dict[str, Any] = {}
    for axis_idx in axes:
        axis_name = AXIS_NAMES[axis_idx]
        traces = []
        for key in trace_keys:
            if key == "throttle" or _motor_trace_index(key) is not None:
                continue
            y = get_trace(df, key, axis_idx)
            if y is None:
                continue
            if smooth_factor > 1:
                y = smooth_by_factor(y, smooth_factor)
            tx, ty = downsample_trace(time_sec, y, factor)
            defn = TRACE_DEFS[key]
            traces.append(
                {
                    "key": key,
                    "label": defn["label"],
                    "color": defn["color"],
                    "x": tx.tolist(),
                    "y": ty.tolist(),
                }
            )
        panels[axis_name] = traces

    # Throttle/motor panel
    motor_traces = []
    motors_use_rpm = False
    for key in trace_keys:
        if key == "throttle":
            col = _resolve_col(df, key, None)
            y = get_trace(df, key, None)
            if y is not None and col is not None:
                if smooth_factor > 1:
                    y = smooth_by_factor(y, smooth_factor)
                tx, ty = downsample_trace(time_sec, y, factor)
                motor_traces.append(
                    {
                        "key": key,
                        "label": TRACE_DEFS[key]["label"],
                        "color": TRACE_DEFS[key]["color"],
                        "x": tx.tolist(),
                        "y": ty.tolist(),
                        "yaxis": "y",
                    }
                )
        elif (motor_idx := _motor_trace_index(key)) is not None:
            col = _resolve_col(df, key, motor_idx)
            y = get_trace(df, key, motor_idx)
            if y is not None and col is not None:
                if smooth_factor > 1:
                    y = smooth_by_factor(y, smooth_factor)
                tx, ty = downsample_trace(time_sec, y, factor)
                yaxis = _motor_trace_yaxis(key, col)
                motors_use_rpm = motors_use_rpm or yaxis == "y2"
                motor_traces.append(
                    {
                        "key": key,
                        "label": TRACE_DEFS[key]["label"].replace(" (RPM)", "") if col.startswith("motor_") else TRACE_DEFS[key]["label"],
                        "color": TRACE_DEFS[key]["color"],
                        "x": tx.tolist(),
                        "y": ty.tolist(),
                        "yaxis": yaxis,
                    }
                )

    return {
        "time_range": [float(time_sec[0]), float(time_sec[-1])],
        "full_time_range": _full_time_range(log),
        "epoch": [epoch_start, epoch_end],
        "lograte_khz": log.lograte_khz,
        "panels": panels,
        "motor_panel": motor_traces,
        "motor_panel_units": {
            "throttle": "percent",
            "motors": "rpm" if motors_use_rpm else "percent",
        },
        "metadata": _trace_metadata(log),
    }


def list_available_traces(df: pd.DataFrame) -> list[str]:
    available = []
    for key, defn in TRACE_DEFS.items():
        if _uses_axis_cols(defn):
            if any(col in df.columns for col in defn["axis_cols"]) and key not in available:
                available.append(key)
        elif not _is_per_axis(defn):
            candidates = [defn["col"]] + defn.get("alt_cols", [])
            if any(c in df.columns for c in candidates):
                available.append(key)
        else:
            for ax in range(3):
                col = defn["col"].format(axis=ax)
                if col in df.columns and key not in available:
                    available.append(key)
                    break
    return available
