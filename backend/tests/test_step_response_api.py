"""Step response API tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from pidbox.core.parsers.base import LoadedLog
from pidbox.main import app
from pidbox.session import SessionFile, session_manager

client = TestClient(app)


def _inject_px4_log(session_id: str) -> None:
    lograte = 4.0
    n = int(lograte * 2000 * 3)
    time_us = np.arange(n) * 250
    seg_len = int(lograte * 2000)

    sp = np.zeros(n)
    gy = np.zeros(n)
    sp[seg_len : seg_len + 500] = 50.0
    gy[seg_len : seg_len + 500] = np.linspace(0, 50, 500)

    att_sp = np.zeros(n)
    att = np.zeros(n)
    att_sp[seg_len : seg_len + 500] = 25.0
    att[seg_len : seg_len + 500] = np.linspace(0, 25, 500)

    vel_sp = np.zeros(n)
    vel = np.zeros(n)
    vel_sp[seg_len : seg_len + 500] = 3.0
    vel[seg_len : seg_len + 500] = np.linspace(0, 3.0, 500)

    accel = np.zeros(n)
    accel[seg_len : seg_len + 500] = np.linspace(0, 2.0, 500)

    df = pd.DataFrame(
        {
            "time_us": time_us,
            "gyroADC_0_": gy,
            "gyroADC_1_": np.zeros(n),
            "gyroADC_2_": np.zeros(n),
            "setpoint_0_": sp,
            "setpoint_1_": np.zeros(n),
            "setpoint_2_": np.zeros(n),
            "att_roll_": att,
            "att_pitch_": np.zeros(n),
            "att_yaw_": np.zeros(n),
            "att_sp_roll_": att_sp,
            "att_sp_pitch_": np.zeros(n),
            "att_sp_yaw_": np.zeros(n),
            "vel_0_": vel,
            "vel_1_": np.zeros(n),
            "vel_2_": np.zeros(n),
            "vel_sp_0_": vel_sp,
            "vel_sp_1_": np.zeros(n),
            "vel_sp_2_": np.zeros(n),
            "accel_0_": accel,
            "accel_1_": np.zeros(n),
            "accel_2_": np.zeros(n),
        }
    )
    duration_sec = (time_us[-1] - time_us[0]) / 1_000_000
    log = LoadedLog(
        name="synthetic.ulg",
        source_path="synthetic.ulg",
        dataframe=df,
        setup_info=[],
        lograte_khz=lograte,
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
        default_epoch_end=duration_sec,
    )
    session = session_manager.get(session_id)
    session.files.append(
        SessionFile(
            file_id="test-file",
            original_name="synthetic.ulg",
            logs=[log],
            epoch_start=[0.0],
            epoch_end=[duration_sec],
        )
    )


def test_step_response_rate_backward_compatible():
    r = client.post("/api/sessions", json={"firmware": "px4"})
    session_id = r.json()["session_id"]
    _inject_px4_log(session_id)

    r2 = client.post(
        "/api/analysis/step-response",
        json={"session_id": session_id, "file_indices": [0], "log_idx": 0, "axes": [0]},
    )
    assert r2.status_code == 200
    body = r2.json()
    assert "axes" in body["results"][0]
    assert "signals" not in body["results"][0]
    roll = body["results"][0]["axes"]["roll"]
    assert "mean_curve" in roll
    assert roll["stats"]["n"] >= 1


def test_step_response_attitude_signal():
    r = client.post("/api/sessions", json={"firmware": "px4"})
    session_id = r.json()["session_id"]
    _inject_px4_log(session_id)

    r2 = client.post(
        "/api/analysis/step-response",
        json={
            "session_id": session_id,
            "file_indices": [0],
            "log_idx": 0,
            "axes": [0],
            "signals": ["attitude"],
        },
    )
    assert r2.status_code == 200
    body = r2.json()
    result = body["results"][0]
    assert "signals" in result
    assert "attitude" in result["signals"]
    assert "axes" not in result
    roll = result["signals"]["attitude"]["roll"]
    assert roll["stats"]["n"] >= 1
    assert "pidf" not in roll


def test_step_response_velocity_and_accel_signals():
    r = client.post("/api/sessions", json={"firmware": "px4"})
    session_id = r.json()["session_id"]
    _inject_px4_log(session_id)

    r2 = client.post(
        "/api/analysis/step-response",
        json={
            "session_id": session_id,
            "file_indices": [0],
            "log_idx": 0,
            "axes": [0],
            "signals": ["velocity", "accel"],
        },
    )
    assert r2.status_code == 200
    result = r2.json()["results"][0]
    vel = result["signals"]["velocity"]["roll"]
    acc = result["signals"]["accel"]["roll"]
    assert vel["stats"]["n"] >= 1
    assert len(vel["mean_curve"]) > 0
    assert acc["stats"]["n"] >= 1
    assert len(acc["mean_curve"]) > 0


def test_step_response_unknown_signal():
    r = client.post("/api/sessions", json={"firmware": "betaflight"})
    session_id = r.json()["session_id"]
    r2 = client.post(
        "/api/analysis/step-response",
        json={"session_id": session_id, "signals": ["unknown"]},
    )
    assert r2.status_code == 400
