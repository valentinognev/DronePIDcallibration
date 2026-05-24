"""Tests for chirp / frequency response."""

import numpy as np

from pidbox.core.chirp import estimate_freq_response, find_chirp_window


def test_estimate_freq_response():
    fs = 1000
    t = np.arange(1000) / fs
    inp = np.sin(2 * np.pi * 10 * t)
    out = 0.8 * np.sin(2 * np.pi * 10 * t - 0.1)
    g, c, freq = estimate_freq_response(inp, out, fs, n_est=256, n_overlap=200)
    assert len(g) == len(freq)
    assert np.max(c) <= 1.01


def test_find_chirp_window():
    d = np.zeros(1000)
    d[200:800] = np.linspace(0, 1, 600)
    w = find_chirp_window(d, 1000)
    assert w is not None
    assert w[0] >= 200
