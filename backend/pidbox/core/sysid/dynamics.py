"""Motor delay filtering and flight data combination."""

from __future__ import annotations

import numpy as np

from pidbox.core.sysid.log_adapter import ACCEL_KEYS, GYRO_KEYS, MOTOR_KEYS
from pidbox.core.sysid.rotor_model import frd_to_flu


def filter_ema(timestamps: np.ndarray, rpm_setpoints: np.ndarray, t_m: float) -> np.ndarray:
    rpms_filtered: list[float] = []
    rpm: float | None = None
    previous_t: float | None = None
    for t, rpm_setpoint in zip(timestamps, rpm_setpoints, strict=True):
        if rpm is None:
            rpm = float(rpm_setpoint)
        else:
            delta_t = t - previous_t  # type: ignore[operator]
            alpha = np.exp(-delta_t / t_m)
            rpm = alpha * rpm + (1.0 - alpha) * float(rpm_setpoint)
        rpms_filtered.append(rpm)
        previous_t = t
    return np.array(rpms_filtered)


def combine(
    flights: list[dict],
    model: dict,
    t_m: float,
    thrust_curves: np.ndarray | None = None,
) -> tuple[dict[str, np.ndarray], list[dict]]:
    """Convert FRD→FLU when needed, apply motor EMA, optionally compute thrusts/torques."""
    if thrust_curves is not None:
        assert len(thrust_curves) == 4

    rotor_positions = np.asarray(model["rotor_positions"], dtype=float)
    rotor_thrust_dirs = np.asarray(model["rotor_thrust_directions"], dtype=float)
    rotor_torque_dirs = np.asarray(model["rotor_torque_directions"], dtype=float)

    for flight in flights:
        timestamps = flight["timestamps"]
        frd = flight.get("convention", "flu") == "frd"

        rpm_setpoints = np.array(
            [flight["data"][key]["values"] for key in MOTOR_KEYS],
            dtype=float,
        ).T

        accel_raw = np.array(
            [flight["data"][key]["values"] for key in ACCEL_KEYS],
            dtype=float,
        ).T
        acceleration = np.array([frd_to_flu(a) for a in accel_raw]) if frd else accel_raw

        omega_raw = np.array(
            [flight["data"][key]["values"] for key in GYRO_KEYS],
            dtype=float,
        ).T
        omega = np.array([frd_to_flu(o) for o in omega_raw]) if frd else omega_raw
        domega = np.gradient(omega, timestamps, axis=0)

        flight["rpm_setpoints"] = rpm_setpoints
        flight["rpms"] = np.column_stack(
            [filter_ema(timestamps, rpm_setpoints[:, i], t_m) for i in range(4)]
        )
        flight["acceleration"] = acceleration
        flight["omega"] = omega
        flight["domega"] = domega

        if thrust_curves is not None:

            def apply_thrust_curves(rpms: np.ndarray, curves: np.ndarray) -> np.ndarray:
                thrusts = []
                for curve, rpm in zip(curves, rpms, strict=True):
                    thrust = sum(coeff * rpm**exp for exp, coeff in enumerate(curve))
                    thrusts.append(thrust)
                return np.array(thrusts)

            flight["thrusts"] = np.array(
                [apply_thrust_curves(rpms, thrust_curves) for rpms in flight["rpms"]]
            )
            motor_thrust_to_torque = np.array(
                [np.cross(rotor_positions[m], rotor_thrust_dirs[m]) for m in range(4)]
            )
            flight["pre_torque"] = flight["thrusts"][:, :, np.newaxis] * rotor_torque_dirs
            flight["pre_torque_geometric"] = (
                flight["thrusts"][:, :, np.newaxis] * motor_thrust_to_torque
            )

    thrusts_combined: dict[str, np.ndarray] = {}
    if thrust_curves is not None:
        thrusts_combined = {
            "thrusts": np.concatenate([f["thrusts"] for f in flights]),
            "pre_torque": np.concatenate([f["pre_torque"] for f in flights]),
            "pre_torque_geometric": np.concatenate([f["pre_torque_geometric"] for f in flights]),
        }

    combined = {
        "rpm_setpoints": np.concatenate([f["rpm_setpoints"] for f in flights]),
        "rpms": np.concatenate([f["rpms"] for f in flights]),
        "acceleration": np.concatenate([f["acceleration"] for f in flights]),
        "omega": np.concatenate([f["omega"] for f in flights]),
        "domega": np.concatenate([f["domega"] for f in flights]),
        **thrusts_combined,
    }
    return combined, flights
