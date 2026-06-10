"""End-to-end system identification pipeline."""

from __future__ import annotations

import numpy as np

from pidbox.core.parsers.base import LoadedLog
from pidbox.core.sysid.dynamics import combine
from pidbox.core.sysid.estimators import (
    estimate_inertia_roll_pitch,
    estimate_inertia_yaw,
    estimate_motor_parameters,
    search_motor_time_constant,
)
from pidbox.core.sysid.excitation import compute_excitation_metrics
from pidbox.core.sysid.log_adapter import capabilities, defaults_from_log, flight_from_log
from pidbox.core.sysid.preprocess import cleanup_series, extract_timeframes, slice_gaps_and_interpolate


def _build_model(request_model: dict) -> dict:
    return {
        "mass": float(request_model["mass"]),
        "gravity": float(request_model.get("gravity", 9.81)),
        "inertia_ratio": float(request_model.get("inertia_ratio", 1.832)),
        "rotor_positions": np.asarray(request_model["rotor_positions"], dtype=float),
        "rotor_thrust_directions": np.asarray(request_model["rotor_thrust_directions"], dtype=float),
        "rotor_torque_directions": np.asarray(request_model["rotor_torque_directions"], dtype=float),
    }


def _clean_flight(flight: dict) -> dict:
    data = {}
    for column_name, series in flight["data"].items():
        values, timestamps = cleanup_series(series["timestamps"], series["values"])
        if len(timestamps) == 0:
            continue
        data[column_name] = {"timestamps": timestamps, "values": values}
    return {**flight, "data": data}


def load_flights(logs: list[LoadedLog]) -> list[dict]:
    return [_clean_flight(flight_from_log(log)) for log in logs]


def preview_excitation(logs: list[LoadedLog], model: dict) -> dict:
    flights = load_flights(logs)
    m = _build_model(model)
    previews = []
    for flight in flights:
        metrics = compute_excitation_metrics(m, flight)
        previews.append(
            {
                "name": flight["name"],
                "motor_source": flight.get("motor_source"),
                "frame_convention": flight.get("convention"),
                "time_range": [
                    float(metrics["timestamps"][0]) if metrics["timestamps"] else 0.0,
                    float(metrics["timestamps"][-1]) if metrics["timestamps"] else 0.0,
                ],
                "metrics": metrics,
            }
        )
    return {"flights": previews}


def defaults_from_session_log(log: LoadedLog) -> dict:
    return defaults_from_log(log)


def log_capabilities(log: LoadedLog) -> dict:
    return capabilities(log)


def _timeframes_to_internal(timeframes: list[dict], flight_index_map: dict[int, int]) -> list[dict]:
    out = []
    for tf in timeframes:
        file_idx = int(tf["file_idx"])
        out.append(
            {
                "flight": flight_index_map[file_idx],
                "start": float(tf["start"]),
                "end": float(tf["end"]),
            }
        )
    return out


def _thrust_diagnostic_plots(
    combined: dict[str, np.ndarray],
    model: dict,
    k_f_mean: np.ndarray,
) -> dict:
    mass = float(model["mass"])
    squared_sp = (combined["rpm_setpoints"] ** 2).sum(axis=1)
    # T = d * (ω₁² + ω₂² + ω₃² + ω₄²); motor commands act as ω after delay filter.
    omega_sq = (combined["rpms"] ** 2).sum(axis=1)
    squared_rpm = omega_sq
    actual_thrust = combined["acceleration"][:, 2] * mass
    predicted_thrust = combined["thrusts"].sum(axis=1)

    abs_accel = np.abs(combined["acceleration"][:, 2] - 9.81)
    hover_perc = 5.0
    mask = abs_accel < float(np.percentile(abs_accel, hover_perc))
    hovering_rpms = combined["rpms"][mask].ravel()
    hovering_rpm = float(np.median(hovering_rpms)) if len(hovering_rpms) else 0.0
    hovering_omega_sq = omega_sq[mask]
    median_omega_sq = float(np.median(hovering_omega_sq)) if len(hovering_omega_sq) else 0.0

    predicted_hover = 0.0
    if k_f_mean[2] != 0:
        disc = k_f_mean[1] ** 2 - 4 * k_f_mean[2] * (k_f_mean[0] - 9.81 * mass / 4.0)
        if disc >= 0:
            predicted_hover = float((-k_f_mean[1] + np.sqrt(disc)) / (2 * k_f_mean[2]))
    thrust_vs_rpm: dict = {
        "omega_sq": omega_sq.tolist(),
        "thrust": actual_thrust.tolist(),
        "fit_quad": {},
    }
    quad_d = 0.0
    if len(omega_sq) > 2:
        denom = float(np.dot(omega_sq, omega_sq))
        quad_d = float(np.dot(omega_sq, actual_thrust) / denom) if denom > 0 else 0.0
        x_min, x_max = float(omega_sq.min()), float(omega_sq.max())
        x_line = np.linspace(x_min, x_max, 100)
        thrust_vs_rpm["fit_quad"] = {
            "d": quad_d,
            "x": x_line.tolist(),
            "y": (quad_d * x_line).tolist(),
        }

    return {
        "delay_comparison": {
            "squared_sp": squared_sp.tolist(),
            "squared_rpm": squared_rpm.tolist(),
            "actual_thrust": actual_thrust.tolist(),
        },
        "thrust_fit": {
            "predicted": predicted_thrust.tolist(),
            "actual": actual_thrust.tolist(),
        },
        "hover_hist": {
            "rpms": hovering_rpms.tolist(),
            "median_rpm": hovering_rpm,
            "median_omega_sq": median_omega_sq,
            "predicted_hover_rpm": predicted_hover,
            "predicted_omega_sq": float(mass * 9.81 / quad_d) if quad_d > 0 else 0.0,
            "hover_percentile": hover_perc,
        },
        "thrust_vs_rpm": thrust_vs_rpm,
    }


