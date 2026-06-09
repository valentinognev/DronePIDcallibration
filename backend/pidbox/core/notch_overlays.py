"""RPM / dynamic-notch overlay helpers for spectral analyzer."""

from __future__ import annotations

import numpy as np

from pidbox.core.filters import bf_filter_coeffs, filter_frequency_response
from pidbox.core.parsers.base import LoadedLog
from pidbox.core.rpm import estimate_rpm
from pidbox.core.spectral import throttle_spectrum
from pidbox.core.traces import get_trace

RPM_HARMONIC_MODES: dict[str, list[int]] = {
    "off": [],
    "1": [1],
    "2": [2],
    "3": [3],
    "1,2": [1, 2],
    "1,3": [1, 3],
    "2,3": [2, 3],
    "1,2,3": [1, 2, 3],
}

DYN_NOTCH_MODES: dict[str, list[int]] = {
    "off": [],
    "1": [0],
    "2": [1],
    "3": [2],
    "4": [3],
    "5": [4],
    "6": [5],
    "7": [6],
    "all": [0, 1, 2, 3, 4, 5, 6],
}

HARMONIC_LINE_STYLES = ("solid", "dash", "dot")
MOTOR_COLORS = ("#e60000", "#ff9900", "#0099ff", "#00cccc")
DYN_NOTCH_COLORS = ("#00ffff", "#ffffff", "#ff00ff", "#ff8800", "#88ff00", "#0088ff", "#ff0088")
# Full-spectrum panel shows 0–1000 Hz; 3rd harmonics often sit just above Nyquist on 1.6 kHz logs.
SPECTRAL_OVERLAY_FREQ_MIN_HZ = 1000.0


def spectral_overlay_freq_axis(
    fs_hz: float,
    rpm_mat: np.ndarray | None = None,
    motors: list[int] | None = None,
    harmonics: list[int] | None = None,
    n_pts: int = 512,
) -> np.ndarray:
    """Frequency grid for 1D spectral overlays (RPM + dyn notch)."""
    f_max = fs_hz / 2
    if rpm_mat is not None and motors and harmonics:
        peak_harm = max(harmonics)
        for mi in motors:
            if mi < 0 or mi >= rpm_mat.shape[1]:
                continue
            col = rpm_mat[:, mi]
            col = col[col > 0]
            if col.size:
                f_max = max(f_max, float(np.nanmedian(col)) * peak_harm * 1.08)
    f_max = max(f_max, SPECTRAL_OVERLAY_FREQ_MIN_HZ)
    return np.linspace(0, f_max, n_pts)


def _debug_col(df, idx: int) -> np.ndarray | None:
    name = f"debug_{idx}_"
    if name not in df.columns:
        return None
    return np.asarray(df[name], dtype=float)


def _motor_poles_from_log(log: LoadedLog) -> int:
    for key, value in log.setup_info:
        if key.strip() == "motor_poles":
            try:
                poles = int(value)
                if poles > 0:
                    return poles
            except ValueError:
                pass
    return 12


def erpm_to_hz(erpm: np.ndarray, motor_poles: int) -> np.ndarray:
    """Betaflight eRPM → mechanical frequency (Hz)."""
    if motor_poles <= 0:
        motor_poles = 12
    scale = motor_poles * 60.0 / 200.0
    out = np.asarray(erpm, dtype=float).copy()
    return np.where(out > 0, out / scale, np.nan)


def extract_rpm_filter_data(df, log: LoadedLog) -> np.ndarray | None:
    """Nx4 motor fundamental Hz from RPM_FILTER debug mode."""
    rpm_mode = log.debug_indices.get("RPM_FILTER", 46)
    if log.debug_mode != rpm_mode:
        return None
    cols = []
    for i in range(4):
        col = _debug_col(df, i)
        if col is None:
            return None
        cols.append(col)
    return np.column_stack(cols)


def extract_erpm_hz_matrix(df, log: LoadedLog) -> np.ndarray | None:
    """Nx4 motor fundamental Hz from DShot/eRPM telemetry columns."""
    poles = _motor_poles_from_log(log)
    cols: list[np.ndarray] = []
    for i in range(4):
        name = f"eRPM_{i}_"
        if name not in df.columns:
            continue
        erpm = np.asarray(df[name], dtype=float)
        if np.nanmax(erpm) < 5:
            continue
        cols.append(erpm_to_hz(erpm, poles))
    if not cols:
        return None
    n = len(cols[0])
    mat = np.full((n, 4), np.nan)
    for i, col in enumerate(cols):
        mat[:, i] = col
    return mat


