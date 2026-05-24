"""Regression tests for QA issues PID-001, PID-004, PID-005, PID-006."""

from __future__ import annotations

import io

import numpy as np
import pytest
from fastapi.testclient import TestClient

from pidbox.config import default_epoch_bounds
from pidbox.main import app

client = TestClient(app)


def test_default_epoch_bounds_short_log():
    start, end = default_epoch_bounds(2.0)
    assert start < end
    assert start == 0.0
    assert end == 2.0


def test_default_epoch_bounds_normal_log():
    start, end = default_epoch_bounds(10.0)
    assert start == 2.0
    assert end == 9.0


def _synthetic_csv_bytes(duration_sec: float, rate_khz: float = 4.0) -> bytes:
    n = int(duration_sec * rate_khz * 1000)
    dt_us = int(1_000_000 / (rate_khz * 1000))
    t = np.arange(n) * dt_us
    gyro = 50 * np.sin(2 * np.pi * 20 * t / 1e6)
    throttle = 500 + 200 * np.sin(2 * np.pi * 0.5 * t / 1e6)
    lines = ["time (us),gyroADC_0_,gyroADC_1_,gyroADC_2_,setpoint_0_,setpoint_1_,setpoint_2_,setpoint_3_,axisP_0_,axisI_0_,axisD_0_,axisF_0_,motor_0_"]
    for i in range(n):
        lines.append(
            f"{t[i]},{gyro[i]:.4f},{gyro[i]:.4f},{gyro[i]:.4f},"
            f"{gyro[i]:.4f},{gyro[i]:.4f},{gyro[i]:.4f},{throttle[i]:.4f},"
            f"{gyro[i] * 0.1:.4f},{gyro[i] * 0.05:.4f},{gyro[i] * 0.02:.4f},{gyro[i] * 0.01:.4f},"
            f"{1000 + i % 100:.0f}"
        )
    return "\n".join(lines).encode()


def _upload_session(csv_bytes: bytes, filename: str = "test.csv") -> str:
    r = client.post("/api/sessions", json={"firmware": "betaflight"})
    assert r.status_code == 200
    session_id = r.json()["session_id"]
    r = client.post(
        f"/api/sessions/{session_id}/files",
        files={"file": (filename, io.BytesIO(csv_bytes), "text/csv")},
    )
    assert r.status_code == 200, r.text
    return session_id


def test_pid001_traces_default_epoch_short_log():
    session_id = _upload_session(_synthetic_csv_bytes(2.0))
    r = client.post(
        f"/api/sessions/{session_id}/traces",
        json={"file_idx": 0, "log_idx": 0, "axes": [0], "traces": ["gyro"]},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["panels"]["roll"]
    assert len(data["panels"]["roll"][0]["y"]) > 0


def test_pid004_stats_returns_200():
    session_id = _upload_session(_synthetic_csv_bytes(10.0))
    r = client.post(
        "/api/analysis/stats",
        json={"session_id": session_id, "file_idx": 0, "axis": 0},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "stats" in body
    assert "term_balance" in body["stats"]


def test_pid005_spectrum_returns_200():
    session_id = _upload_session(_synthetic_csv_bytes(10.0))
    r = client.post(
        "/api/analysis/spectrum",
        json={
            "session_id": session_id,
            "file_indices": [0],
            "axes": [0, 1, 2],
            "traces": ["gyro"],
            "psd": True,
        },
    )
    assert r.status_code == 200, r.text
    results = r.json()["results"]
    assert results[0]["axes"]["roll"]["gyro"]["freq"]
    assert results[0]["axes"]["roll"]["gyro"]["spec"]


def test_pid006_throttle_spectrum_returns_200():
    session_id = _upload_session(_synthetic_csv_bytes(10.0))
    r = client.post(
        "/api/analysis/throttle-spectrum",
        json={
            "session_id": session_id,
            "file_idx": 0,
            "axis": 0,
            "trace": "gyro",
            "psd": True,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "freq_hz" in body
    assert "amp_matrix" in body
    assert len(body["amp_matrix"]) == 100