def run_sysid(
    logs: list[LoadedLog],
    file_indices: list[int],
    model: dict,
    *,
    exponents: list[int],
    separate_motors: bool,
    timeframes_thrust: list[dict],
    timeframes_inertia_rp: list[dict],
    timeframes_inertia_yaw: list[dict],
    t_m_steps: int = 100,
    t_m_min: float = 0.001,
    t_m_max: float = 0.2,
) -> dict:
    flights = load_flights(logs)
    m = _build_model(model)
    flight_index_map = {fi: i for i, fi in enumerate(file_indices)}

    tf_thrust = _timeframes_to_internal(timeframes_thrust, flight_index_map)
    tf_rp = _timeframes_to_internal(timeframes_inertia_rp, flight_index_map)
    tf_yaw = _timeframes_to_internal(timeframes_inertia_yaw, flight_index_map)

    flights_thrust = slice_gaps_and_interpolate(extract_timeframes(flights, tf_thrust))
    flights_rp = slice_gaps_and_interpolate(extract_timeframes(flights, tf_rp))
    flights_yaw = slice_gaps_and_interpolate(extract_timeframes(flights, tf_yaw))

    if not flights_thrust:
        raise ValueError("No usable thrust timeframe data after gap handling")
    if not flights_rp:
        raise ValueError("No usable roll/pitch inertia timeframe data after gap handling")
    if not flights_yaw:
        raise ValueError("No usable yaw timeframe data after gap handling")

    t_m, k_f, t_m_candidates, rmses = search_motor_time_constant(
        flights_thrust,
        m,
        exponents,
        t_m_min=t_m_min,
        t_m_max=t_m_max,
        steps=t_m_steps,
        separate=separate_motors,
    )
    k_f_mean = k_f.mean(axis=0)
    thrust_curves = np.array([k_f_mean for _ in range(4)])

    combined_thrust, _ = combine(flights_thrust, m, t_m, thrust_curves=thrust_curves)
    combined_rp, _ = combine(flights_rp, m, t_m, thrust_curves=thrust_curves)
    combined_yaw, _ = combine(flights_yaw, m, t_m, thrust_curves=thrust_curves)

    _, thrust_rmse = estimate_motor_parameters(
        combined_thrust, m, exponents, separate=separate_motors
    )

    i_xx, i_yy, inertia_plots = estimate_inertia_roll_pitch(combined_rp)
    i_zz = (i_xx + i_yy) / 2.0 * float(m["inertia_ratio"])
    k_tau, yaw_plot = estimate_inertia_yaw(combined_yaw, m, i_zz)

    plots = _thrust_diagnostic_plots(combined_thrust, m, k_f_mean)
    plots["tau_curve"] = {"t_m_candidates": t_m_candidates, "rmses": rmses, "t_m": t_m}
    plots["inertia"] = inertia_plots
    plots["yaw"] = yaw_plot

    return {
        "parameters": {
            "t_m": t_m,
            "k_f": k_f.tolist(),
            "k_f_mean": k_f_mean.tolist(),
            "thrust_rmse": thrust_rmse,
            "i_xx": i_xx,
            "i_yy": i_yy,
            "i_zz": i_zz,
            "k_tau": k_tau,
            "mass": float(m["mass"]),
            "inertia_ratio": float(m["inertia_ratio"]),
        },
        "plots": plots,
    }
