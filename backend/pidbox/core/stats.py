"""PID statistics and tuning diagnostics - simplified port of PSplotStats.m."""

from __future__ import annotations

import numpy as np

from pidbox.core.spectral import psd_2d


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
    setpoint = np.asarray(setpoint, dtype=float)
    pterm = np.asarray(pterm, dtype=float)
    iterm = np.asarray(iterm, dtype=float)
    dterm = np.asarray(dterm, dtype=float)
    fterm = np.asarray(fterm, dtype=float)

    pid_err = gyro - setpoint
    pid_sum = pterm + iterm + dterm + fterm

    freqs, gyro_psd = psd_2d(gyro, lograte_khz, psd=True)

    def _band_power(psd: np.ndarray, f: np.ndarray, lo: float, hi: float) -> float:
        mask = (f >= lo) & (f <= hi)
        return float(np.sum(10 ** (psd[mask] / 10))) if np.any(mask) else 0.0

    motor_band = _band_power(gyro_psd, freqs, 80, 500)
    low_band = _band_power(gyro_psd, freqs, 0, 50)

    p_rms = float(np.sqrt(np.mean(pterm**2)))
    i_rms = float(np.sqrt(np.mean(iterm**2)))
    d_rms = float(np.sqrt(np.mean(dterm**2)))
    f_rms = float(np.sqrt(np.mean(fterm**2)))
    total = p_rms + i_rms + d_rms + f_rms + 1e-12

    return {
        "pid_error_rms": float(np.sqrt(np.mean(pid_err**2))),
        "pid_sum_rms": float(np.sqrt(np.mean(pid_sum**2))),
        "gyro_rms": float(np.sqrt(np.mean(gyro**2))),
        "motor_band_power": motor_band,
        "low_band_power": low_band,
        "term_balance": {
            "P_pct": 100 * p_rms / total,
            "I_pct": 100 * i_rms / total,
            "D_pct": 100 * d_rms / total,
            "F_pct": 100 * f_rms / total,
        },
        "tracking_error_mean": float(np.mean(np.abs(pid_err))),
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
