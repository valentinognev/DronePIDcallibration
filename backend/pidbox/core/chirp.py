"""Chirp / frequency response estimation - port of PSestimateFreqResponse.m."""

from __future__ import annotations

import numpy as np


def estimate_freq_response(
    inp: np.ndarray,
    out: np.ndarray,
    fs: float,
    n_est: int | None = None,
    n_overlap: int | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Welch cross-spectral frequency response estimation.
    Returns G (complex), C (coherence), freq (Hz).
    """
    inp = np.asarray(inp, dtype=float).ravel()
    out = np.asarray(out, dtype=float).ravel()

    if n_est is None:
        n_est = round(2.5 * fs)
    if n_overlap is None:
        n_overlap = round(0.9 * n_est)

    n = min(len(inp), len(out))
    inp = inp[:n] - np.mean(inp[:n])
    out = out[:n] - np.mean(out[:n])

    w = np.hanning(n_est)
    n_step = n_est - n_overlap
    n_seg = (n - n_est) // n_step + 1

    n_half = n_est // 2 + 1
    if n_seg < 1:
        freq = np.arange(n_half) * fs / n_est
        return np.zeros(n_half), np.zeros(n_half), freq

    w_norm = np.sum(w) / n_est / 2
    suu = np.zeros(n_half)
    syu = np.zeros(n_half, dtype=complex)
    syy = np.zeros(n_half)

    for s in range(n_seg):
        i0 = s * n_step
        idx = slice(i0, i0 + n_est)
        u_seg = inp[idx] * w
        y_seg = out[idx] * w

        u_fft = np.fft.fft(u_seg, n_est)[:n_half] / (n_est * w_norm)
        y_fft = np.fft.fft(y_seg, n_est)[:n_half] / (n_est * w_norm)

        u_fft[0] /= 2
        u_fft[-1] /= 2
        y_fft[0] /= 2
        y_fft[-1] /= 2

        suu += np.abs(u_fft) ** 2
        syu += y_fft * np.conj(u_fft)
        syy += np.abs(y_fft) ** 2

    suu /= n_seg
    syu /= n_seg
    syy /= n_seg

    delta = np.max(suu) * 1e-12
    g = syu / (suu + delta)
    c = np.abs(syu) ** 2 / (suu * syy + delta)
    freq = np.arange(n_half) * fs / n_est

    return g, c, freq


def find_chirp_window(
    debug0: np.ndarray, fs: float, threshold: float = 0.5
) -> tuple[int, int] | None:
    """Find chirp excitation window from debug_0_ signal."""
    d = np.asarray(debug0, dtype=float)
    if len(d) == 0:
        return None
    d_norm = (d - np.min(d)) / (np.max(d) - np.min(d) + 1e-12)
    above = np.where(d_norm > threshold)[0]
    if len(above) < 10:
        return None
    return int(above[0]), int(above[-1])


def rot_filt_filt(signal: np.ndarray, sinarg: np.ndarray, fs: float) -> np.ndarray:
    """Rotating demodulation filter - port of PSrotFiltFilt.m."""
    from scipy.signal import filtfilt, bilinear

    ts = 1 / fs
    wlp = 2 * np.pi * 10
    d_lp = np.sqrt(3) / 2
    # butter2 tustin
    k = 2 / ts
    k2 = k**2
    wn2 = wlp**2
    denom = k2 + 2 * d_lp * wlp * k + wn2
    b0 = wn2 / denom
    b1 = 2 * wn2 / denom
    b2 = wn2 / denom
    a1 = 2 * (wn2 - k2) / denom
    a2 = (k2 - 2 * d_lp * wlp * k + wn2) / denom
    b = [b0, b1, b2]
    a = [1, a1, a2]

    sig = np.asarray(signal, dtype=float).ravel()
    ph = np.exp(1j * np.asarray(sinarg, dtype=float).ravel())

    y_r = sig * ph
    y_q = sig * np.conj(ph)
    y_r = filtfilt(b, a, y_r)
    y_q = filtfilt(b, a, y_q)
    return np.real((y_r * np.conj(ph) + y_q * ph) * 0.5)
