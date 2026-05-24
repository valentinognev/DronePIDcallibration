"""LOWESS smoothing matching Octave/MATLAB smooth(..., 'lowess')."""

from __future__ import annotations

import numpy as np
from statsmodels.nonparametric.smoothers_lowess import lowess


def smooth_lowess(y: np.ndarray, span: int) -> np.ndarray:
    """Apply LOWESS smoothing with given span (window size)."""
    y = np.asarray(y, dtype=float).ravel()
    if span <= 1 or len(y) < 3:
        return y.copy()
    frac = min(1.0, span / len(y))
    result = lowess(y, np.arange(len(y)), frac=frac, return_sorted=False)
    return np.asarray(result, dtype=float)


SMOOTH_VALS = [1, 20, 40, 60]


def smooth_by_factor(y: np.ndarray, smooth_factor: int) -> np.ndarray:
    """Map smooth factor index (1-4) to LOWESS span."""
    idx = max(0, min(len(SMOOTH_VALS) - 1, smooth_factor - 1))
    return smooth_lowess(y, SMOOTH_VALS[idx])
