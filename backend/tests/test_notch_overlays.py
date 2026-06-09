"""Tests for spectral notch overlay helpers."""

import numpy as np
import pandas as pd
import pytest

from pidbox.core.notch_overlays import (
    build_dyn_notch_overlay_curves,
    build_rpm_overlay_curves,
    describe_overlay_capabilities,
    erpm_to_hz,
    extract_dyn_notch_data,
    extract_erpm_hz_matrix,
    extract_rpm_filter_data,
    merge_overlay_capabilities,
    resolve_rpm_filter_matrix,
    spectral_overlay_freq_axis,
)
from pidbox.core.parsers.base import LoadedLog


def _log(debug_mode: int, fw_major: int = 4) -> LoadedLog:
    return LoadedLog(
        name="t",
        source_path="x",
        dataframe=pd.DataFrame(),
        setup_info=[],
        lograte_khz=4.0,
        fw_type="Betaflight",
        fw_major=fw_major,
        fw_minor=5,
        debug_mode=debug_mode,
        debug_indices={"RPM_FILTER": 46, "FFT_FREQ": 17},
        gyro_debug_axis=0,
        roll_pidf="",
        pitch_pidf="",
        yaw_pidf="",
        default_epoch_start=0.0,
        default_epoch_end=1.0,
    )


def test_extract_rpm_filter_data():
    n = 100
    df = pd.DataFrame({f"debug_{i}_": np.linspace(80 + i * 10, 200 + i * 10, n) for i in range(4)})
    log = _log(46)
    mat = extract_rpm_filter_data(df, log)
    assert mat is not None
    assert mat.shape == (n, 4)


def test_extract_dyn_notch_data_bf4():
    n = 50
    df = pd.DataFrame({f"debug_{i}_": np.full(n, 150.0 + i * 30) for i in range(3)})
    log = _log(17, fw_major=4)
    mat = extract_dyn_notch_data(df, log)
    assert mat is not None
    assert mat.shape[1] == 3


def test_build_rpm_overlay_curves():
    rpm = np.array([[100, 120, 0, 0], [110, 130, 0, 0]])
    freq = np.linspace(0, 500, 100)
    curves = build_rpm_overlay_curves(rpm, freq, motors=[0, 1], harmonics=[1, 2], y_min=-50, y_max=20)
    assert len(curves) == 4
    assert all(len(c["y"]) == 100 for c in curves)


def test_rpm_overlay_linestyle_matches_harmonic_number():
    """Line style must follow harmonic index (PSplotRPMOverlay.m), not list position."""
    rpm = np.array([[100, 0, 0, 0]])
    freq = np.linspace(0, 500, 100)
    curves = build_rpm_overlay_curves(rpm, freq, motors=[0], harmonics=[2, 3], y_min=-50, y_max=20)
    assert curves[0]["harmonic"] == 2
    assert curves[0]["dash"] == "dash"
    assert curves[0]["center_hz"] == pytest.approx(200.0)
    assert curves[1]["harmonic"] == 3
    assert curves[1]["dash"] == "dot"
    assert curves[1]["center_hz"] == pytest.approx(300.0)


def test_rpm_overlay_harmonic_ordering():
    rpm = np.array([[150, 0, 0, 0]])
    freq = np.linspace(0, 1000, 200)
    curves = build_rpm_overlay_curves(rpm, freq, motors=[0], harmonics=[1, 2], y_min=-50, y_max=20)
    assert curves[0]["center_hz"] < curves[1]["center_hz"]


def test_spectral_overlay_freq_axis_extends_for_third_harmonic():
  # 1.6 kHz log: Nyquist 800 Hz, but 3rd harmonic ~1000 Hz should still be drawable.
    rpm = np.array([[1206.0, 0, 0, 0]])
    freq = spectral_overlay_freq_axis(1600.0, rpm, motors=[0], harmonics=[3])
    assert freq[-1] >= 1000.0
    curves = build_rpm_overlay_curves(rpm, freq, motors=[0], harmonics=[3], y_min=-50, y_max=20)
    assert len(curves) == 1
    assert curves[0]["harmonic"] == 3
    assert curves[0]["dash"] == "dot"


def test_erpm_to_hz_12_poles():
    hz = erpm_to_hz(np.array([360.0, 0.0]), motor_poles=12)
    assert hz[0] == pytest.approx(100.0)
    assert np.isnan(hz[1])


def test_extract_erpm_hz_matrix():
    n = 20
    df = pd.DataFrame({f"eRPM_{i}_": np.linspace(100, 500, n) for i in range(4)})
    log = _log(0)
    log.setup_info = [("motor_poles", "12")]
    mat = extract_erpm_hz_matrix(df, log)
    assert mat is not None
    assert mat.shape == (n, 4)


def test_resolve_rpm_prefers_erpm_when_debug_mode_mismatch():
    n = 50
    df = pd.DataFrame(
        {
            **{f"eRPM_{i}_": np.full(n, 360.0) for i in range(4)},
            **{f"debug_{i}_": np.ones(n) for i in range(4)},
        }
    )
    log = _log(61)  # not RPM_FILTER
    log.setup_info = [("motor_poles", "12")]
    mat, source = resolve_rpm_filter_matrix(df, log)
    assert source == "erpm"
    assert mat is not None
    assert mat[0, 0] == pytest.approx(100.0)


def test_resolve_rpm_prefers_estimate_when_enabled():
    n = 50
    # Logged eRPM would yield 100 Hz; estimate path uses motor % × multiplier.
    df = pd.DataFrame(
        {
            **{f"eRPM_{i}_": np.full(n, 360.0) for i in range(4)},
            "motor_0_": np.full(n, 50.0),
            "setpoint_3_": np.linspace(0, 100, n),
        }
    )
    log = _log(61)
    log.setup_info = [("motor_poles", "12")]
    mat_logged, source_logged = resolve_rpm_filter_matrix(df, log, rpm_estimate=False)
    assert source_logged == "erpm"
    assert mat_logged[0, 0] == pytest.approx(100.0)

    mat_est, source_est = resolve_rpm_filter_matrix(df, log, rpm_estimate=True, rpm_multiplier=2.1)
    assert source_est == "estimated"
    assert mat_est is not None
    assert mat_est[0, 0] == pytest.approx(50.0 * 2.1)


def test_describe_overlay_capabilities_missing_dyn():
    n = 50
    df = pd.DataFrame({f"eRPM_{i}_": np.full(n, 360.0) for i in range(4)})
    log = _log(61)
    log.setup_info = [("motor_poles", "12")]
    caps = describe_overlay_capabilities(df, log)
    assert caps["rpm_notch"]["available"] is True
    assert caps["dyn_notch"]["available"] is False
    assert "FFT_FREQ" in caps["dyn_notch"]["message"]


def test_merge_overlay_capabilities_any_file():
    merged = merge_overlay_capabilities(
        [
            {"rpm_notch": {"available": True, "message": "ok"}, "dyn_notch": {"available": False, "message": "no dyn"}},
            {"rpm_notch": {"available": False, "message": "no rpm"}, "dyn_notch": {"available": True, "message": "dyn ok"}},
        ]
    )
    assert merged["rpm_notch"]["available"] is True
    assert merged["dyn_notch"]["available"] is True


def test_build_dyn_notch_overlay_curves():
    notch = np.array([[140, 180, 260], [150, 190, 270]])
    freq = np.linspace(0, 500, 200)
    curves = build_dyn_notch_overlay_curves(notch, freq, [0, 2], y_top=20, fs_hz=8000)
    assert len(curves) == 2
    assert curves[0]["notch"] == 1
