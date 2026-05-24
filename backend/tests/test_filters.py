"""Tests for filter design."""

import numpy as np

from pidbox.core.filters import bf_filter_coeffs, filter_frequency_response, phase_shift_deg, simulate_filter_chain


def test_pt1_coeffs():
    b, a = bf_filter_coeffs("pt1", 250, 8000)
    assert len(b) == 2
    assert a[0] == 1.0


def test_pt2_correction():
    b, a = bf_filter_coeffs("pt2", 250, 8000)
    assert len(b) == 3


def test_notch_coeffs():
    b, a = bf_filter_coeffs("notch", 200, 8000, q=500)
    assert len(b) == 3


def test_filter_frequency_response():
    b, a = bf_filter_coeffs("pt1", 250, 8000)
    resp = filter_frequency_response(b, a, 8000)
    assert "magnitude" in resp
    assert len(resp["freq_hz"]) > 0


def test_phase_shift_deg():
    assert abs(phase_shift_deg(1.0, 100) - 36) < 1


def test_simulate_filter_chain():
    result = simulate_filter_chain(8000, [250, 500], [(100, 500)])
    assert "total_delay_ms" in result
