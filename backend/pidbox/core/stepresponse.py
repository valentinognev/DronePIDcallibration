"""Step response calculation - port of PSstepcalc.m."""

from __future__ import annotations

import numpy as np

from pidbox.core.smoothing import smooth_by_factor


def step_calc(
    sp: np.ndarray,
    gy: np.ndarray,
    lograte_khz: float,
    y_correction: bool = True,
    smooth_factor: int = 1,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Deconvolve step response using Wiener deconvolution.
    Returns (stepresponse stack n x wnd, time_ms).
    """
    sp = np.asarray(sp, dtype=float).ravel()
    gy = smooth_by_factor(np.asarray(gy, dtype=float).ravel(), smooth_factor)

    min_input = 20
    lograte = lograte_khz
    segment_length = int(lograte * 2000)
    wnd = int(lograte * 1000 * 0.5)
    step_resp_duration_ms = 500
    t = np.arange(0, step_resp_duration_ms + 1 / lograte, 1 / lograte)

    file_dur_sec = len(sp) / (lograte * 1000)
    if file_dur_sec <= 20:
        subsample_factor = 10
    elif file_dur_sec <= 60:
        subsample_factor = 7
    else:
        subsample_factor = 3

    step = max(1, round(segment_length / subsample_factor))
    segment_vector = np.arange(0, len(sp) - segment_length, step)
    n_segs = len([i for i in segment_vector if i + segment_length < segment_vector[-1] + segment_length])

    sp_seg_list = []
    gy_seg_list = []
    for i in segment_vector:
        if i + segment_length > len(sp):
            break
        if np.max(np.abs(sp[i : i + segment_length])) >= min_input:
            sp_seg_list.append(sp[i : i + segment_length])
            gy_seg_list.append(gy[i : i + segment_length])

    if not sp_seg_list:
        return np.zeros((0, wnd + 1)), t[: wnd + 1]

    pad_length = 100
    responses = []
    hann = np.hanning

    for sp_seg, gy_seg in zip(sp_seg_list, gy_seg_list):
        a = gy_seg * hann(len(gy_seg))
        b = sp_seg * hann(len(sp_seg))
        a_fft = np.fft.fft(np.concatenate([np.zeros(pad_length), a, np.zeros(pad_length)]))
        b_fft = np.fft.fft(np.concatenate([np.zeros(pad_length), b, np.zeros(pad_length)]))
        g = a_fft / len(a_fft)
        h = b_fft / len(b_fft)
        h_conj = np.conj(h)
        imp = np.real(np.fft.ifft((g * h_conj) / (h * h_conj + 0.0001)))
        resp = np.cumsum(imp)
        resp_len = min(len(resp), len(t))
        resp = resp[:resp_len]
        t_seg = t[:resp_len]

        steady_window = (t_seg > 200) & (t_seg < step_resp_duration_ms)
        if y_correction and np.any(steady_window):
            steady = resp[steady_window]
            mean_steady = np.nanmean(steady)
            if mean_steady < 1 or mean_steady > 1:
                yoffset = 1 - mean_steady
                resp = resp * (yoffset + 1)

        if np.any(steady_window):
            steady = resp[steady_window]
            if np.min(steady) > 0.5 and np.max(steady) < 3:
                out_len = min(wnd + 1, len(resp))
                responses.append(resp[:out_len])

    if not responses:
        return np.zeros((0, wnd + 1)), t[: wnd + 1]

    return np.array(responses), t[: wnd + 1]


def step_stats(step_responses: np.ndarray, time_ms: np.ndarray) -> dict[str, float]:
    """Compute peak and latency statistics from step response stack."""
    if step_responses.size == 0:
        return {"peak_mean": 0, "peak_std": 0, "latency_mean_ms": 0, "latency_std_ms": 0, "n": 0}

    peaks = np.max(step_responses, axis=1)
    latencies = []
    for row in step_responses:
        above = np.where(row >= 0.5)[0]
        latencies.append(time_ms[above[0]] if len(above) else 0)

    latencies = np.array(latencies)
    return {
        "peak_mean": float(np.mean(peaks)),
        "peak_std": float(np.std(peaks)),
        "latency_mean_ms": float(np.mean(latencies)),
        "latency_std_ms": float(np.std(latencies)),
        "n": len(peaks),
    }
