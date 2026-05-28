"""PX4 ULOG (.ulg) parser using pyulog."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from pidbox.config import US2SEC, default_epoch_bounds
from pidbox.core.debug_modes import debug_mode_indices
from pidbox.core.parsers.base import LoadedLog, LogParser, register_parser
from pidbox.core.parsers.common import compute_derived_columns

logger = logging.getLogger(__name__)

RAD2DEG = 180.0 / np.pi


def _safe_dataset(ulog, name: str):
    try:
        return ulog.get_dataset(name)
    except (KeyError, IndexError, ValueError, AttributeError):
        return None


def _timestamp_us(dataset) -> np.ndarray:
    return np.asarray(dataset.data["timestamp"], dtype=np.float64)


def _interp_to(time_us: np.ndarray, src_us: np.ndarray, values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    mask = np.isfinite(values)
    if mask.sum() == 0:
        return np.zeros_like(time_us, dtype=float)
    return np.interp(time_us, src_us[mask], values[mask])


def _unpack_sensor_fifo(
    dataset,
    axis_fields: tuple[str, str, str] = ("x", "y", "z"),
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Unpack PX4 sensor_*_fifo topic into flat high-rate arrays."""
    ts_us = _timestamp_us(dataset)
    n_packets = len(ts_us)
    if n_packets == 0:
        return np.array([]), np.array([]), np.array([]), np.array([])

    samples_per = int(np.median(dataset.data["samples"]))
    scale = np.asarray(dataset.data["scale"], dtype=float)

    axes = []
    for axis_idx, axis in enumerate(axis_fields):
        block = np.zeros((n_packets, samples_per), dtype=float)
        axis_scale = scale[axis_idx] if len(scale) > axis_idx else scale[0]
        for s in range(samples_per):
            field = f"{axis}[{s}]"
            block[:, s] = np.asarray(dataset.data[field], dtype=float) * axis_scale
        axes.append(block.flatten())

    flat_len = n_packets * samples_per
    time_us = np.linspace(ts_us[0], ts_us[-1], flat_len)
    return time_us, axes[0], axes[1], axes[2]


def _gyro_from_sensor_combined(dataset) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    ts_us = _timestamp_us(dataset)
    gx = np.rad2deg(np.asarray(dataset.data["gyro_rad[0]"], dtype=float))
    gy = np.rad2deg(np.asarray(dataset.data["gyro_rad[1]"], dtype=float))
    gz = np.rad2deg(np.asarray(dataset.data["gyro_rad[2]"], dtype=float))
    return ts_us, gx, gy, gz


def _build_setup_info(ulog, path: Path) -> list[tuple[str, str]]:
    setup: list[tuple[str, str]] = [
        ("Firmware revision", "PX4"),
        ("source", path.name),
    ]
    params = getattr(ulog, "initial_parameters", None) or {}
    for key in sorted(params.keys())[:200]:
        setup.append((str(key), str(params[key])))
    return setup


