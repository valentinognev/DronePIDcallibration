"""API integration tests."""

import pytest
from fastapi.testclient import TestClient

from pidbox.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_session():
    r = client.post("/api/sessions", json={"firmware": "betaflight"})
    assert r.status_code == 200
    assert "session_id" in r.json()


def test_firmwares():
    r = client.get("/api/sessions/firmwares")
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_filter_sim():
    r = client.post(
        "/api/analysis/filter-sim",
        json={"looprate_hz": 8000, "lpf_cutoffs": [250], "notch_configs": [[100, 500]]},
    )
    assert r.status_code == 200
    assert "total_delay_ms" in r.json()


def test_settings():
    r = client.get("/api/settings")
    assert r.status_code == 200
    r2 = client.put("/api/settings", json={"theme": "dark", "y_scale": 500})
    assert r2.status_code == 200
