"""Build sysid flight structures from normalized LoadedLog dataframes."""

from __future__ import annotations

import numpy as np

from pidbox.config import US2SEC
from pidbox.core.parsers.base import LoadedLog
from pidbox.core.sysid.rotor_model import frd_to_flu, rotor_geometry_from_ca_rotor_params
from pidbox.core.traces import get_trace

DEG2RAD = np.pi / 180.0

# Canonical internal series names used by dynamics / excitation / preprocess.
MOTOR_KEYS = [f"motor_{i}" for i in range(4)]
ACCEL_KEYS = [f"accel_{i}" for i in range(3)]
GYRO_KEYS = [f"gyro_{i}" for i in range(3)]


def _setup_map(setup_info: list[tuple[str, str]]) -> dict[str, str]:
    return {k: v for k, v in setup_info}


def _time_seconds(df) -> np.ndarray:
    t0 = float(df["time_us"].iloc[0])
    return (df["time_us"].values.astype(float) - t0) / US2SEC


def _series(timestamps: np.ndarray, values: np.ndarray) -> dict[str, np.ndarray]:
    return {"timestamps": timestamps, "values": values}


def _resolve_motor_columns(df) -> tuple[list[str], str]:
    """Return motor column names (0..1 normalized) and a source label."""
    in_cols = [f"motor_in_{i}_" for i in range(4)]
    if all(c in df.columns for c in in_cols):
        return in_cols, "motor_in"

    pwm_cols = [f"motor_{i}_" for i in range(4)]
    if all(c in df.columns for c in pwm_cols):
        return pwm_cols, "motor_pwm"

    rpm_cols = [f"eRPM_{i}_" for i in range(4)]
    if all(c in df.columns for c in rpm_cols):
        return rpm_cols, "motor_rpm"

    present_in = [c for c in in_cols if c in df.columns]
    present_pwm = [c for c in pwm_cols if c in df.columns]
    if len(present_in) >= 4:
        return in_cols, "motor_in"
    if len(present_pwm) >= 4:
        return pwm_cols, "motor_pwm"
    raise ValueError(
        "Motor commands not found: need motor_in_0..3, motor_0..3, or eRPM_0..3 columns"
    )


def _normalize_motor_values(values: np.ndarray, source: str) -> np.ndarray:
    if source == "motor_in":
        return values / 100.0
    if source == "motor_pwm":
        return values / 100.0
    if source == "motor_rpm":
        vmax = float(np.nanmax(np.abs(values)))
        if vmax <= 0:
            return values
        return values / vmax
    return values


def frame_convention(log: LoadedLog) -> str:
    """PX4 vehicle acceleration / angular velocity are logged in FRD."""
    fw = (log.fw_type or log.metadata.get("firmware", "")).upper()
    if fw == "PX4" or log.metadata.get("accel_source") == "vehicle_acceleration":
        return "frd"
    return "flu"


def capabilities(log: LoadedLog) -> dict:
    df = log.dataframe
    missing: list[str] = []
    has_accel = all(f"accel_{i}_" in df.columns for i in range(3))
    has_gyro = all(f"gyroADC_{i}_" in df.columns for i in range(3))
    motor_source = None
    try:
        _, motor_source = _resolve_motor_columns(df)
    except ValueError:
        missing.append("motor commands (motor_in_*, motor_*, or eRPM_*)")

    if not has_accel:
        missing.append("accelerometer (accel_0..2)")
    if not has_gyro:
        missing.append("gyro (gyroADC_0..2)")

    return {
        "ready": len(missing) == 0,
        "missing": missing,
        "motor_source": motor_source,
        "frame_convention": frame_convention(log),
        "accel_unit": log.metadata.get("accel_unit", "unknown"),
    }


def flight_from_log(log: LoadedLog) -> dict:
    """Convert a parsed LoadedLog into the sysid flight dict."""
    caps = capabilities(log)
    if not caps["ready"]:
        raise ValueError(
            f"Log '{log.name}' missing sysid signals: {', '.join(caps['missing'])}"
        )

    df = log.dataframe
    timestamps = _time_seconds(df)
    motor_cols, motor_source = _resolve_motor_columns(df)
    data: dict[str, dict[str, np.ndarray]] = {}

    for i, col in enumerate(motor_cols):
        raw = get_trace(df, f"motor_in_{i}", i) if motor_source == "motor_in" else df[col].values.astype(float)
        if raw is None:
            raw = df[col].values.astype(float)
        values = _normalize_motor_values(raw, motor_source)
        data[MOTOR_KEYS[i]] = _series(timestamps, values)

    for i in range(3):
        accel_col = f"accel_{i}_"
        gyro_col = f"gyroADC_{i}_"
        data[ACCEL_KEYS[i]] = _series(timestamps, df[accel_col].values.astype(float))
        gyro_deg = df[gyro_col].values.astype(float)
        data[GYRO_KEYS[i]] = _series(timestamps, gyro_deg * DEG2RAD)

    return {
        "name": log.name,
        "convention": caps["frame_convention"],
        "motor_source": motor_source,
        "data": data,
        "timestamps": timestamps,
    }


def defaults_from_log(log: LoadedLog) -> dict:
    """Best-effort model defaults from parsed setup info (PX4 CA_ROTOR*, mass)."""
    params = _setup_map(log.setup_info)
    result: dict = {
        "mass": None,
        "rotor_positions": None,
        "rotor_thrust_directions": None,
        "rotor_torque_directions": None,
        "frame_convention": frame_convention(log),
    }

    ca_keys = [k for k in params if k.startswith("CA_ROTOR")]
    if ca_keys:
        geom = rotor_geometry_from_ca_rotor_params(params)
        result["rotor_positions"] = geom["rotor_positions"].tolist()
        result["rotor_thrust_directions"] = geom["rotor_thrust_directions"].tolist()
        result["rotor_torque_directions"] = geom["rotor_torque_directions"].tolist()

    for mass_key in ("WEIGHT_BASE", "MPC_MASS", "mass"):
        if mass_key in params:
            try:
                mass = float(params[mass_key])
                if mass_key == "WEIGHT_BASE" and mass > 50:
                    mass /= 1000.0
                result["mass"] = mass
                break
            except ValueError:
                continue

    return result