def resolve_rpm_filter_matrix(
    df,
    log: LoadedLog,
    *,
    rpm_estimate: bool = False,
    rpm_multiplier: float = 2.1,
) -> tuple[np.ndarray | None, str]:
    """
    Resolve per-motor fundamental Hz for notch overlays.
    When rpm_estimate is set: motor-spectrum estimate (ignores logged RPM channels).
    Otherwise: RPM_FILTER debug → eRPM telemetry.
    """
    if rpm_estimate:
        rpm_mat = estimate_rpm_filter_from_motors(df, log, rpm_multiplier)
        return (rpm_mat, "estimated") if rpm_mat is not None else (None, "none")

    rpm_mat = extract_rpm_filter_data(df, log)
    if rpm_mat is not None:
        return rpm_mat, "rpm_filter_debug"

    rpm_mat = extract_erpm_hz_matrix(df, log)
    if rpm_mat is not None:
        return rpm_mat, "erpm"

    return None, "none"


def describe_overlay_capabilities(
    df,
    log: LoadedLog,
    *,
    rpm_estimate: bool = False,
    rpm_multiplier: float = 2.1,
) -> dict:
    """Report whether RPM / dyn-notch overlay data exists for a log."""
    fft_mode = log.debug_indices.get("FFT_FREQ", 17)
    dyn_mat = extract_dyn_notch_data(df, log)
    if dyn_mat is not None:
        n_notch = dyn_mat.shape[1]
        dyn_msg = ""
        if log.fw_type == "Betaflight" and log.fw_major >= 2025 and n_notch < 7:
            dyn_msg = f" ({n_notch} dynamic notch(es) in log — BF 2025+ logs DN1–DN{n_notch})"
        dyn = {"available": True, "message": f"Dynamic notch overlays from FFT_FREQ debug.{dyn_msg}"}
    else:
        dyn = {
            "available": False,
            "message": (
                f"No dynamic notch data: blackbox debug_mode is {log.debug_mode} "
                f"(need FFT_FREQ = {fft_mode}). Re-record with debug mode FFT_FREQ."
            ),
        }

    rpm_mat, rpm_source = resolve_rpm_filter_matrix(
        df,
        log,
        rpm_estimate=rpm_estimate,
        rpm_multiplier=rpm_multiplier,
    )
    if rpm_mat is not None:
        source_labels = {
            "rpm_filter_debug": "RPM_FILTER debug",
            "erpm": "eRPM telemetry",
            "estimated": "RPM estimate from motor output",
        }
        rpm = {
            "available": True,
            "message": f"RPM notch overlays from {source_labels.get(rpm_source, rpm_source)}.",
        }
    elif rpm_estimate:
        rpm = {
            "available": False,
            "message": (
                "RPM est. is on but motor/throttle data is missing — cannot estimate fundamentals."
            ),
        }
    else:
        rpm = {
            "available": False,
            "message": (
                "No RPM notch data in log (need RPM_FILTER debug or eRPM telemetry). "
                "Enable RPM est. to estimate from motor output."
            ),
        }

    return {"rpm_notch": rpm, "dyn_notch": dyn}


def merge_overlay_capabilities(per_file: list[dict]) -> dict:
    """Combine per-file overlay capability into one UI state (any file may enable)."""
    if not per_file:
        return {
            "rpm_notch": {"available": False, "message": "Load a log file first."},
            "dyn_notch": {"available": False, "message": "Load a log file first."},
        }

    def _merge(key: str) -> dict:
        available = any(f[key]["available"] for f in per_file)
        if available:
            return {"available": True, "message": per_file[0][key]["message"]}
        messages = list(dict.fromkeys(f[key]["message"] for f in per_file if f[key]["message"]))
        return {"available": False, "message": messages[0] if len(messages) == 1 else messages[0]}

    return {
        "rpm_notch": _merge("rpm_notch"),
        "dyn_notch": _merge("dyn_notch"),
    }


def extract_dyn_notch_data(df, log: LoadedLog) -> np.ndarray | None:
    """NxM dynamic notch center frequencies from FFT_FREQ debug mode."""
    fft_mode = log.debug_indices.get("FFT_FREQ", 17)
    if log.debug_mode != fft_mode:
        return None
    if log.fw_type == "Betaflight" and log.fw_major >= 2025:
        indices = list(range(1, 8))
    else:
        indices = list(range(7))
    cols = []
    for i in indices:
        col = _debug_col(df, i)
        if col is None:
            break
        cols.append(col)
    if not cols:
        return None
    return np.column_stack(cols)


def _motor_command_series(df, motor_idx: int) -> np.ndarray | None:
    """Motor output % — use commanded motor columns, not eRPM telemetry."""
    name = f"motor_{motor_idx}_"
    if name not in df.columns:
        return None
    return np.asarray(df[name], dtype=float)


