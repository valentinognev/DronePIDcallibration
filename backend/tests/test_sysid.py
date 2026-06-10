"""Unit tests for quadrotor system identification core."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pidbox.core.parsers.base import LoadedLog
from pidbox.core.sysid.dynamics import combine, filter_ema
from pidbox.core.sysid.estimators import estimate_motor_parameters, search_motor_time_constant
from pidbox.core.sysid.excitation import compute_excitation_metrics
from pidbox.core.sysid.log_adapter import MOTOR_KEYS, capabilities, flight_from_log
from pidbox.core.sysid.preprocess import cleanup_series, extract_timeframes
from pidbox.core.sysid.rotor_model import frd_to_flu, rotor_geometry_from_ca_rotor_params


def _synthetic_model() -> dict:
    return {
        "mass": 1.0,
        "gravity": 9.81,
        "inertia_ratio": 1.5,
        "rotor_positions": np.array(
            [
                [0.1, -0.1, 0.0],
                [-0.1, 0.1, 0.0],
                [0.1, 0.1, 0.0],
                [-0.1, -0.1, 0.0],
            ]
        ),
        "rotor_thrust_directions": np.tile([0.0, 0.0, 1.0], (4, 1)),
        "rotor_torque_directions": np.array(
            [[0, 0, -1], [0, 0, -1], [0, 0, 1], [0, 0, 1]],
            dtype=float,
        ),
    }


def _synthetic_flight(n: int = 200) -> dict:
    ts = np.linspace(0, 2, n)
    data: dict = {}
    for i in range(3):
        data[f"accel_{i}"] = {
            "timestamps": ts,
            "values": np.zeros(n) if i < 2 else np.full(n, -9.81),
        }
        data[f"gyro_{i}"] = {"timestamps": ts, "values": np.zeros(n)}
    for m in range(4):
        data[MOTOR_KEYS[m]] = {
            "timestamps": ts,
            "values": 0.3 + 0.1 * m + 0.05 * np.sin(ts * 5),
        }
    return {
        "name": "synthetic",
        "convention": "flu",
        "motor_source": "motor_in",
        "timestamps": ts,
        "data": data,
    }


def _synthetic_loaded_log(n: int = 200) -> LoadedLog:
    ts_us = np.arange(n, dtype=float) * 1000.0
    df = pd.DataFrame(
        {
            "time_us": ts_us,
            "accel_0_": np.zeros(n),
            "accel_1_": np.zeros(n),
            "accel_2_": np.full(n, -9.81),
            "gyroADC_0_": np.zeros(n),
            "gyroADC_1_": np.zeros(n),
            "gyroADC_2_": np.zeros(n),
            "motor_in_0_": 30.0 + 5 * np.sin(np.linspace(0, 4 * np.pi, n)),
            "motor_in_1_": 35.0,
            "motor_in_2_": 32.0,
            "motor_in_3_": 33.0,
        }
    )
    return LoadedLog(
        name="test.ulg",
        source_path="/tmp/test.ulg",
        dataframe=df,
        setup_info=[("CA_ROTOR_COUNT", "4"), ("CA_ROTOR0_PX", "0.1"), ("CA_ROTOR0_PY", "-0.1")],
        lograte_khz=1.0,
        fw_type="PX4",
        fw_major=0,
        fw_minor=0,
        debug_mode=0,
        debug_indices={},
        gyro_debug_axis=0,
        roll_pidf="",
        pitch_pidf="",
        yaw_pidf="",
        default_epoch_start=0.0,
        default_epoch_end=float(n) / 1000.0,
        metadata={"accel_unit": "m/s²", "accel_source": "vehicle_acceleration"},
    )


def test_frd_to_flu():
    assert np.allclose(frd_to_flu(np.array([1.0, 2.0, 3.0])), [1.0, -2.0, -3.0])


def test_rotor_geometry_from_ca_params():
    geom = rotor_geometry_from_ca_rotor_params(
        {
            "CA_ROTOR_COUNT": "4",
            "CA_ROTOR0_PX": "0.1",
            "CA_ROTOR0_PY": "0.1",
            "CA_ROTOR0_PZ": "0.0",
            "CA_ROTOR0_AX": "0",
            "CA_ROTOR0_AY": "0",
            "CA_ROTOR0_AZ": "1",
        }
    )
    assert geom["rotor_positions"].shape == (4, 3)


def test_cleanup_series_drops_nans():
    ts = np.array([0.0, 0.1, 0.2, 0.3])
    vals = np.array([1.0, np.nan, 3.0, 4.0])
    clean_vals, clean_ts = cleanup_series(ts, vals, window_size=2, min_valid_ratio=0.5)
    assert len(clean_vals) >= 2
    assert not np.any(np.isnan(clean_vals))


def test_filter_ema_converges():
    ts = np.linspace(0, 1, 50)
    sp = np.ones(50)
    out = filter_ema(ts, sp, 0.05)
    assert abs(out[-1] - 1.0) < 0.05


def test_extract_timeframes():
    flight = _synthetic_flight()
    sliced = extract_timeframes([flight], [{"flight": 0, "start": 0.5, "end": 1.5}])
    assert len(sliced) == 1
    motor = sliced[0]["data"][MOTOR_KEYS[0]]["timestamps"]
    assert motor[0] >= 0.5
    assert motor[-1] <= 1.5


def test_excitation_metrics_shape():
    model = _synthetic_model()
    flight = _synthetic_flight()
    metrics = compute_excitation_metrics(model, flight)
    assert len(metrics["timestamps"]) == 200
    assert "thrust_z" in metrics


def test_motor_parameter_estimation_runs():
    model = _synthetic_model()
    flight = _synthetic_flight()
    combined, _ = combine([flight], model, 0.02)
    k_f, rmse = estimate_motor_parameters(combined, model, [2], separate=False)
    assert k_f.shape == (4, 3)
    assert rmse >= 0.0


def test_search_motor_time_constant_runs():
    model = _synthetic_model()
    flight = _synthetic_flight()
    t_m, k_f, candidates, rmses = search_motor_time_constant(
        [flight],
        model,
        [2],
        steps=5,
    )
    assert t_m > 0
    assert len(candidates) == 5
    assert len(rmses) == 5
    assert k_f.shape == (4, 3)


def test_flight_from_loaded_log():
    log = _synthetic_loaded_log()
    assert capabilities(log)["ready"] is True
    flight = flight_from_log(log)
    assert MOTOR_KEYS[0] in flight["data"]
    assert flight["convention"] == "frd"
    assert flight["data"][MOTOR_KEYS[0]]["values"].max() <= 1.0
