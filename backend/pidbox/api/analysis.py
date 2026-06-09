"""Analysis API routes."""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, HTTPException

from pidbox.api.schemas import (
    ChirpRequest,
    FilterSimRequest,
    OverlayCapabilitiesRequest,
    SetupInfoRequest,
    SpectrumRequest,
    StatsRequest,
    StepResponseRequest,
    ThrottleSpectrumRequest,
    TimeFreqRequest,
)
from pidbox.core.chirp import estimate_freq_response, find_chirp_window
from pidbox.core.filters import simulate_filter_chain
from pidbox.core.parsers.common import slice_epoch
from pidbox.core.motor_noise_harmonics import compute_motor_noise_harmonics
from pidbox.core.notch_overlays import (
    DYN_NOTCH_MODES,
    RPM_HARMONIC_MODES,
    build_dyn_notch_overlay_curves,
    build_rpm_overlay_curves,
    describe_overlay_capabilities,
    extract_dyn_notch_data,
    merge_overlay_capabilities,
    resolve_rpm_filter_matrix,
    spectral_overlay_freq_axis,
)
from pidbox.core.rpm import estimate_rpm
from pidbox.core.spectral import compute_spectrum_grid, psd_2d, throttle_spectrum, time_freq_calc
from pidbox.core.stats import compute_motor_noise, compute_pid_stats
from pidbox.core.stepresponse import step_calc, step_stats
from pidbox.core.traces import AXIS_NAMES, get_trace
from pidbox.session import session_manager

router = APIRouter()

STEP_SIGNAL_PAIRS: dict[str, tuple[str | None, str]] = {
    "rate": ("setpoint", "gyro"),
    "attitude": ("attitude_sp", "attitude"),
    "velocity": ("velocity_sp", "velocity"),
    # Accel: excitation from velocity-setpoint steps (no direct accel SP in logs).
    "accel": ("velocity_sp", "accel"),
}

# Minimum setpoint excursion per 2 s window; None = auto from signal scale in step_calc.
STEP_SIGNAL_MIN_INPUT: dict[str, float | None] = {
    "rate": 20.0,
    "attitude": 5.0,
    "velocity": 0.5,
    "accel": 0.25,
}


def _get_epoched_log(session_id: str, file_idx: int, log_idx: int, epoch_start, epoch_end):
    session = session_manager.get(session_id)
    log = session_manager.get_log(session_id, file_idx, log_idx)
    sf = session.files[file_idx]
    es = epoch_start if epoch_start is not None else sf.epoch_start[log_idx]
    ee = epoch_end if epoch_end is not None else sf.epoch_end[log_idx]
    df = slice_epoch(log.dataframe, es, ee)
    return log, df, es, ee


def _to_json(obj):
    """Convert numpy arrays and non-JSON floats in nested dicts for serialization."""
    import math

    import numpy as np

    if isinstance(obj, np.ndarray):
        if obj.ndim == 0:
            return _to_json(obj.item())
        return [_to_json(v) for v in obj.tolist()]
    if isinstance(obj, dict):
        return {k: _to_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_json(v) for v in obj]
    if isinstance(obj, (np.floating, np.integer)):
        obj = obj.item()
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
    return obj


def _trace_or_empty(df, trace_key: str, axis: int = 0):
    y = get_trace(df, trace_key, axis)
    return y if y is not None else []


def _empty_step_result() -> dict:
    return {
        "time_ms": [],
        "curves": [],
        "mean_curve": [],
        "stats": step_stats(np.zeros((0, 0)), np.array([])),
    }


def _step_axis_result(
    df,
    log,
    axis: int,
    signal: str,
    smooth_factor: int,
    y_correction: bool,
) -> dict:
    sp_key, meas_key = STEP_SIGNAL_PAIRS[signal]
    meas = get_trace(df, meas_key, axis)
    if meas is None:
        return _empty_step_result()

    if sp_key is None:
        sp = np.zeros(len(meas), dtype=float)
    else:
        sp = get_trace(df, sp_key, axis)
        if sp is None:
            return _empty_step_result()

    sp = np.asarray(sp, dtype=float)
    min_input = STEP_SIGNAL_MIN_INPUT.get(signal)
    responses, time_ms = step_calc(
        sp, meas, log.lograte_khz, y_correction, smooth_factor, min_input=min_input
    )
    mean_curve = responses.mean(axis=0).tolist() if len(responses) else []
    result = {
        "time_ms": time_ms.tolist(),
        "curves": responses.tolist(),
        "mean_curve": mean_curve,
        "stats": step_stats(responses, time_ms),
    }
    if signal == "rate":
        result["pidf"] = [log.roll_pidf, log.pitch_pidf, log.yaw_pidf][axis]
    return result


