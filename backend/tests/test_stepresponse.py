"""Tests for step response."""

import numpy as np

from pidbox.core.stepresponse import step_calc, step_stats


def test_step_calc_empty():
    sp = np.zeros(100)
    gy = np.zeros(100)
    resp, t = step_calc(sp, gy, 4.0)
    assert resp.shape[0] == 0 or resp.ndim == 2


def test_step_calc_with_step():
    lograte = 4.0
    n = int(lograte * 2000 * 3)
    sp = np.zeros(n)
    gy = np.zeros(n)
    seg_len = int(lograte * 2000)
    sp[seg_len : seg_len + 500] = 50
    gy[seg_len : seg_len + 500] = np.linspace(0, 50, 500)
    resp, t = step_calc(sp, gy, lograte, smooth_factor=1)
    assert len(t) > 0


def test_step_stats():
    resp = np.array([[0, 0.2, 0.8, 1.0, 1.0], [0, 0.3, 0.7, 0.9, 1.0]])
    t = np.array([0, 50, 100, 200, 500])
    stats = step_stats(resp, t)
    assert stats["n"] == 2
    assert stats["peak_mean"] > 0
