"""Tests for PID statistics."""

import json

import numpy as np

from pidbox.core.stats import compute_pid_stats


def test_compute_pid_stats_empty_pid_terms():
    """PX4 and other logs may lack P/I/D/F columns; stats must stay JSON-safe."""
    gyro = np.array([1.0, 2.0, 3.0])
    empty = np.array([])

    stats = compute_pid_stats(gyro, empty, empty, empty, empty, empty, lograte_khz=1.0)

    json.dumps(stats)
    assert stats["gyro_rms"] > 0
    assert stats["pid_error_rms"] > 0
    assert stats["term_balance"]["P_pct"] == 0.0


def test_compute_pid_stats_all_empty():
    empty = np.array([])

    stats = compute_pid_stats(empty, empty, empty, empty, empty, empty, lograte_khz=1.0)

    json.dumps(stats)
    assert stats["gyro_rms"] == 0.0
    assert stats["pid_error_rms"] == 0.0