@router.post("/overlay-capabilities")
def overlay_capabilities(req: OverlayCapabilitiesRequest):
    try:
        per_file = []
        for file_idx in req.file_indices:
            log, df, _, _ = _get_epoched_log(
                req.session_id, file_idx, req.log_idx, req.epoch_start, req.epoch_end
            )
            per_file.append(
                describe_overlay_capabilities(
                    df,
                    log,
                    rpm_estimate=req.rpm_estimate,
                    rpm_multiplier=req.rpm_multiplier,
                )
            )
        return merge_overlay_capabilities(per_file)
    except KeyError:
        raise HTTPException(404, "Session not found")


@router.post("/spectrum")
def run_spectrum(req: SpectrumRequest):
    try:
        results = []
        for file_idx in req.file_indices:
            log, df, _, _ = _get_epoched_log(
                req.session_id, file_idx, req.log_idx, req.epoch_start, req.epoch_end
            )
            file_result: dict = {"file_idx": file_idx, "name": log.name, "axes": {}}
            for axis in req.axes:
                signals = {}
                for trace in req.traces:
                    y = get_trace(df, trace, axis)
                    if y is not None:
                        signals[trace] = y
                if signals:
                    file_result["axes"][AXIS_NAMES[axis]] = compute_spectrum_grid(
                        signals,
                        log.lograte_khz,
                        psd=req.psd,
                        sub100hz=req.sub100hz,
                        smooth_factor=req.smooth_factor,
                    )

            fs_hz = log.lograte_khz * 1000
            y_min = -50.0 if req.psd else 0.0
            y_max = 20.0 if req.psd else 0.5

            rpm_mat, rpm_source = resolve_rpm_filter_matrix(
                df,
                log,
                rpm_estimate=req.rpm_estimate,
                rpm_multiplier=req.rpm_multiplier,
            )

            rpm_harmonics = RPM_HARMONIC_MODES.get(req.rpm_notch_mode, [])
            freq_axis = spectral_overlay_freq_axis(
                fs_hz,
                rpm_mat,
                req.rpm_motors,
                rpm_harmonics,
            )
            if rpm_mat is not None and rpm_harmonics and req.rpm_motors:
                file_result["rpm_overlays"] = build_rpm_overlay_curves(
                    rpm_mat,
                    freq_axis,
                    req.rpm_motors,
                    rpm_harmonics,
                    y_min,
                    y_max,
                )
            else:
                file_result["rpm_overlays"] = []

            notch_mat = extract_dyn_notch_data(df, log)
            dyn_indices = DYN_NOTCH_MODES.get(req.dyn_notch_mode, [])
            if notch_mat is not None and dyn_indices:
                file_result["dyn_overlays"] = build_dyn_notch_overlay_curves(
                    notch_mat,
                    freq_axis,
                    dyn_indices,
                    y_max,
                    fs_hz,
                )
            else:
                file_result["dyn_overlays"] = []

            file_result["overlay_meta"] = {
                "rpm_source": rpm_source,
                "rpm_from_log": rpm_source == "rpm_filter_debug",
                "has_dyn_notch": notch_mat is not None,
                "debug_mode": log.debug_mode,
                "fft_freq_debug_mode": log.debug_indices.get("FFT_FREQ", 17),
                "dyn_overlay_count": len(file_result["dyn_overlays"]),
            }

            if req.include_motor_noise:
                file_result["motor_noise"] = compute_motor_noise_harmonics(
                    df,
                    log,
                    rpm_estimate=req.rpm_estimate,
                    rpm_multiplier=req.rpm_multiplier,
                )
            else:
                file_result["motor_noise"] = {}

            results.append(file_result)
    except KeyError:
        raise HTTPException(404, "Session not found")
    except IndexError:
        raise HTTPException(404, "File or log not found")
    return _to_json({"results": results})


@router.post("/step-response")
def run_step_response(req: StepResponseRequest):
    unknown = [s for s in req.signals if s not in STEP_SIGNAL_PAIRS]
    if unknown:
        raise HTTPException(400, f"Unknown step-response signals: {unknown}")

    try:
        results = []
        for file_idx in req.file_indices:
            log, df, _, _ = _get_epoched_log(
                req.session_id, file_idx, req.log_idx, req.epoch_start, req.epoch_end
            )
            signals_data: dict[str, dict] = {}
            for signal in req.signals:
                axis_data = {}
                for axis in req.axes:
                    axis_data[AXIS_NAMES[axis]] = _step_axis_result(
                        df, log, axis, signal, req.smooth_factor, req.y_correction
                    )
                signals_data[signal] = axis_data

            file_result: dict = {"file_idx": file_idx, "name": log.name}
            if req.signals == ["rate"]:
                file_result["axes"] = signals_data["rate"]
            else:
                file_result["signals"] = signals_data
                if "rate" in req.signals:
                    file_result["axes"] = signals_data["rate"]
            results.append(file_result)
    except KeyError:
        raise HTTPException(404, "Session not found")
    return {"results": results}


