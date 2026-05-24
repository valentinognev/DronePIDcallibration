"""RPM estimation from throttle-binned spectra - port of PSestimateRPM.m."""

from __future__ import annotations

import numpy as np

from pidbox.core.smoothing import smooth_lowess


def estimate_rpm(
    freq_axis: np.ndarray,
    amp_matrix: np.ndarray,
    n_harmonics: int = 3,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Estimate motor fundamental frequency per throttle bin.
    Returns fund_freq (100,) and harmonics (100, n_harmonics).
    """
    n_bins = amp_matrix.shape[0]
    fund_freq = np.full(n_bins, np.nan)
    f_lo, f_hi = 80, 500
    f_mask = (freq_axis >= f_lo) & (freq_axis <= f_hi)
    f_idx = np.where(f_mask)[0]

    if len(f_idx) == 0:
        return fund_freq, np.full((n_bins, n_harmonics), np.nan)

    for t in range(n_bins):
        spec = amp_matrix[t, :]
        if np.all(spec == 0):
            continue

        band = spec[f_idx]
        noise_floor = np.median(band)
        threshold = noise_floor + (np.max(band) - noise_floor) * 0.3

        pk_idx = []
        pk_val = []
        for j in range(1, len(band) - 1):
            if band[j] > band[j - 1] and band[j] > band[j + 1] and band[j] > threshold:
                pk_idx.append(j)
                pk_val.append(band[j])

        if not pk_idx:
            continue

        si = np.argsort(pk_val)[::-1]
        f0 = freq_axis[f_idx[pk_idx[si[0]]]]

        f2mask = (freq_axis >= f0 * 1.8) & (freq_axis <= f0 * 2.2)
        if np.any(f2mask) and np.max(spec[f2mask]) > noise_floor * 1.5:
            fund_freq[t] = f0
        else:
            fhmask = (freq_axis >= f0 * 0.4) & (freq_axis <= f0 * 0.6) & f_mask
            if np.any(fhmask) and np.max(spec[fhmask]) > noise_floor * 1.3:
                fund_freq[t] = f0 / 2
            else:
                fund_freq[t] = f0

    valid = ~np.isnan(fund_freq)
    if np.sum(valid) > 5:
        fund_freq[valid] = smooth_lowess(fund_freq[valid], 5)

    harmonics = np.outer(fund_freq, np.arange(1, n_harmonics + 1))
    return fund_freq, harmonics