def _read_px4_ulg(path: Path) -> tuple[pd.DataFrame, list[tuple[str, str]], dict]:
    try:
        from pyulog import ULog
        from pyulog.px4 import PX4ULog
    except ImportError as e:
        raise ImportError("pyulog required for PX4 ULOG files") from e

    ulog = ULog(str(path))
    try:
        px4 = PX4ULog(ulog)
        px4.add_roll_pitch_yaw()
        ulog = px4._ulog
    except Exception:
        logger.debug("PX4ULog attitude enrichment skipped for %s", path.name)

    metadata: dict = {"gyro_source": "sensor_combined", "has_gyro_fifo": False, "has_accel_fifo": False}

    gyro_fifo = _safe_dataset(ulog, "sensor_gyro_fifo")
    if gyro_fifo is not None:
        time_us, gx, gy, gz = _unpack_sensor_fifo(gyro_fifo)
        gx = np.rad2deg(gx)
        gy = np.rad2deg(gy)
        gz = np.rad2deg(gz)
        if len(time_us) > 0:
            metadata["gyro_source"] = "sensor_gyro_fifo"
            metadata["has_gyro_fifo"] = True
        else:
            gyro_fifo = None

    if gyro_fifo is None:
        combined = _safe_dataset(ulog, "sensor_combined")
        if combined is None:
            ang_vel = _safe_dataset(ulog, "vehicle_angular_velocity")
            if ang_vel is None:
                raise ValueError("No gyro data found in PX4 ULOG (need sensor_gyro_fifo, sensor_combined, or vehicle_angular_velocity)")
            time_us = _timestamp_us(ang_vel)
            gx = np.rad2deg(np.asarray(ang_vel.data["xyz[0]"], dtype=float))
            gy = np.rad2deg(np.asarray(ang_vel.data["xyz[1]"], dtype=float))
            gz = np.rad2deg(np.asarray(ang_vel.data["xyz[2]"], dtype=float))
            metadata["gyro_source"] = "vehicle_angular_velocity"
        else:
            time_us, gx, gy, gz = _gyro_from_sensor_combined(combined)
            metadata["gyro_source"] = "sensor_combined"

    accel_fifo = _safe_dataset(ulog, "sensor_accel_fifo")
    if accel_fifo is not None:
        accel_ts, ax, ay, az = _unpack_sensor_fifo(accel_fifo)
        if len(accel_ts) > 0:
            metadata["has_accel_fifo"] = True
            metadata["accel_time_us"] = accel_ts
            metadata["accel_x"] = ax
            metadata["accel_y"] = ay
            metadata["accel_z"] = az

    rates_sp = _safe_dataset(ulog, "vehicle_rates_setpoint")
    if rates_sp is not None:
        sp_us = _timestamp_us(rates_sp)
        sp0 = np.rad2deg(np.asarray(rates_sp.data["roll"], dtype=float))
        sp1 = np.rad2deg(np.asarray(rates_sp.data["pitch"], dtype=float))
        sp2 = np.rad2deg(np.asarray(rates_sp.data["yaw"], dtype=float))
    else:
        sp_us = np.array([time_us[0], time_us[-1]])
        sp0 = sp1 = sp2 = np.zeros(2)

    thrust = _safe_dataset(ulog, "vehicle_thrust_setpoint")
    if thrust is not None:
        thr_us = _timestamp_us(thrust)
        thr = np.clip(-np.asarray(thrust.data["xyz[2]"], dtype=float) * 1000.0, 0.0, 1000.0)
    else:
        thr_us = np.array([time_us[0], time_us[-1]])
        thr = np.zeros(2)

    att_sp = _safe_dataset(ulog, "vehicle_attitude_setpoint")
    att = _safe_dataset(ulog, "vehicle_attitude")

    df_dict: dict[str, np.ndarray] = {
        "time_us": time_us,
        "gyroADC_0_": gx,
        "gyroADC_1_": gy,
        "gyroADC_2_": gz,
        "setpoint_0_": _interp_to(time_us, sp_us, sp0),
        "setpoint_1_": _interp_to(time_us, sp_us, sp1),
        "setpoint_2_": _interp_to(time_us, sp_us, sp2),
        "setpoint_3_": _interp_to(time_us, thr_us, thr),
    }

    if att_sp is not None:
        att_sp_us = _timestamp_us(att_sp)
        df_dict["att_sp_roll_"] = _interp_to(
            time_us, att_sp_us, np.rad2deg(np.asarray(att_sp.data["roll_body"], dtype=float))
        )
        df_dict["att_sp_pitch_"] = _interp_to(
            time_us, att_sp_us, np.rad2deg(np.asarray(att_sp.data["pitch_body"], dtype=float))
        )
        df_dict["att_sp_yaw_"] = _interp_to(
            time_us, att_sp_us, np.rad2deg(np.asarray(att_sp.data["yaw_body"], dtype=float))
        )

    if att is not None and "roll" in att.data:
        att_us = _timestamp_us(att)
        df_dict["att_roll_"] = _interp_to(
            time_us, att_us, np.rad2deg(np.asarray(att.data["roll"], dtype=float))
        )
        df_dict["att_pitch_"] = _interp_to(
            time_us, att_us, np.rad2deg(np.asarray(att.data["pitch"], dtype=float))
        )
        df_dict["att_yaw_"] = _interp_to(
            time_us, att_us, np.rad2deg(np.asarray(att.data["yaw"], dtype=float))
        )

    df = pd.DataFrame(df_dict)
    setup_info = _build_setup_info(ulog, path)
    return df, setup_info, metadata


@register_parser
class Px4Parser(LogParser):
    firmware_key = "px4"
    display_name = "PX4"
    extensions = (".ulg",)

    def can_parse(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def parse(
        self, path: Path, log_indices: list[int] | None = None
    ) -> list[LoadedLog]:
        df, setup_info, metadata = _read_px4_ulg(path)
        df = compute_derived_columns(df, firmware="px4")

        diffs = np.diff(df["time_us"].values)
        diffs = diffs[diffs > 0]
        lograte = round((1000 / np.median(diffs)) * 10) / 10 if len(diffs) else 1.0

        dbg_idx = debug_mode_indices("PX4", 0, 0)
        duration_sec = (df["time_us"].iloc[-1] - df["time_us"].iloc[0]) / US2SEC
        epoch_start, epoch_end = default_epoch_bounds(duration_sec)

        return [
            LoadedLog(
                name=path.name,
                source_path=str(path),
                dataframe=df,
                setup_info=setup_info,
                lograte_khz=lograte,
                fw_type="PX4",
                fw_major=0,
                fw_minor=0,
                debug_mode=0,
                debug_indices=dbg_idx,
                gyro_debug_axis=0,
                roll_pidf="",
                pitch_pidf="",
                yaw_pidf="",
                default_epoch_start=epoch_start,
                default_epoch_end=epoch_end,
                metadata=metadata,
            )
        ]
