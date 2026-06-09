"""Spectral analysis - ports of PSSpec2d, PSthrSpec, PStimeFreqCalc."""

from __future__ import annotations

import numpy as np

from pidbox.core.smoothing import smooth_by_factor, smooth_lowess


def hann_window(n: int) -> np.ndarray:
    return np.hanning(n)


def psd_2d(y: np.ndarray, f_khz: float, psd: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """
    Port of PSSpec2d.m - manual Hann + FFT PSD/amplitude spectrum.
    f_khz: sample frequency in kHz (same as original F parameter).
    """
    y = np.asarray(y, dtype=float).ravel()
    n = len(y)
    if n == 0:
        return np.array([]), np.array([])
    fs_hz = f_khz * 1000
    freqs = (fs_hz * np.arange(0, n // 2 + 1)) / n

    y_win = y * hann_window(n)
    y_fft = np.fft.fft(y_win)

    if psd:
        psdx = np.abs(y_fft) ** 2 / (fs_hz * n)
        psdx[1:-1] = 2 * psdx[1:-1]
        psdx = psdx[: n // 2 + 1]
        spec = 10 * np.log10(np.maximum(psdx, 1e-30))
    else:
        spec = np.abs(y_fft) / n
        spec = spec[: n // 2 + 1]

    return freqs, spec


def throttle_spectrum(
    x_throttle: np.ndarray,
    y: np.ndarray,
    f_khz: float,
    psd: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Port of PSthrSpec.m - frequency vs throttle heatmap data.
    Returns freq axis (M,) and amp_mat (100, M).
    """
    x = np.asarray(x_throttle, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    tr = 100
    multiplier = 0.3
    wnd = 1
    segment_length = int(f_khz * 1000 * multiplier)

    file_dur_sec = len(x) / (f_khz * 1000)
    if file_dur_sec <= 20:
        subsample_factor = 5
    elif file_dur_sec <= 60:
        subsample_factor = 3
    else:
        subsample_factor = 1
    subsample_factor = max(1, subsample_factor)

    step = max(1, segment_length // subsample_factor)
    segment_vector = np.arange(0, len(y) - segment_length, step)

    tm_list: list[float] = []
    yseg_list: list[np.ndarray] = []
    for i in segment_vector:
        seg_x = x[i : i + segment_length]
        tm_list.append(float(np.nanmean(seg_x)))
        yseg_list.append(y[i : i + segment_length - 1])

    if not yseg_list:
        return np.array([]), np.zeros((tr, segment_length // 2))

    thr_sort_ind = np.argsort(tm_list)
    thr_sort = np.array(tm_list)[thr_sort_ind]
    yseg_sort = [yseg_list[i] for i in thr_sort_ind]

    half = segment_length // 2
    amp_mat = np.zeros((tr, half))
    freq_out = np.zeros((tr, half))

    for i in range(1, tr + 1):
        inds = np.where((thr_sort > i - wnd) & (thr_sort <= i + wnd))[0]
        if len(inds) == 0:
            continue
        tmp_rows = []
        for j in inds:
            ytmp = np.asarray(yseg_sort[j], dtype=float)
            n = len(ytmp)
            fs = (f_khz * 1000) * np.arange(1, n // 2 + 1) / n
            ytmp2 = ytmp * hann_window(n)
            if psd:
                y_fft = np.fft.fft(ytmp2)
                psdx = np.abs(y_fft) ** 2 / (f_khz * 1000 * n)
                psdx[1:-1] = 2 * psdx[1:-1]
                psdx = psdx[: n // 2]
                row = 10 * np.log10(np.maximum(psdx, 1e-30)) + 40
            else:
                y_fft = np.abs(np.fft.fft(ytmp2, n)) / n
                row = y_fft[: n // 2]
            tmp_rows.append(row)
        if tmp_rows:
            amp_mat[i - 1, : len(tmp_rows[0])] = np.nanmean(tmp_rows, axis=0)
            freq_out[i - 1, : len(fs)] = fs

    freq_axis = freq_out[0, :] if np.any(freq_out) else np.arange(half)
    return freq_axis, amp_mat


def time_freq_calc(
    y: np.ndarray,
    f_khz: float,
    smooth_factor: int = 1,
    subsample_factor: int = 1,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Port of PStimeFreqCalc.m - time x frequency spectrogram.
    Returns Tm (time sec), freq, spec_mat (freq x time, flipped).
    """
    y = np.asarray(y, dtype=float).ravel()
    multiplier = 0.3
    segment_length = int(f_khz * 1000 * multiplier)
    half_segment = round(segment_length / 2)

    stepsz = max(1, round(segment_length / subsample_factor))
    smpls = np.arange(0, len(y) - segment_length, stepsz)
    tm = smpls / (f_khz * 1000)

    yseg: list[np.ndarray] = []
    for i in smpls:
        if i < segment_length:
            yseg.append(y[i : i + segment_length])
        else:
            yseg.append(y[i - half_segment : i + half_segment - 1])

    spec_mat = []
    freq = np.array([])
    for seg in yseg:
        seg_arr = np.asarray(seg, dtype=float)
        if len(seg_arr) < segment_length:
            seg_arr = np.pad(seg_arr, (0, segment_length - len(seg_arr)))
        freq, spec = psd_2d(seg_arr, f_khz, psd=True)
        spec = smooth_by_factor(spec, smooth_factor)
        spec_mat.append(spec)

    if not spec_mat:
        return tm, freq, np.zeros((0, 0))

    spec_arr = np.array(spec_mat)
    return tm, freq, np.flipud(spec_arr.T)


def smooth_spectrum(spec: np.ndarray, smooth_factor: int = 1) -> np.ndarray:
    """LOWESS on PSD vs frequency — port of PSplotSpec2D span = log10(n) * factor^3."""
    spec = np.asarray(spec, dtype=float).ravel()
    if smooth_factor < 1 or len(spec) < 3:
        return spec.copy()
    span = int(np.log10(len(spec)) * (smooth_factor**3))
    if span < 1:
        return spec.copy()
    return smooth_lowess(spec, span)


def compute_spectrum_grid(
    signals: dict[str, np.ndarray],
    f_khz: float,
    psd: bool = True,
    sub100hz: bool = False,
    smooth_factor: int = 1,
) -> dict[str, dict[str, np.ndarray]]:
    """Compute full + sub-100Hz spectra for multiple traces."""
    result: dict[str, dict[str, np.ndarray]] = {}
    for name, y in signals.items():
        freqs, spec = psd_2d(y, f_khz, psd=psd)
        spec = smooth_spectrum(spec, smooth_factor)
        entry: dict[str, np.ndarray] = {"freq": freqs, "spec": spec}
        if sub100hz:
            mask = freqs <= 100
            entry["freq_sub"] = freqs[mask]
            entry["spec_sub"] = spec[mask]
        result[name] = entry
    return result
