"""Tests for RPM estimation."""

import numpy as np

from pidbox.core.rpm import estimate_rpm


def test_estimate_rpm():
    freqs = np.linspace(0, 1000, 500)
    amp = np.zeros((100, 500))
    amp[:, 80] = 10  # peak at ~160 Hz
    fund, harm = estimate_rpm(freqs, amp)
    assert len(fund) == 100
    assert harm.shape == (100, 3)
