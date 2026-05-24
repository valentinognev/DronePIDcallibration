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
    "throttle": {"col": "rcCommand_3_", "alt_cols": ["rcData_3_"], "label": "Throttle", "color": "#000000", "axis": None},
    "motor_0": {"col": "motor_0_", "label": "Motor 1", "color": "#e60000"},
    "motor_1": {"col": "motor_1_", "label": "Motor 2", "color": "#ff9900"},
    "motor_2": {"col": "motor_2_", "label": "Motor 3", "color": "#0099ff"},
    "motor_3": {"col": "motor_3_", "label": "Motor 4", "color": "#00cccc"},
    "debug": {"col": "debug_{axis}_", "label": "Debug", "color": "#ff0000"},
}


def _is_per_axis(defn: dict[str, Any]) -> bool:
    return "{axis}" in defn["col"]


def _col_name(trace_key: str, axis_idx: int | None) -> str | None:
    defn = TRACE_DEFS.get(trace_key)
    if not defn:
        return None
    if not _is_per_axis(defn):
        return defn["col"]
    if axis_idx is None:
        return None
    return defn["col"].format(axis=axis_idx)


def _resolve_col(df: pd.DataFrame, trace_key: str, axis_idx: int | None) -> str | None:
    defn = TRACE_DEFS.get(trace_key)
    if not defn:
        return None
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


def get_trace(
    df: pd.DataFrame,
    trace_key: str,
    axis_idx: int = 0,
) -> np.ndarray | None:
    col = _resolve_col(df, trace_key, axis_idx if trace_key != "throttle" else None)
    if col:
        return df[col].values.astype(float)
    return None


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
    t0 = df["time_us"].iloc[0]
    time_sec = ((df["time_us"] - t0) / US2SEC).values

    factor = int(log.lograte_khz * DOWNSAMPLE_MULTIPLIER) if downsample else 1

    panels: dict[str, Any] = {}
    for axis_idx in axes:
        axis_name = AXIS_NAMES[axis_idx]
        traces = []
        for key in trace_keys:
            if key == "throttle" or key.startswith("motor_"):
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
    for key in trace_keys:
        if key == "throttle":
            y = get_trace(df, key, None)
            if y is not None:
                tx, ty = downsample_trace(time_sec, y, factor)
                motor_traces.append(
                    {
                        "key": key,
                        "label": TRACE_DEFS[key]["label"],
                        "color": TRACE_DEFS[key]["color"],
                        "x": tx.tolist(),
                        "y": ty.tolist(),
                    }
                )
        elif key.startswith("motor_"):
            motor_idx = int(key.split("_")[1])
            y = get_trace(df, key, motor_idx)
            if y is not None:
                tx, ty = downsample_trace(time_sec, y, factor)
                motor_traces.append(
                    {
                        "key": key,
                        "label": TRACE_DEFS[key]["label"],
                        "color": TRACE_DEFS[key]["color"],
                        "x": tx.tolist(),
                        "y": ty.tolist(),
                    }
                )

    return {
        "time_range": [float(time_sec[0]), float(time_sec[-1])],
        "epoch": [epoch_start, epoch_end],
        "lograte_khz": log.lograte_khz,
        "panels": panels,
        "motor_panel": motor_traces,
        "metadata": {
            "name": log.name,
            "fw_type": log.fw_type,
            "roll_pidf": log.roll_pidf,
            "pitch_pidf": log.pitch_pidf,
            "yaw_pidf": log.yaw_pidf,
            "debug_mode": log.debug_mode,
        },
    }


def list_available_traces(df: pd.DataFrame) -> list[str]:
    available = []
    for key, defn in TRACE_DEFS.items():
        if not _is_per_axis(defn):
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
