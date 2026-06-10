"""Least-squares estimators for thrust curve, inertia, and yaw torque coefficient."""

from __future__ import annotations

import numpy as np

from pidbox.core.sysid.dynamics import combine


def estimate_motor_parameters(
    combined: dict[str, np.ndarray],
    model: dict,
    exponents: list[int],
    *,
    separate: bool = False,
) -> tuple[np.ndarray, float]:
    b_list: list[np.ndarray] = []
    a_rows: list[np.ndarray] = []
    mass = float(model["mass"])
    thrust_dirs = np.asarray(model["rotor_thrust_directions"], dtype=float)

    for step_i in range(len(combined["rpms"])):
        b_list.append(mass * combined["acceleration"][step_i])
        rpm = combined["rpms"][step_i]
        current_a: list[np.ndarray] = []
        if separate:
            for motor_i in range(4):
                for exponent in exponents:
                    current_a.append(thrust_dirs[motor_i] * rpm[motor_i] ** exponent)
        else:
            for exponent in exponents:
                acc = np.zeros(3)
                for motor_i in range(4):
                    acc += thrust_dirs[motor_i] * rpm[motor_i] ** exponent
                current_a.append(acc)
        a_rows.append(np.array(current_a).T)

    n_coeff = (4 if separate else 1) * len(exponents)
    a_mat = np.array(a_rows).reshape(-1, n_coeff)
    b_vec = np.array(b_list).reshape(-1)
    k_f, *_ = np.linalg.lstsq(a_mat, b_vec, rcond=None)
    k_f = k_f.reshape(-1, len(exponents))

    if separate:
        k_f_full = np.array(
            [
                [k_f[motor_i][exponents.index(i)] if i in exponents else 0.0 for i in range(3)]
                for motor_i in range(4)
            ]
        )
    else:
        k_f_full = np.array(
            [[k_f[0][exponents.index(i)] if i in exponents else 0.0 for i in range(3)] for _ in range(4)]
        )

    residual = a_mat @ k_f.reshape(-1) - b_vec
    rmse = float(np.sqrt(np.mean(residual**2)))
    return k_f_full, rmse


def search_motor_time_constant(
    flights: list[dict],
    model: dict,
    exponents: list[int],
    *,
    t_m_min: float = 0.001,
    t_m_max: float = 0.2,
    steps: int = 100,
    separate: bool = False,
) -> tuple[float, np.ndarray, list[float], list[float]]:
    candidates = np.linspace(t_m_min, t_m_max, steps)
    rmses: list[float] = []
    k_fs: list[np.ndarray] = []
    for t_m in candidates:
        combined, _ = combine(flights, model, float(t_m))
        k_f, rmse = estimate_motor_parameters(
            combined, model, exponents, separate=separate
        )
        rmses.append(rmse)
        k_fs.append(k_f)
    best = int(np.argmin(rmses))
    return float(candidates[best]), k_fs[best], candidates.tolist(), rmses


def estimate_inertia_roll_pitch(
    combined: dict[str, np.ndarray],
    *,
    percentile: float = 50.0,
) -> tuple[float, float, dict]:
    results: list[float] = []
    plots: dict[str, dict] = {}
    for axis_i, axis_name in enumerate(["x", "y"]):
        dw_full = combined["domega"][:, axis_i]
        torque_full = combined["pre_torque_geometric"].sum(axis=1)[:, axis_i]
        perc = percentile
        dw_lo = np.percentile(dw_full, perc)
        dw_hi = np.percentile(dw_full, 100.0 - perc)
        mask = (dw_full < dw_lo) | (dw_full > dw_hi)
        dw = dw_full[mask]
        torque = torque_full[mask]
        i_axis = float(np.inner(dw, torque) / np.sum(dw**2))
        results.append(i_axis)
        plots[axis_name] = {
            "torque_full": torque_full.tolist(),
            "dw_full": dw_full.tolist(),
            "torque_fit": torque.tolist(),
            "dw_fit": dw.tolist(),
            "i_axis": i_axis,
            "fit_line_x": [float(torque_full.min()), float(torque_full.max())],
            "fit_line_y": [
                float(torque_full.min() / i_axis),
                float(torque_full.max() / i_axis),
            ],
        }
    return results[0], results[1], plots


def estimate_inertia_yaw(
    combined: dict[str, np.ndarray],
    model: dict,
    i_zz: float,
) -> tuple[float, dict]:
    rotor_torque_dirs = np.asarray(model["rotor_torque_directions"], dtype=float)
    thrust_torques = combined["thrusts"][:, :, np.newaxis] * rotor_torque_dirs
    thrust_torque_z = thrust_torques[:, :, 2].sum(axis=1)
    dwz = combined["domega"][:, 2]
    b = dwz * i_zz
    k_tau = float(np.inner(thrust_torque_z, b) / np.sum(thrust_torque_z**2))
    plot = {
        "thrust_torque_z": thrust_torque_z.tolist(),
        "b": b.tolist(),
        "k_tau": k_tau,
        "fit_line_x": [float(thrust_torque_z.min()), float(thrust_torque_z.max())],
        "fit_line_y": [
            float(k_tau * thrust_torque_z.min()),
            float(k_tau * thrust_torque_z.max()),
        ],
    }
    return k_tau, plot
