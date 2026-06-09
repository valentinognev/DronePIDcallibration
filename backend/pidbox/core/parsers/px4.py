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
MAX_MOTORS = 4
# PWM channels stuck at disarmed/min throttle have ~0 std; flying motors vary.
MOTOR_OUTPUT_MIN_STD = 1.0
# Normalized control[] in actuator_motors (0–1); idle channels are constant.
MOTOR_CONTROL_MIN_STD = 0.01
# esc_status esc[N].esc_rpm — idle ESC slots stay at 0 RPM.
ESC_RPM_MIN_STD = 10.0
MAX_ESC_SLOTS = 8


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


def _record_missing(metadata: dict, message: str) -> None:
    """Append a user-facing note when a signal has no usable log source."""
    missing: list[str] = metadata.setdefault("missing_data", [])
    if message not in missing:
        missing.append(message)


def _quat_fields_to_euler_deg(data: dict, prefix: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert PX4 quaternion fields (w,x,y,z) to roll/pitch/yaw in degrees."""
    q0 = np.asarray(data[f"{prefix}[0]"], dtype=float)
    q1 = np.asarray(data[f"{prefix}[1]"], dtype=float)
    q2 = np.asarray(data[f"{prefix}[2]"], dtype=float)
    q3 = np.asarray(data[f"{prefix}[3]"], dtype=float)

    sinr_cosp = 2.0 * (q0 * q1 + q2 * q3)
    cosr_cosp = 1.0 - 2.0 * (q1 * q1 + q2 * q2)
    roll = np.arctan2(sinr_cosp, cosr_cosp)

    sinp = 2.0 * (q0 * q2 - q3 * q1)
    pitch = np.where(np.abs(sinp) >= 1.0, np.copysign(np.pi / 2.0, sinp), np.arcsin(sinp))

    siny_cosp = 2.0 * (q0 * q3 + q1 * q2)
    cosy_cosp = 1.0 - 2.0 * (q2 * q2 + q3 * q3)
    yaw = np.arctan2(siny_cosp, cosy_cosp)

    return np.rad2deg(roll), np.rad2deg(pitch), np.rad2deg(yaw)


def _euler_from_dataset(
    data: dict,
    euler_fields: tuple[str, str, str],
    quat_prefix: str | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, str, bool] | None:
    """Read Euler angles from named fields (rad) or quaternion prefix (deg)."""
    roll_f, pitch_f, yaw_f = euler_fields
    if roll_f in data and pitch_f in data and yaw_f in data:
        return (
            np.asarray(data[roll_f], dtype=float),
            np.asarray(data[pitch_f], dtype=float),
            np.asarray(data[yaw_f], dtype=float),
            roll_f,
            False,
        )

    if quat_prefix and all(f"{quat_prefix}[{i}]" in data for i in range(4)):
        roll, pitch, yaw = _quat_fields_to_euler_deg(data, quat_prefix)
        return roll, pitch, yaw, quat_prefix, True

    return None


def _interp_euler(
    time_us: np.ndarray,
    src_us: np.ndarray,
    roll: np.ndarray,
    pitch: np.ndarray,
    yaw: np.ndarray,
    already_deg: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if not already_deg:
        roll = np.rad2deg(roll)
        pitch = np.rad2deg(pitch)
        yaw = np.rad2deg(yaw)
    return (
        _interp_to(time_us, src_us, roll),
        _interp_to(time_us, src_us, pitch),
        _interp_to(time_us, src_us, yaw),
    )


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


def _accel_from_sensor_combined(dataset) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    ts_us = _timestamp_us(dataset)
    ax = np.asarray(dataset.data["accelerometer_m_s2[0]"], dtype=float)
    ay = np.asarray(dataset.data["accelerometer_m_s2[1]"], dtype=float)
    az = np.asarray(dataset.data["accelerometer_m_s2[2]"], dtype=float)
    return ts_us, ax, ay, az


def _load_accel(
    ulog,
    time_us: np.ndarray,
    metadata: dict,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Interpolate accelerometer to gyro timeline (m/s²)."""
    accel_fifo = _safe_dataset(ulog, "sensor_accel_fifo")
    if accel_fifo is not None:
        accel_ts, ax, ay, az = _unpack_sensor_fifo(accel_fifo)
        if len(accel_ts) > 0:
            metadata["has_accel_fifo"] = True
            metadata["accel_source"] = "sensor_accel_fifo"
            return (
                _interp_to(time_us, accel_ts, ax),
                _interp_to(time_us, accel_ts, ay),
                _interp_to(time_us, accel_ts, az),
            )

    combined = _safe_dataset(ulog, "sensor_combined")
    if combined is not None and "accelerometer_m_s2[0]" in combined.data:
        accel_ts, ax, ay, az = _accel_from_sensor_combined(combined)
        metadata["accel_source"] = "sensor_combined"
        return (
            _interp_to(time_us, accel_ts, ax),
            _interp_to(time_us, accel_ts, ay),
            _interp_to(time_us, accel_ts, az),
        )

    veh_accel = _safe_dataset(ulog, "vehicle_acceleration")
    if veh_accel is not None:
        accel_ts = _timestamp_us(veh_accel)
        ax = np.asarray(veh_accel.data["xyz[0]"], dtype=float)
        ay = np.asarray(veh_accel.data["xyz[1]"], dtype=float)
        az = np.asarray(veh_accel.data["xyz[2]"], dtype=float)
        metadata["accel_source"] = "vehicle_acceleration"
        return (
            _interp_to(time_us, accel_ts, ax),
            _interp_to(time_us, accel_ts, ay),
            _interp_to(time_us, accel_ts, az),
        )

    metadata["accel_source"] = None
    _record_missing(
        metadata,
        "Accelerometer: no sensor_accel_fifo, sensor_combined, or vehicle_acceleration topic logged",
    )
    return (
        np.zeros_like(time_us, dtype=float),
        np.zeros_like(time_us, dtype=float),
        np.zeros_like(time_us, dtype=float),
    )


def _load_velocity(
    ulog,
    time_us: np.ndarray,
    metadata: dict,
) -> tuple[
    np.ndarray, np.ndarray, np.ndarray,
    np.ndarray, np.ndarray, np.ndarray,
]:
    """Interpolate local velocity estimate + setpoint to gyro timeline (m/s, NED)."""
    pos = _safe_dataset(ulog, "vehicle_local_position")
    if pos is not None:
        pos_us = _timestamp_us(pos)
        vx = _interp_to(time_us, pos_us, np.asarray(pos.data["vx"], dtype=float))
        vy = _interp_to(time_us, pos_us, np.asarray(pos.data["vy"], dtype=float))
        vz = _interp_to(time_us, pos_us, np.asarray(pos.data["vz"], dtype=float))
        metadata["velocity_source"] = "vehicle_local_position"
    else:
        vx = vy = vz = np.zeros_like(time_us, dtype=float)
        metadata["velocity_source"] = None
        _record_missing(metadata, "Velocity: vehicle_local_position topic not logged")

    pos_sp = _safe_dataset(ulog, "vehicle_local_position_setpoint")
    if pos_sp is not None:
        sp_us = _timestamp_us(pos_sp)
        vx_sp = _interp_to(time_us, sp_us, np.asarray(pos_sp.data["vx"], dtype=float))
        vy_sp = _interp_to(time_us, sp_us, np.asarray(pos_sp.data["vy"], dtype=float))
        vz_sp = _interp_to(time_us, sp_us, np.asarray(pos_sp.data["vz"], dtype=float))
        metadata["velocity_setpoint_source"] = "vehicle_local_position_setpoint"
    else:
        traj_sp = _safe_dataset(ulog, "trajectory_setpoint")
        if traj_sp is not None:
            sp_us = _timestamp_us(traj_sp)
            vx_sp = _interp_to(time_us, sp_us, np.asarray(traj_sp.data["velocity[0]"], dtype=float))
            vy_sp = _interp_to(time_us, sp_us, np.asarray(traj_sp.data["velocity[1]"], dtype=float))
            vz_sp = _interp_to(time_us, sp_us, np.asarray(traj_sp.data["velocity[2]"], dtype=float))
            metadata["velocity_setpoint_source"] = "trajectory_setpoint"
        else:
            vx_sp = vy_sp = vz_sp = np.zeros_like(time_us, dtype=float)
            metadata["velocity_setpoint_source"] = None
            _record_missing(
                metadata,
                "Velocity setpoint: no vehicle_local_position_setpoint or trajectory_setpoint topic logged",
            )

    return vx, vy, vz, vx_sp, vy_sp, vz_sp


def _load_attitude(
    ulog,
    time_us: np.ndarray,
    metadata: dict,
) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    att = _safe_dataset(ulog, "vehicle_attitude")
    if att is None:
        metadata["attitude_source"] = None
        _record_missing(metadata, "Attitude: vehicle_attitude topic not logged")
        return None

    parsed = _euler_from_dataset(att.data, ("roll", "pitch", "yaw"), "q")
    if parsed is None:
        metadata["attitude_source"] = None
        _record_missing(
            metadata,
            "Attitude: vehicle_attitude has no roll/pitch/yaw or quaternion fields",
        )
        return None

    roll, pitch, yaw, label, already_deg = parsed
    att_us = _timestamp_us(att)
    metadata["attitude_source"] = f"vehicle_attitude ({label})"
    return _interp_euler(time_us, att_us, roll, pitch, yaw, already_deg)


def _load_attitude_setpoint(
    ulog,
    time_us: np.ndarray,
    metadata: dict,
) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    att_sp = _safe_dataset(ulog, "vehicle_attitude_setpoint")
    if att_sp is None:
        metadata["attitude_setpoint_source"] = None
        _record_missing(metadata, "Attitude setpoint: vehicle_attitude_setpoint topic not logged")
        return None

    parsed = _euler_from_dataset(
        att_sp.data,
        ("roll_body", "pitch_body", "yaw_body"),
        "q_d",
    )
    if parsed is None:
        parsed = _euler_from_dataset(
            att_sp.data,
            ("roll_d", "pitch_d", "yaw_d"),
            None,
        )

    if parsed is None:
        metadata["attitude_setpoint_source"] = None
        _record_missing(
            metadata,
            "Attitude setpoint: no roll_body, roll_d, or q_d fields in vehicle_attitude_setpoint",
        )
        return None

    roll, pitch, yaw, label, already_deg = parsed
    att_sp_us = _timestamp_us(att_sp)
    metadata["attitude_setpoint_source"] = f"vehicle_attitude_setpoint ({label})"
    return _interp_euler(time_us, att_sp_us, roll, pitch, yaw, already_deg)


def _discover_active_channels(
    dataset,
    field_prefix: str,
    count: int,
    min_std: float,
    max_channels: int = MAX_MOTORS,
) -> list[int]:
    """Return topic field indices with enough variation to be an active motor channel."""
    active: list[int] = []
    for i in range(count):
        field = f"{field_prefix}[{i}]"
        if field not in dataset.data:
            continue
        values = np.asarray(dataset.data[field], dtype=float)
        finite = values[np.isfinite(values)]
        if len(finite) == 0:
            continue
        if float(np.nanstd(finite)) > min_std:
            active.append(i)
    return sorted(active)[:max_channels]


def _discover_motor_output_channels(dataset, max_motors: int = MAX_MOTORS) -> list[int]:
    """Map logical motors 0..N-1 to actuator_outputs output[] indices with varying PWM."""
    return _discover_active_channels(dataset, "output", 16, MOTOR_OUTPUT_MIN_STD, max_motors)


def _discover_motor_control_channels(dataset, max_motors: int = MAX_MOTORS) -> list[int]:
    """Map logical motors 0..N-1 to actuator_motors control[] indices."""
    return _discover_active_channels(dataset, "control", 12, MOTOR_CONTROL_MIN_STD, max_motors)


def _discover_esc_rpm_channels(dataset, max_motors: int = MAX_MOTORS) -> list[int]:
    """Map logical motors 0..N-1 to esc_status esc[N].esc_rpm indices."""
    active: list[int] = []
    for i in range(MAX_ESC_SLOTS):
        field = f"esc[{i}].esc_rpm"
        if field not in dataset.data:
            continue
        values = np.asarray(dataset.data[field], dtype=float)
        finite = values[np.isfinite(values)]
        if len(finite) == 0:
            continue
        if float(np.nanstd(finite)) > ESC_RPM_MIN_STD:
            active.append(i)
    return sorted(active)[:max_motors]


def _load_motors(
    ulog,
    time_us: np.ndarray,
    metadata: dict,
) -> dict[str, np.ndarray]:
    """Load PX4 motor RPM (esc_status), PWM output, and control input onto gyro timeline."""
    result: dict[str, np.ndarray] = {}

    esc = _safe_dataset(ulog, "esc_status")
    if esc is not None:
        rpm_channels = _discover_esc_rpm_channels(esc)
        if rpm_channels:
            esc_us = _timestamp_us(esc)
            for motor_idx, ch in enumerate(rpm_channels):
                rpm = np.asarray(esc.data[f"esc[{ch}].esc_rpm"], dtype=float)
                result[f"eRPM_{motor_idx}_"] = _interp_to(time_us, esc_us, rpm)
            metadata["motor_rpm_source"] = "esc_status"
            metadata["motor_rpm_channels"] = rpm_channels
        else:
            metadata["motor_rpm_source"] = None
            metadata["motor_rpm_channels"] = []
    else:
        metadata["motor_rpm_source"] = None
        metadata["motor_rpm_channels"] = []

    outs = _safe_dataset(ulog, "actuator_outputs")
    if outs is not None:
        out_channels = _discover_motor_output_channels(outs)
        if out_channels:
            out_us = _timestamp_us(outs)
            for motor_idx, ch in enumerate(out_channels):
                pwm = np.asarray(outs.data[f"output[{ch}]"], dtype=float)
                result[f"motor_{motor_idx}_"] = _interp_to(time_us, out_us, pwm)
            metadata["motor_source"] = "actuator_outputs"
            metadata["motor_output_channels"] = out_channels
        else:
            metadata["motor_source"] = None
            metadata["motor_output_channels"] = []
    else:
        metadata["motor_source"] = None
        metadata["motor_output_channels"] = []

    motors_in = _safe_dataset(ulog, "actuator_motors")
    if motors_in is not None:
        in_channels = _discover_motor_control_channels(motors_in)
        if in_channels:
            in_us = _timestamp_us(motors_in)
            for motor_idx, ch in enumerate(in_channels):
                control = np.asarray(motors_in.data[f"control[{ch}]"], dtype=float)
                # Store as percent (0–100) to match motor output trace units in the UI.
                result[f"motor_in_{motor_idx}_"] = (
                    _interp_to(time_us, in_us, control) * 100.0
                )
            metadata["motor_input_source"] = "actuator_motors"
            metadata["motor_input_channels"] = in_channels
        else:
            metadata["motor_input_source"] = None
            metadata["motor_input_channels"] = []
    else:
        metadata["motor_input_source"] = None
        metadata["motor_input_channels"] = []

    if metadata.get("motor_rpm_source") is None and metadata.get("motor_source") is None:
        _record_missing(
            metadata,
            "Motor output/RPM: no esc_status or actuator_outputs with active channels",
        )
    if metadata.get("motor_input_source") is None:
        _record_missing(
            metadata,
            "Motor input: actuator_motors topic not logged or no active control channels",
        )

    return result


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

    metadata: dict = {
        "gyro_source": "sensor_combined",
        "has_gyro_fifo": False,
        "has_accel_fifo": False,
        "accel_unit": "m/s²",
        "velocity_unit": "m/s",
        "velocity_frame": "NED local",
        "attitude_unit": "deg",
        "missing_data": [],
    }

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

    ax, ay, az = _load_accel(ulog, time_us, metadata)
    vx, vy, vz, vx_sp, vy_sp, vz_sp = _load_velocity(ulog, time_us, metadata)

    rates_sp = _safe_dataset(ulog, "vehicle_rates_setpoint")
    if rates_sp is not None:
        sp_us = _timestamp_us(rates_sp)
        sp0 = np.rad2deg(np.asarray(rates_sp.data["roll"], dtype=float))
        sp1 = np.rad2deg(np.asarray(rates_sp.data["pitch"], dtype=float))
        sp2 = np.rad2deg(np.asarray(rates_sp.data["yaw"], dtype=float))
        metadata["rate_setpoint_source"] = "vehicle_rates_setpoint"
    else:
        sp_us = np.array([time_us[0], time_us[-1]])
        sp0 = sp1 = sp2 = np.zeros(2)
        metadata["rate_setpoint_source"] = None
        _record_missing(metadata, "Rate setpoint: vehicle_rates_setpoint topic not logged")

    thrust = _safe_dataset(ulog, "vehicle_thrust_setpoint")
    if thrust is not None:
        thr_us = _timestamp_us(thrust)
        thr = np.clip(-np.asarray(thrust.data["xyz[2]"], dtype=float) * 1000.0, 0.0, 1000.0)
        metadata["throttle_source"] = "vehicle_thrust_setpoint"
    else:
        thr_us = np.array([time_us[0], time_us[-1]])
        thr = np.zeros(2)
        metadata["throttle_source"] = None
        _record_missing(metadata, "Throttle setpoint: vehicle_thrust_setpoint topic not logged")

    df_dict: dict[str, np.ndarray] = {
        "time_us": time_us,
        "gyroADC_0_": gx,
        "gyroADC_1_": gy,
        "gyroADC_2_": gz,
        "setpoint_0_": _interp_to(time_us, sp_us, sp0),
        "setpoint_1_": _interp_to(time_us, sp_us, sp1),
        "setpoint_2_": _interp_to(time_us, sp_us, sp2),
        "setpoint_3_": _interp_to(time_us, thr_us, thr),
        "accel_0_": ax,
        "accel_1_": ay,
        "accel_2_": az,
        "vel_0_": vx,
        "vel_1_": vy,
        "vel_2_": vz,
        "vel_sp_0_": vx_sp,
        "vel_sp_1_": vy_sp,
        "vel_sp_2_": vz_sp,
    }

    attitude = _load_attitude(ulog, time_us, metadata)
    if attitude is not None:
        df_dict["att_roll_"], df_dict["att_pitch_"], df_dict["att_yaw_"] = attitude

    attitude_sp = _load_attitude_setpoint(ulog, time_us, metadata)
    if attitude_sp is not None:
        df_dict["att_sp_roll_"], df_dict["att_sp_pitch_"], df_dict["att_sp_yaw_"] = attitude_sp

    df_dict.update(_load_motors(ulog, time_us, metadata))

    df = pd.DataFrame(df_dict)
    setup_info = _build_setup_info(ulog, path)
    if metadata.get("motor_output_channels"):
        setup_info.append(
            ("Motor output channels", str(metadata["motor_output_channels"]))
        )
    if metadata.get("motor_rpm_channels"):
        setup_info.append(
            ("Motor RPM channels", str(metadata["motor_rpm_channels"]))
        )
    if metadata.get("motor_input_channels"):
        setup_info.append(
            ("Motor input channels", str(metadata["motor_input_channels"]))
        )
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
