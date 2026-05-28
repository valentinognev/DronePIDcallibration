"""Tests for rejecting uploads that parse to zero logs (ISSUE-004)."""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from pidbox.core.loader import empty_parse_error_message
from pidbox.main import app

client = TestClient(app)


def test_empty_parse_error_message_ulg_betaflight_session():
    msg = empty_parse_error_message(Path("flight.ulg"), "betaflight")
    assert "No logs could be parsed" in msg
    assert "px4" in msg.lower()
    assert "betaflight" in msg


def test_upload_rejects_empty_parse_no_session_file():
    r = client.post("/api/sessions", json={"firmware": "betaflight"})
    assert r.status_code == 200
    session_id = r.json()["session_id"]

    with patch("pidbox.session.load_log_file", return_value=[]):
        r = client.post(
            f"/api/sessions/{session_id}/files",
            files={"file": ("flight.ulg", io.BytesIO(b"\x00"), "application/octet-stream")},
        )

    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "No logs could be parsed" in detail
    assert "px4" in detail.lower()

    info = client.get(f"/api/sessions/{session_id}")
    assert info.status_code == 200
    assert info.json()["files"] == []


def test_upload_valid_csv_still_succeeds():
    lines = [
        "time (us),gyroADC_0_,gyroADC_1_,gyroADC_2_",
        "0,1.0,2.0,3.0",
        "250,1.1,2.1,3.1",
    ]
    content = "\n".join(lines).encode()

    r = client.post("/api/sessions", json={"firmware": "betaflight"})
    session_id = r.json()["session_id"]
    r = client.post(
        f"/api/sessions/{session_id}/files",
        files={"file": ("tiny.csv", io.BytesIO(content), "text/csv")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["log_count"] >= 1
