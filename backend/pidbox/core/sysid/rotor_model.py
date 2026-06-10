"""Rotor geometry helpers (FLU frame)."""

from __future__ import annotations

import numpy as np

ROT_MAT_FLU_FRD = np.array([[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]])


def frd_to_flu(vec: np.ndarray) -> np.ndarray:
    return ROT_MAT_FLU_FRD @ np.asarray(vec, dtype=float)


def rotor_geometry_from_ca_rotor_params(params: dict[str, str]) -> dict[str, np.ndarray]:
    """Build rotor arrays from PX4 CA_ROTOR* parameter dict (values as strings)."""
    num_rotors = int(float(params.get("CA_ROTOR_COUNT", 4)))
    rotor_positions: list[np.ndarray] = []
    rotor_thrust_directions: list[np.ndarray] = []
    rotor_torque_directions: list[np.ndarray] = []

    for i in range(num_rotors):
        px = float(params.get(f"CA_ROTOR{i}_PX", 0.0))
        py = float(params.get(f"CA_ROTOR{i}_PY", 0.0))
        pz = float(params.get(f"CA_ROTOR{i}_PZ", 0.0))
        rotor_positions.append(frd_to_flu(np.array([px, py, pz])))

        ax = float(params.get(f"CA_ROTOR{i}_AX", 0.0))
        ay = float(params.get(f"CA_ROTOR{i}_AY", 0.0))
        az = float(params.get(f"CA_ROTOR{i}_AZ", 1.0))
        rotor_thrust_directions.append(frd_to_flu(np.array([ax, ay, az])))

        torque_sign = 1.0 if np.sign(px) == np.sign(py) else -1.0
        rotor_torque_directions.append(frd_to_flu(np.array([0.0, 0.0, torque_sign])))

    return {
        "rotor_positions": np.array(rotor_positions),
        "rotor_thrust_directions": np.array(rotor_thrust_directions),
        "rotor_torque_directions": np.array(rotor_torque_directions),
    }
