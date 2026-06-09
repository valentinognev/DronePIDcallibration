"""PID statistics and tuning diagnostics - simplified port of PSplotStats.m."""

from __future__ import annotations

import numpy as np

from pidbox.core.spectral import psd_2d


def _rms(arr: np.ndarray) -> float:
    arr = np.asarray(arr, dtype=float)
    if arr.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(arr**2)))


def _mean_abs(arr: np.ndarray) -> float:
    arr = np.asarray(arr, dtype=float)
    if arr.size == 0:
        return 0.0
    return float(np.mean(np.abs(arr)))


def _align_trace(arr: np.ndarray, n: int) -> np.ndarray:
    """Pad missing traces with zeros so PID math matches gyro length."""
    arr = np.asarray(arr, dtype=float)
    if n == 0:
        return arr
    if arr.size == 0:
        return np.zeros(n)
    if arr.size == n:
        return arr
    return arr[:n] if arr.size > n else np.pad(arr, (0, n - arr.size))


def compute_pid_stats(
    gyro: np.ndarray,
    setpoint: np.ndarray,
    pterm: np.ndarray,
    iterm: np.ndarray,
    dterm: np.ndarray,
    fterm: np.ndarray,
    lograte_khz: float,
) -> dict[str, float | dict]:
    """Compute PID balance and noise statistics."""
    gyro = np.asarray(gyro, dtype=float)
    n = gyro.size
    setpoint = _align_trace(setpoint, n)
    pterm = _align_trace(pterm, n)
    iterm = _align_trace(iterm, n)
    dterm = _align_trace(dterm, n)
    fterm = _align_trace(fterm, n)

    if n == 0:
        return {
            "pid_error_rms": 0.0,
            "pid_sum_rms": 0.0,
            "gyro_rms": 0.0,
            "motor_band_power": 0.0,
            "low_band_power": 0.0,
            "term_balance": {"P_pct": 0.0, "I_pct": 0.0, "D_pct": 0.0, "F_pct": 0.0},
            "tracking_error_mean": 0.0,
        }

    pid_err = gyro - setpoint
    pid_sum = pterm + iterm + dterm + fterm

    freqs, gyro_psd = psd_2d(gyro, lograte_khz, psd=True)

    def _band_power(psd: np.ndarray, f: np.ndarray, lo: float, hi: float) -> float:
        mask = (f >= lo) & (f <= hi)
        return float(np.sum(10 ** (psd[mask] / 10))) if np.any(mask) else 0.0

    motor_band = _band_power(gyro_psd, freqs, 80, 500)
    low_band = _band_power(gyro_psd, freqs, 0, 50)

    p_rms = _rms(pterm)
    i_rms = _rms(iterm)
    d_rms = _rms(dterm)
    f_rms = _rms(fterm)
    total = p_rms + i_rms + d_rms + f_rms + 1e-12

    return {
        "pid_error_rms": _rms(pid_err),
        "pid_sum_rms": _rms(pid_sum),
        "gyro_rms": _rms(gyro),
        "motor_band_power": motor_band,
        "low_band_power": low_band,
        "term_balance": {
            "P_pct": 100 * p_rms / total,
            "I_pct": 100 * i_rms / total,
            "D_pct": 100 * d_rms / total,
            "F_pct": 100 * f_rms / total,
        },
        "tracking_error_mean": _mean_abs(pid_err),
    }


def compute_motor_noise(
    motors: list[np.ndarray],
    lograte_khz: float,
) -> dict[str, np.ndarray]:
    """Motor noise spectral comparison."""
    result = {}
    for i, m in enumerate(motors):
        freqs, spec = psd_2d(m, lograte_khz, psd=True)
        result[f"motor_{i}"] = {"freq": freqs.tolist(), "psd": spec.tolist()}
    return result
