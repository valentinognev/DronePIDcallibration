"""Average motor noise by harmonic — spectral analyzer motor-noise view."""

from __future__ import annotations

import numpy as np

from pidbox.core.notch_overlays import resolve_rpm_filter_matrix
from pidbox.core.parsers.base import LoadedLog
from pidbox.core.spectral import psd_2d
from pidbox.core.traces import AXIS_NAMES, get_trace


def _segment_fundamental(
    rpm_mat: np.ndarray | None,
    start: int,
    end: int,
    multiplier: float,
    motor_median: float | None,
) -> float | None:
    if rpm_mat is not None:
        seg = rpm_mat[start:end, :]
        flat = seg[seg > 0]
        if flat.size:
            return float(np.nanmedian(flat))
    if motor_median is not None and motor_median > 0:
        return motor_median * multiplier
    return None


def _spec_at_hz(y: np.ndarray, lograte_khz: float, target_hz: float) -> float:
    freqs, spec = psd_2d(y, lograte_khz, psd=True)
    if freqs.size == 0 or not np.isfinite(target_hz):
        return float("nan")
    if target_hz <= freqs[0] or target_hz >= freqs[-1]:
        return float("nan")
    return float(np.interp(target_hz, freqs, spec))


def compute_motor_noise_harmonics(
    df,
    log: LoadedLog,
    *,
    rpm_estimate: bool = False,
    rpm_multiplier: float = 2.1,
) -> dict[str, dict]:
    """
    Average gyro noise at motor harmonics across the log epoch.
    Dotted = gyro prefilt, solid = filtered gyro.
    """
    rpm_mat, _ = resolve_rpm_filter_matrix(
        df,
        log,
        rpm_estimate=rpm_estimate,
        rpm_multiplier=rpm_multiplier,
    )

    motors = []
    for i in range(4):
        m = get_trace(df, f"motor_{i}", None)
        motors.append(np.asarray(m, dtype=float) if m is not None else None)

    fs_hz = log.lograte_khz * 1000
    seg_len = max(int(fs_hz * 0.3), 256)
    step = max(seg_len // 3, 64)

    result: dict[str, dict] = {}
    for axis in range(3):
        gyro = get_trace(df, "gyro", axis)
        gyro_pf = get_trace(df, "gyro_pf", axis)
        if gyro is None or gyro_pf is None:
            continue
        gyro = np.asarray(gyro, dtype=float)
        gyro_pf = np.asarray(gyro_pf, dtype=float)
        n = min(len(gyro), len(gyro_pf))
        if n < seg_len:
            continue

        pre_vals: list[list[float]] = [[], [], []]
        post_vals: list[list[float]] = [[], [], []]

        for start in range(0, n - seg_len, step):
            end = start + seg_len
            motor_med = None
            if motors[0] is not None and len(motors[0]) >= end:
                active = [motors[i][start:end] for i in range(4) if motors[i] is not None]
                if active:
                    stacked = np.nanmean(np.column_stack(active), axis=1)
                    stacked = stacked[stacked > 5]
                    if stacked.size:
                        motor_med = float(np.nanmedian(stacked))

            rpm_slice = rpm_mat[start:end, :] if rpm_mat is not None and rpm_mat.shape[0] >= end else None
            f0 = _segment_fundamental(rpm_slice, 0, seg_len, rpm_multiplier, motor_med)
            if f0 is None or f0 <= 0:
                continue

            for hi, harm in enumerate((1, 2, 3)):
                fh = f0 * harm
                pre = _spec_at_hz(gyro_pf[start:end], log.lograte_khz, fh)
                post = _spec_at_hz(gyro[start:end], log.lograte_khz, fh)
                if np.isfinite(pre):
                    pre_vals[hi].append(pre)
                if np.isfinite(post):
                    post_vals[hi].append(post)

        if not any(pre_vals) and not any(post_vals):
            continue

        def _mean_std(vals: list[list[float]]) -> tuple[list[float], list[float]]:
            means, stds = [], []
            for bucket in vals:
                if bucket:
                    arr = np.asarray(bucket, dtype=float)
                    means.append(float(np.nanmean(arr)))
                    stds.append(float(np.nanstd(arr)) if arr.size > 1 else 0.0)
                else:
                    means.append(float("nan"))
                    stds.append(0.0)
            return means, stds

        pre_mean, pre_std = _mean_std(pre_vals)
        post_mean, post_std = _mean_std(post_vals)
        result[AXIS_NAMES[axis]] = {
            "harmonics": [1, 2, 3],
            "pre_filt": pre_mean,
            "post_filt": post_mean,
            "pre_std": pre_std,
            "post_std": post_std,
        }

    return result
