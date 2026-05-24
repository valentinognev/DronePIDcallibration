"""Shared log parsing utilities."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from pidbox.config import MAX_MOTOR_OUTPUT, US2SEC


def _matlabify_column(name: str) -> str:
    """Convert blackbox_decode CSV headers to names matching Octave readtable."""
    name = name.strip()
    if name == "time (us)":
        return "time_us"
    name = re.sub(r"\[(\d+)\]", r"_\1_", name)
    name = re.sub(r" \(([^)]+)\)", lambda m: "_" + m.group(1).replace(" ", "_"), name)
    if not name.endswith("_"):
        name += "_"
    return name


def normalize_blackbox_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [_matlabify_column(c) for c in df.columns]
    return df


def read_csv_log(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    return normalize_blackbox_columns(df)


def extract_setup_info_from_header(
    bbl_path: Path, log_index: int = 0
) -> list[tuple[str, str]]:
    """Extract setup info key:value pairs from BBL/BFL header or CSV companion."""
    path = Path(bbl_path)
    if path.suffix.lower() == ".csv":
        # Try companion header file or parse from first lines if embedded
        header_path = path.with_suffix(".header.txt")
        if header_path.exists():
            lines = header_path.read_text(errors="replace").splitlines()
        else:
            return _setup_from_csv_columns(path)
        return _parse_setup_lines(lines)

    text = path.read_text(errors="replace").splitlines()
    start_markers = ("Firmware version", "Firmware revision")
    end_markers = (
        "throttle_boost_cutoff",
        "debug_mode",
        "motor_pwm_rate",
        "use_unsynced_pwm",
        "gyro_32khz_hardware_lpf",
        "gyro_hardware_lpf",
        "yaw_deadband",
        "deadband",
        "pidsum_limit_yaw",
        "pidsum_limit",
        "energyCumulative (mAh)",
        "looptime",
    )

    start_points = [
        i
        for i, line in enumerate(text)
        if any(m in line for m in start_markers)
    ]
    if not start_points:
        return []

    end_points = []
    for marker in end_markers:
        pts = [i for i, line in enumerate(text) if marker in line]
        if pts:
            end_points = pts
            break

    if not end_points or log_index >= len(start_points):
        return []

    section = text[start_points[log_index] : end_points[0] + 1]
    return _parse_setup_lines(section)


def _parse_setup_lines(lines: list[str]) -> list[tuple[str, str]]:
    setup: list[tuple[str, str]] = []
    for line in lines:
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        if key.startswith("H "):
            key = key[2:]
        setup.append((key, val.strip()))
    return setup


def _setup_from_csv_columns(path: Path) -> list[tuple[str, str]]:
    """Minimal setup info when only CSV is available."""
    df = pd.read_csv(path, nrows=1)
    return [("source", path.name), ("columns", str(len(df.columns)))]


def parse_bf_version(setup_info: list[tuple[str, str]]) -> tuple[str, int, int]:
    fw_type = "Unknown"
    fw_major = 0
    fw_minor = 0

    ver_str = ""
    for key in ("Firmware version", "Firmware revision"):
        for k, v in setup_info:
            if k == key:
                ver_str = v
                break
        if ver_str:
            break

    if not ver_str:
        return fw_type, fw_major, fw_minor

    parts = ver_str.split("/")
    fw_type = parts[0].strip()

    tokens = re.findall(r"(\d+)\.(\d+)\.(\d+)", ver_str)
    for maj_s, mnr_s, _ in tokens:
        maj, mnr = int(maj_s), int(mnr_s)
        if maj >= 2:
            return fw_type, maj, mnr
    if tokens:
        return fw_type, int(tokens[0][0]), int(tokens[0][1])
    return fw_type, fw_major, fw_minor


def parse_pidf(setup_info: list[tuple[str, str]]) -> tuple[str, str, str]:
    def _get(key: str) -> str:
        for k, v in setup_info:
            if k == key:
                return v
        return ""

    r = _get("rollPID")
    p = _get("pitchPID")
    y = _get("yawPID")
    dm = _get("d_max") or _get("d_min") or " , , "
    ff = _get("feedforward_weight") or _get("ff_weight") or " , , "

    a = [i for i, c in enumerate(dm) if c == ","]
    b = [i for i, c in enumerate(ff) if c == ","]

    def _pidf(pid: str, dm_part: str, ff_part: str) -> str:
        return f"{pid},{dm_part},{ff_part}"

    if len(a) >= 2 and len(b) >= 2:
        roll = _pidf(r, dm[: a[0]], ff[: b[0]])
        pitch = _pidf(p, dm[a[0] + 1 : a[1]], ff[b[0] + 1 : b[1]])
        yaw = _pidf(y, dm[a[1] + 1 :], ff[b[1] + 1 :])
        return roll, pitch, yaw
    return f"{r},,", f"{p},,", f"{y},,"


def compute_derived_columns(df: pd.DataFrame, firmware: str = "betaflight") -> pd.DataFrame:
    """Add derived columns matching PSload.m post-processing."""
    df = df.copy()

    if firmware == "inav":
        for axis in range(3):
            col = f"axisRate_{axis}_"
            if col in df.columns:
                df[f"setpoint_{axis}_"] = df[col]
        if "rcData_3_" in df.columns:
            df["setpoint_3_"] = df["rcData_3_"] - 1000

    for k in range(4):
        if firmware != "ardupilot":
            for prefix in ("debug", "axisF"):
                col = f"{prefix}_{k}_"
                if col not in df.columns:
                    n = len(df)
                    df[col] = np.zeros(n)

            mcol = f"motor_{k}_"
            if mcol in df.columns:
                if firmware == "inav":
                    df[mcol] = (df[mcol] - 1000) / 10
                else:
                    df[mcol] = (df[mcol] / MAX_MOTOR_OUTPUT) * 100

            mcol4 = f"motor_{k + 4}_"
            if mcol4 in df.columns:
                if firmware == "inav":
                    df[mcol4] = (df[mcol4] - 1000) / 10
                else:
                    df[mcol4] = (df[mcol4] / MAX_MOTOR_OUTPUT) * 100

        if k < 3:
            gyro = f"gyroADC_{k}_"
            sp = f"setpoint_{k}_"
            if gyro in df.columns and sp in df.columns:
                df[f"piderr_{k}_"] = df[gyro] - df[sp]

            if k < 2 and gyro in df.columns:
                dpf = f"axisDpf_{k}_"
                dterm = f"axisD_{k}_"
                if dterm in df.columns:
                    d1 = pd.Series(-np.diff(df[gyro].values, prepend=df[gyro].iloc[0]))
                    d1_smooth = d1.rolling(100, min_periods=1, center=True).mean()
                    d2_smooth = df[dterm].rolling(100, min_periods=1, center=True).mean()
                    ratio = d2_smooth / d1_smooth.replace(0, np.nan)
                    sclr = np.nanmedian(ratio[(ratio > 0) & np.isfinite(ratio)])
                    if np.isfinite(sclr):
                        df[dpf] = d1 * sclr
                    else:
                        df[dpf] = d1

            pcol, icol, dcol, fcol = (
                f"axisP_{k}_",
                f"axisI_{k}_",
                f"axisD_{k}_",
                f"axisF_{k}_",
            )
            parts = [c for c in (pcol, icol, dcol, fcol) if c in df.columns]
            if len(parts) >= 3:
                df[f"pidsum_{k}_"] = sum(df[c] for c in parts)

    return df


def slice_epoch(df: pd.DataFrame, epoch_start: float, epoch_end: float) -> pd.DataFrame:
    t0 = df["time_us"].iloc[0]
    t_sec = (df["time_us"] - t0) / US2SEC
    mask = (t_sec >= epoch_start) & (t_sec <= epoch_end)
    return df.loc[mask].copy()


def downsample_trace(x: np.ndarray, y: np.ndarray, factor: int) -> tuple[np.ndarray, np.ndarray]:
    if factor <= 1:
        return x, y
    idx = np.arange(0, len(x), factor)
    return x[idx], y[idx]
