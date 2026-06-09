"""Tests for spectral analysis."""

import numpy as np

from pidbox.core.spectral import (
    compute_spectrum_grid,
    psd_2d,
    smooth_spectrum,
    throttle_spectrum,
    time_freq_calc,
)


def test_psd_2d_shape():
    fs = 4.0  # kHz
    n = 1024
    t = np.arange(n) / (fs * 1000)
    y = np.sin(2 * np.pi * 100 * t)
    freqs, spec = psd_2d(y, fs, psd=True)
    assert len(freqs) == n // 2 + 1
    assert len(spec) == n // 2 + 1
    peak_idx = np.argmax(spec)
    assert 90 < freqs[peak_idx] < 110


def test_psd_2d_amplitude_mode():
    y = np.random.randn(512)
    freqs, spec = psd_2d(y, 4.0, psd=False)
    assert np.all(spec >= 0)


def test_time_freq_calc():
    y = np.random.randn(8000)
    tm, freq, spec = time_freq_calc(y, 4.0, smooth_factor=1, subsample_factor=2)
    assert len(tm) > 0
    assert spec.shape[0] == len(freq)


def test_smooth_spectrum_reduces_high_frequency_roughness():
    rng = np.random.default_rng(0)
    n = 2000
    spec = np.sin(np.linspace(0, 40, n)) + rng.normal(0, 0.5, n)
    smoothed = smooth_spectrum(spec, smooth_factor=3)
    assert len(smoothed) == n
    assert np.std(np.diff(smoothed)) < np.std(np.diff(spec))


def test_compute_spectrum_grid_applies_smoothing():
    fs = 4.0
    n = 4096
    t = np.arange(n) / (fs * 1000)
    y = np.sin(2 * np.pi * 100 * t) + 0.1 * np.random.default_rng(1).standard_normal(n)
    raw = compute_spectrum_grid({"gyro": y}, fs, smooth_factor=0)["gyro"]["spec"]
    smooth = compute_spectrum_grid({"gyro": y}, fs, smooth_factor=3)["gyro"]["spec"]
    assert np.std(np.diff(smooth)) < np.std(np.diff(raw))


def test_compute_spectrum_grid_smoothing_amplitude_mode():
    fs = 4.0
    n = 4096
    t = np.arange(n) / (fs * 1000)
    y = np.sin(2 * np.pi * 100 * t) + 0.1 * np.random.default_rng(2).standard_normal(n)
    raw = compute_spectrum_grid({"gyro": y}, fs, psd=False, smooth_factor=0)["gyro"]["spec"]
    smooth = compute_spectrum_grid({"gyro": y}, fs, psd=False, smooth_factor=3)["gyro"]["spec"]
    assert np.std(np.diff(smooth)) < np.std(np.diff(raw))


def test_throttle_spectrum():
    n = 40000
    throttle = np.linspace(0, 100, n)
    y = np.random.randn(n) * 0.1
    freq, amp = throttle_spectrum(throttle, y, 4.0, psd=True)
    assert amp.shape[0] == 100
