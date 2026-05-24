"""Betaflight-compatible filter design - port of PSbfFilters.m."""

from __future__ import annotations

import numpy as np
from scipy import signal


def bf_filter_coeffs(
    ftype: str, fc: float, fs: float, q: float = 1 / np.sqrt(2)
) -> tuple[np.ndarray, np.ndarray]:
    """Design discrete filter matching Betaflight pt1/pt2/pt3/biquad/notch."""
    if fc <= 0 or fc >= fs / 2:
        return np.array([1.0]), np.array([1.0])

    ts = 1 / fs

    ftype = ftype.lower()
    if ftype == "pt1":
        rc = 1 / (2 * np.pi * fc)
        k = ts / (rc + ts)
        b = np.array([k, 0.0])
        a = np.array([1.0, -(1 - k)])

    elif ftype == "pt2":
        fc_corr = fc * 1.553773974
        rc = 1 / (2 * np.pi * fc_corr)
        k = ts / (rc + ts)
        b1, a1 = np.array([k, 0.0]), np.array([1.0, -(1 - k)])
        b = np.convolve(b1, b1)
        a = np.convolve(a1, a1)

    elif ftype == "pt3":
        fc_corr = fc * 1.961459177
        rc = 1 / (2 * np.pi * fc_corr)
        k = ts / (rc + ts)
        b1, a1 = np.array([k, 0.0]), np.array([1.0, -(1 - k)])
        b = np.convolve(np.convolve(b1, b1), b1)
        a = np.convolve(np.convolve(a1, a1), a1)

    elif ftype == "biquad":
        w0 = 2 * np.pi * fc / fs
        alpha = np.sin(w0) / (2 * (1 / np.sqrt(2)))
        b0 = (1 - np.cos(w0)) / 2
        b1 = 1 - np.cos(w0)
        b2 = (1 - np.cos(w0)) / 2
        a0 = 1 + alpha
        b = np.array([b0, b1, b2]) / a0
        a = np.array([1.0, -2 * np.cos(w0) / a0, (1 - alpha) / a0])

    elif ftype == "notch":
        w0 = 2 * np.pi * fc / fs
        alpha = np.sin(w0) / (2 * q)
        a0 = 1 + alpha
        b = np.array([1, -2 * np.cos(w0), 1]) / a0
        a = np.array([1.0, -2 * np.cos(w0) / a0, (1 - alpha) / a0])

    else:
        b, a = np.array([1.0]), np.array([1.0])

    return b, a


def cascade_filters(filters: list[tuple[np.ndarray, np.ndarray]]) -> tuple[np.ndarray, np.ndarray]:
    b_total = np.array([1.0])
    a_total = np.array([1.0])
    for b, a in filters:
        b_total = np.convolve(b_total, b)
        a_total = np.convolve(a_total, a)
    return b_total, a_total


def filter_frequency_response(
    b: np.ndarray,
    a: np.ndarray,
    fs: float,
    n_points: int = 2048,
    log_freq: bool = False,
) -> dict[str, np.ndarray]:
    """Compute magnitude, phase, group delay, and step response."""
    if log_freq:
        freqs = np.logspace(0, np.log10(fs / 2), n_points)
        w, h = signal.freqs(b, a, worN=2 * np.pi * freqs)
    else:
        w, h = signal.freqz(b, a, worN=n_points, fs=fs)
        freqs = w

    magnitude = np.abs(h)
    phase_deg = np.angle(h, deg=True)
    phase_rad = np.unwrap(np.angle(h))
    group_delay = -np.gradient(phase_rad, freqs) / (2 * np.pi)
    group_delay_ms = group_delay * 1000

    # Step response
    t_step = np.arange(0, 0.004, 1 / fs)
    _, step_resp = signal.dstep((b, a, 1), t=t_step)
    step_resp = np.squeeze(step_resp)

    total_delay_ms = float(np.mean(group_delay_ms[: max(1, len(group_delay_ms) // 10)]))

    return {
        "freq_hz": freqs,
        "magnitude": magnitude,
        "magnitude_db": 20 * np.log10(np.maximum(magnitude, 1e-12)),
        "phase_deg": phase_deg,
        "group_delay_ms": group_delay_ms,
        "step_time_ms": t_step * 1000,
        "step_response": step_resp,
        "total_delay_ms": total_delay_ms,
    }


def phase_shift_deg(delay_ms: float, freq_hz: float) -> float:
    """Port of PSphaseShiftDeg.m."""
    period_ms = 1000 / freq_hz
    return delay_ms / period_ms * 360


def simulate_filter_chain(
    looprate_hz: float,
    lpf_cutoffs: list[float],
    notch_configs: list[tuple[float, float]],
    duration_sec: float = 1.0,
    signal_hz_start: float = 0,
    signal_hz_end: float = 1000,
) -> dict:
    """Full filter simulator response for LPF + notch chain."""
    fs = looprate_hz
    filters = []
    lpf_responses = []
    for fc in lpf_cutoffs:
        if fc > 0:
            b, a = bf_filter_coeffs("pt1", fc, fs)
            filters.append((b, a))
            lpf_responses.append(filter_frequency_response(b, a, fs))

    notch_responses = []
    for fc, q in notch_configs:
        if fc > 0:
            b, a = bf_filter_coeffs("notch", fc, fs, q=q)
            filters.append((b, a))
            notch_responses.append(filter_frequency_response(b, a, fs))

    b_total, a_total = cascade_filters(filters) if filters else (np.array([1.0]), np.array([1.0]))
    combined = filter_frequency_response(b_total, a_total, fs)

    return {
        "lpf": lpf_responses,
        "notch": notch_responses,
        "combined": combined,
        "total_delay_ms": combined["total_delay_ms"],
    }
