"""Excitation metrics for time-range selection (thrust / roll-pitch / yaw)."""

from __future__ import annotations

import numpy as np

from pidbox.core.sysid.log_adapter import MOTOR_KEYS


def compute_excitation_metrics(model: dict, flight: dict) -> dict[str, dict[str, list[float]]]:
    thrust_dirs = np.asarray(model["rotor_thrust_directions"], dtype=float)
    torque_dirs = np.asarray(model["rotor_torque_directions"], dtype=float)
    positions = np.asarray(model["rotor_positions"], dtype=float)

    torque_vectors = np.array([np.cross(positions[i], thrust_dirs[i]) for i in range(4)])

    ts = flight["data"][MOTOR_KEYS[0]]["timestamps"]
    n = len(ts)
    thrusts = np.zeros(n)
    torques_x = np.zeros(n)
    torques_y = np.zeros(n)
    torques_z = np.zeros(n)
    motors = {f"motor_{i}": [] for i in range(4)}

    for step_i in range(n):
        torque = np.zeros(3)
        torque_drag = 0.0
        thrust = 0.0
        for motor_i in range(4):
            cmd = float(flight["data"][MOTOR_KEYS[motor_i]]["values"][step_i])
            motors[f"motor_{motor_i}"].append(cmd)
            thrust += cmd * thrust_dirs[motor_i, 2]
            torque += torque_vectors[motor_i] * cmd
            torque_drag += cmd * torque_dirs[motor_i, 2]
        thrusts[step_i] = thrust
        torques_x[step_i] = torque[0]
        torques_y[step_i] = torque[1]
        torques_z[step_i] = torque_drag

    t_list = ts.tolist()
    return {
        "timestamps": t_list,
        "motors": motors,
        "thrust_z": {"timestamps": t_list, "values": thrusts.tolist()},
        "torque_x": {"timestamps": t_list, "values": torques_x.tolist()},
        "torque_y": {"timestamps": t_list, "values": torques_y.tolist()},
        "torque_z": {"timestamps": t_list, "values": torques_z.tolist()},
    }
