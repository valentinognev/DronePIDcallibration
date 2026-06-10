"""Tests for log viewer trace scaling."""

from __future__ import annotations

import pytest
import numpy as np
import pandas as pd

from pidbox.core.traces import extract_log_viewer_traces, get_trace
from pidbox.core.parsers.base import LoadedLog


def _mock_log(df: pd.DataFrame) -> LoadedLog:
    return LoadedLog(
        name="test.csv",
        source_path="test.bbl",
        dataframe=df,
        setup_info=[],
        lograte_khz=4.0,
        fw_type="BF",
        fw_major=4,
        fw_minor=5,
        debug_mode=0,
        debug_indices={},
        gyro_debug_axis=0,
        roll_pidf="",
        pitch_pidf="",
        yaw_pidf="",
        default_epoch_start=0.0,
        default_epoch_end=10.0,
    )


def test_throttle_percent_from_setpoint():
    df = pd.DataFrame({"time_us": np.arange(0, 4000, 1000), "setpoint_3_": [0, 360, 637, 1000]})
    y = get_trace(df, "throttle", None)
    assert y is not None
    np.testing.assert_allclose(y, [0, 36, 63.7, 100])


def test_throttle_percent_from_rc_command():
    df = pd.DataFrame({"time_us": np.arange(0, 3000, 1000), "rcCommand_3_": [1000, 1360, 1631]})
    y = get_trace(df, "throttle", None)
    assert y is not None
    np.testing.assert_allclose(y, [0, 36, 63.1])


def test_motor_panel_uses_erpm_when_available():
    n = 100
    df = pd.DataFrame(
        {
            "time_us": np.arange(n) * 250,
            "setpoint_3_": np.full(n, 500),
            "eRPM_0_": np.linspace(100, 2000, n),
            "motor_0_": np.linspace(10, 90, n),
        }
    )
    log = _mock_log(df)
    data = extract_log_viewer_traces(
        log, 0.0, 10.0, [0], ["throttle", "motor_0"], smooth_factor=1, downsample=False
    )
    throttle = next(t for t in data["motor_panel"] if t["key"] == "throttle")
    motor = next(t for t in data["motor_panel"] if t["key"] == "motor_0")

    assert throttle["y"][0] == 50.0
    assert motor["y"][-1] == 2000.0
    assert motor["yaxis"] == "y2"
    assert data["motor_panel_units"]["motors"] == "rpm"
    assert data["full_time_range"][0] == 0.0
    assert data["full_time_range"][1] == pytest.approx(0.02475)


def test_trace_time_absolute_from_log_start():
    n = 400
    df = pd.DataFrame(
        {
            "time_us": np.arange(n) * 250,
            "gyroADC_0_": np.zeros(n),
        }
    )
    log = _mock_log(df)
    data = extract_log_viewer_traces(log, 0.01, 0.05, [0], ["gyro"], smooth_factor=1, downsample=False)
    gyro = data["panels"]["roll"][0]
    assert gyro["x"][0] == pytest.approx(0.01, abs=0.001)
    assert gyro["x"][-1] == pytest.approx(0.05, abs=0.001)
    assert data["time_range"][0] == pytest.approx(0.01, abs=0.001)
    assert data["time_range"][1] == pytest.approx(0.05, abs=0.001)


def test_full_time_range_independent_of_epoch():
    n = 400
    df = pd.DataFrame(
        {
            "time_us": np.arange(n) * 250,
            "gyroADC_0_": np.zeros(n),
        }
    )
    log = _mock_log(df)
    data = extract_log_viewer_traces(log, 0.01, 0.05, [0], ["gyro"], smooth_factor=1, downsample=False)
    assert data["full_time_range"] == [0.0, pytest.approx(0.09975)]
    assert data["epoch"] == [0.01, 0.05]


def test_empty_epoch_slice_returns_empty_panels():
    n = 100
    df = pd.DataFrame(
        {
            "time_us": np.arange(n) * 250,
            "gyroADC_0_": np.linspace(0, 10, n),
            "setpoint_3_": np.full(n, 500),
        }
    )
    log = _mock_log(df)
    data = extract_log_viewer_traces(
        log, 50.0, 60.0, [0, 1], ["gyro", "throttle"], smooth_factor=1, downsample=False
    )
    assert data["time_range"] == [50.0, 60.0]
    assert data["epoch"] == [50.0, 60.0]
    assert data["full_time_range"] == [0.0, pytest.approx(0.02475)]
    assert data["panels"] == {"roll": [], "pitch": []}
    assert data["motor_panel"] == []
    assert data["metadata"]["name"] == "test.csv"


def test_gyro_pf_uses_debug_not_axis_dpf():
    n = 100
    gyro = np.sin(np.linspace(0, 20, n))
    prefilt = gyro * 2.0 + 0.5
    dpf = np.gradient(gyro)
    df = pd.DataFrame(
        {
            "time_us": np.arange(n) * 250,
            "gyroADC_0_": gyro,
            "debug_0_": prefilt,
            "axisDpf_0_": dpf,
        }
    )
    y = get_trace(df, "gyro_pf", 0)
    assert y is not None
    np.testing.assert_allclose(y, prefilt)


def test_gyro_pf_prefers_gyro_unfilt_when_debug_is_flat():
    n = 100
    prefilt = np.sin(np.linspace(0, 20, n))
    df = pd.DataFrame(
        {
            "time_us": np.arange(n) * 250,
            "gyroADC_0_": prefilt * 0.5,
            "debug_0_": np.zeros(n),
            "gyroUnfilt_0_": prefilt,
        }
    )
    y = get_trace(df, "gyro_pf", 0)
    assert y is not None
    np.testing.assert_allclose(y, prefilt)


def test_px4_like_traces_available_and_extracted():
    n = 200
    df = pd.DataFrame(
        {
            "time_us": np.arange(n) * 250,
            "accel_0_": np.linspace(0, 5, n),
            "accel_1_": np.linspace(0, 4, n),
            "accel_2_": np.linspace(9.8, 10.2, n),
            "att_roll_": np.linspace(-5, 5, n),
            "att_pitch_": np.linspace(-3, 3, n),
            "att_yaw_": np.linspace(0, 180, n),
            "att_sp_roll_": np.zeros(n),
            "att_sp_pitch_": np.zeros(n),
            "att_sp_yaw_": np.zeros(n),
            "vel_0_": np.linspace(-1, 1, n),
            "vel_1_": np.linspace(-2, 2, n),
            "vel_2_": np.linspace(-0.5, 0.5, n),
            "vel_sp_0_": np.zeros(n),
            "vel_sp_1_": np.zeros(n),
            "vel_sp_2_": np.zeros(n),
        }
    )
    from pidbox.core.traces import list_available_traces

    available = list_available_traces(df)
    for key in ("accel", "attitude", "attitude_sp", "velocity", "velocity_sp"):
        assert key in available

    log = _mock_log(df)
    data = extract_log_viewer_traces(
        log,
        0.0,
        10.0,
        [0, 1, 2],
        ["accel", "attitude", "attitude_sp", "velocity", "velocity_sp"],
        smooth_factor=1,
        downsample=False,
    )
    assert len(data["panels"]["roll"]) == 5
    assert data["panels"]["roll"][0]["key"] == "accel"
    assert data["panels"]["roll"][1]["key"] == "attitude"
    assert get_trace(df, "attitude", 0) is not None
    assert get_trace(df, "velocity_sp", 2) is not None