def estimate_rpm_filter_from_motors(
    df,
    log: LoadedLog,
    multiplier: float,
) -> np.ndarray | None:
    """Estimate per-motor fundamental Hz using motor spectra and multiplier."""
    throttle = get_trace(df, "throttle", None)
    if throttle is None:
        return None

    motors: list[np.ndarray] = []
    for i in range(4):
        m = _motor_command_series(df, i)
        if m is not None:
            motors.append(m)
    if not motors:
        return None

    n = len(throttle)
    out = np.full((n, 4), np.nan)
    for mi, m in enumerate(motors):
        if mi >= 4:
            break
        freq, amp_mat = throttle_spectrum(throttle, m, log.lograte_khz, psd=True)
        if freq.size == 0:
            active = m > 5
            if np.any(active):
                out[active, mi] = np.nanmedian(m[active]) * multiplier
            continue
        fund, _ = estimate_rpm(freq, amp_mat, n_harmonics=1)
        valid = ~np.isnan(fund) & (fund > 0)
        if not np.any(valid):
            active = m > 5
            if np.any(active):
                out[active, mi] = np.nanmedian(m[active]) * multiplier
            continue
        # Map throttle bins back to samples via mean throttle per bin
        thr_pct = np.clip(np.asarray(throttle, dtype=float), 0, 100)
        for si in range(len(m)):
            bin_idx = int(round(thr_pct[si])) - 1
            bin_idx = min(max(bin_idx, 0), 99)
            if valid[bin_idx]:
                out[si, mi] = fund[bin_idx] * multiplier

    if np.all(np.isnan(out)):
        return None
    return out


def _rpm_envelope(freq: np.ndarray, center: float, y_min: float, y_max: float) -> np.ndarray:
    width = max(center * 0.12, 8.0)
    x = (freq - center) / width
    return y_min + (y_max - y_min) / (1.0 + np.exp(-x))


def _interp_db(freq: np.ndarray, spec_db: np.ndarray, target_hz: float) -> float:
    if target_hz <= freq[0] or target_hz >= freq[-1]:
        return float("nan")
    return float(np.interp(target_hz, freq, spec_db))


def build_rpm_overlay_curves(
    rpm_mat: np.ndarray,
    freq_axis: np.ndarray,
    motors: list[int],
    harmonics: list[int],
    y_min: float,
    y_max: float,
) -> list[dict]:
    """Sigmoid envelopes at median harmonic frequency per motor."""
    if rpm_mat.size == 0 or not harmonics or not motors:
        return []

    curves: list[dict] = []
    freq = np.asarray(freq_axis, dtype=float)
    for mi in motors:
        if mi < 0 or mi >= rpm_mat.shape[1]:
            continue
        col = rpm_mat[:, mi]
        col = col[col > 0]
        if col.size == 0:
            continue
        f0 = float(np.nanmedian(col))
        for harm in harmonics:
            center = f0 * harm
            if center <= 0 or center > freq[-1]:
                continue
            curves.append(
                {
                    "motor": mi,
                    "harmonic": harm,
                    "center_hz": center,
                    "freq": freq.tolist(),
                    "y": _rpm_envelope(freq, center, y_min, y_max).tolist(),
                    "color": MOTOR_COLORS[mi % len(MOTOR_COLORS)],
                    "dash": HARMONIC_LINE_STYLES[
                        min(harm - 1, len(HARMONIC_LINE_STYLES) - 1)
                    ],
                }
            )
    return curves


def build_dyn_notch_overlay_curves(
    notch_mat: np.ndarray,
    freq_axis: np.ndarray,
    notch_indices: list[int],
    y_top: float,
    fs_hz: float,
    q: float = 500.0,
) -> list[dict]:
    """Notch filter magnitude dips centered at median dyn-notch frequencies."""
    if notch_mat.size == 0 or not notch_indices:
        return []

    curves: list[dict] = []
    freq = np.asarray(freq_axis, dtype=float)
    for ni in notch_indices:
        if ni < 0 or ni >= notch_mat.shape[1]:
            continue
        col = notch_mat[:, ni]
        col = col[(col > 0) & np.isfinite(col)]
        if col.size == 0:
            continue
        fc = float(np.nanmedian(col))
        if fc <= 0 or fc >= freq[-1]:
            continue
        b, a = bf_filter_coeffs("notch", fc, fs_hz, q=q)
        resp = filter_frequency_response(b, a, fs_hz, n_points=len(freq))
        rf = resp["freq_hz"]
        db = resp["magnitude_db"]
        y = y_top + np.interp(freq, rf, db, left=y_top, right=y_top)
        curves.append(
            {
                "notch": ni + 1,
                "freq": freq.tolist(),
                "y": y.tolist(),
                "color": DYN_NOTCH_COLORS[ni % len(DYN_NOTCH_COLORS)],
            }
        )
    return curves