@router.post("/throttle-spectrum")
def run_throttle_spectrum(req: ThrottleSpectrumRequest):
    try:
        log, df, _, _ = _get_epoched_log(
            req.session_id, req.file_idx, req.log_idx, req.epoch_start, req.epoch_end
        )
        throttle = get_trace(df, "throttle", None)
        y = get_trace(df, req.trace, req.axis)
        if throttle is None or y is None:
            raise HTTPException(400, "Required traces not found")

        freq, amp_mat = throttle_spectrum(throttle, y, log.lograte_khz, psd=req.psd)
        fund, harmonics = estimate_rpm(freq, amp_mat)
    except KeyError:
        raise HTTPException(404, "Session not found")

    return _to_json(
        {
            "freq_hz": freq.tolist(),
            "amp_matrix": amp_mat.tolist(),
            "throttle_bins": list(range(1, 101)),
            "rpm_fundamental": fund.tolist(),
            "rpm_harmonics": harmonics.tolist(),
        }
    )


@router.post("/time-freq")
def run_time_freq(req: TimeFreqRequest):
    try:
        log, df, _, _ = _get_epoched_log(
            req.session_id, req.file_idx, req.log_idx, req.epoch_start, req.epoch_end
        )
        y = get_trace(df, req.trace, req.axis)
        if y is None:
            raise HTTPException(400, "Trace not found")
        tm, freq, spec_mat = time_freq_calc(
            y, log.lograte_khz, req.smooth_factor, req.subsample_factor
        )
    except KeyError:
        raise HTTPException(404, "Session not found")

    return {
        "time_sec": tm.tolist(),
        "freq_hz": freq.tolist(),
        "spec_matrix": spec_mat.tolist(),
    }


@router.post("/filter-sim")
def run_filter_sim(req: FilterSimRequest):
    notch = [(n[0], n[1]) for n in req.notch_configs if len(n) >= 2]
    result = simulate_filter_chain(req.looprate_hz, req.lpf_cutoffs, notch)
    return _to_json(
        {
            "lpf": result["lpf"],
            "notch": result["notch"],
            "combined": result["combined"],
            "total_delay_ms": result["total_delay_ms"],
        }
    )


@router.post("/stats")
def run_stats(req: StatsRequest):
    try:
        log, df, _, _ = _get_epoched_log(
            req.session_id, req.file_idx, req.log_idx, req.epoch_start, req.epoch_end
        )
        ax = req.axis
        stats = compute_pid_stats(
            _trace_or_empty(df, "gyro", ax),
            _trace_or_empty(df, "setpoint", ax),
            _trace_or_empty(df, "pterm", ax),
            _trace_or_empty(df, "iterm", ax),
            _trace_or_empty(df, "dterm", ax),
            _trace_or_empty(df, "fterm", ax),
            log.lograte_khz,
        )
        motors = []
        for i in range(4):
            m = get_trace(df, f"motor_{i}", i)
            if m is not None:
                motors.append(m)
        motor_noise = compute_motor_noise(motors, log.lograte_khz) if motors else {}
    except KeyError:
        raise HTTPException(404, "Session not found")

    return _to_json({"stats": stats, "motor_noise": motor_noise})


@router.post("/chirp")
def run_chirp(req: ChirpRequest):
    try:
        log, df, _, _ = _get_epoched_log(req.session_id, req.file_idx, req.log_idx, None, None)
        fs = log.lograte_khz * 1000
        debug0 = df.get("debug_0_", None)
        if debug0 is None:
            raise HTTPException(400, "No chirp debug data")
        window = find_chirp_window(debug0.values, fs)
        inp = get_trace(df, "setpoint", req.axis)
        out = get_trace(df, "gyro", req.axis)
        if inp is None or out is None:
            raise HTTPException(400, "Missing setpoint/gyro")
        if window:
            inp, out = inp[window[0] : window[1]], out[window[0] : window[1]]
        g, c, freq = estimate_freq_response(inp, out, fs)
    except KeyError:
        raise HTTPException(404, "Session not found")

    return {
        "freq_hz": freq.tolist(),
        "magnitude_db": (20 * __import__("numpy").log10(__import__("numpy").abs(g) + 1e-12)).tolist(),
        "coherence": c.tolist(),
        "phase_deg": __import__("numpy").angle(g, deg=True).tolist(),
    }


@router.post("/setup-diff")
def setup_diff(req: SetupInfoRequest):
    try:
        log_a = session_manager.get_log(req.session_id, req.file_idx_a, req.log_idx_a)
        log_b = session_manager.get_log(req.session_id, req.file_idx_b, req.log_idx_b)
    except KeyError:
        raise HTTPException(404, "Session not found")
    except IndexError:
        raise HTTPException(404, "File not found")

    map_a = dict(log_a.setup_info)
    map_b = dict(log_b.setup_info)
    all_keys = sorted(set(map_a) | set(map_b))

    rows = []
    for i, key in enumerate(all_keys, 1):
        va = map_a.get(key, "")
        vb = map_b.get(key, "")
        diff = va != vb
        if req.differences_only and not diff:
            continue
        rows.append({"line": i, "key": key, "value_a": va, "value_b": vb, "diff": diff})

    return {
        "file_a": log_a.name,
        "file_b": log_b.name,
        "rows": rows,
    }
