"""Analysis API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from pidbox.api.schemas import (
    ChirpRequest,
    FilterSimRequest,
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
from pidbox.core.rpm import estimate_rpm
from pidbox.core.spectral import compute_spectrum_grid, psd_2d, throttle_spectrum, time_freq_calc
from pidbox.core.stats import compute_motor_noise, compute_pid_stats
from pidbox.core.stepresponse import step_calc, step_stats
from pidbox.core.traces import AXIS_NAMES, get_trace
from pidbox.session import session_manager

router = APIRouter()


def _get_epoched_log(session_id: str, file_idx: int, log_idx: int, epoch_start, epoch_end):
    session = session_manager.get(session_id)
    log = session_manager.get_log(session_id, file_idx, log_idx)
    sf = session.files[file_idx]
    es = epoch_start if epoch_start is not None else sf.epoch_start[log_idx]
    ee = epoch_end if epoch_end is not None else sf.epoch_end[log_idx]
    df = slice_epoch(log.dataframe, es, ee)
    return log, df, es, ee


@router.post("/spectrum")
def run_spectrum(req: SpectrumRequest):
    try:
        results = []
        for file_idx in req.file_indices:
            log, df, _, _ = _get_epoched_log(
                req.session_id, file_idx, req.log_idx, req.epoch_start, req.epoch_end
            )
            file_result = {"file_idx": file_idx, "name": log.name, "axes": {}}
            for axis in req.axes:
                signals = {}
                for trace in req.traces:
                    y = get_trace(df, trace, axis)
                    if y is not None:
                        signals[trace] = y
                if signals:
                    file_result["axes"][AXIS_NAMES[axis]] = compute_spectrum_grid(
                        signals, log.lograte_khz, psd=req.psd, sub100hz=req.sub100hz
                    )
            results.append(file_result)
    except KeyError:
        raise HTTPException(404, "Session not found")
    except IndexError:
        raise HTTPException(404, "File or log not found")
    return {"results": results}


@router.post("/step-response")
def run_step_response(req: StepResponseRequest):
    try:
        results = []
        for file_idx in req.file_indices:
            log, df, _, _ = _get_epoched_log(
                req.session_id, file_idx, req.log_idx, req.epoch_start, req.epoch_end
            )
            axis_data = {}
            for axis in req.axes:
                sp = get_trace(df, "setpoint", axis)
                gy = get_trace(df, "gyro", axis)
                if sp is None or gy is None:
                    axis_data[AXIS_NAMES[axis]] = {"curves": [], "stats": step_stats([], [])}
                    continue
                responses, time_ms = step_calc(
                    sp, gy, log.lograte_khz, req.y_correction, req.smooth_factor
                )
                mean_curve = responses.mean(axis=0).tolist() if len(responses) else []
                axis_data[AXIS_NAMES[axis]] = {
                    "time_ms": time_ms.tolist(),
                    "curves": responses.tolist(),
                    "mean_curve": mean_curve,
                    "stats": step_stats(responses, time_ms),
                    "pidf": [log.roll_pidf, log.pitch_pidf, log.yaw_pidf][axis],
                }
            results.append({"file_idx": file_idx, "name": log.name, "axes": axis_data})
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
        if throttle is None and "rcCommand_3_" in df.columns:
            throttle = df["rcCommand_3_"].values
        y = get_trace(df, req.trace, req.axis)
        if throttle is None or y is None:
            raise HTTPException(400, "Required traces not found")

        freq, amp_mat = throttle_spectrum(throttle, y, log.lograte_khz, psd=req.psd)
        fund, harmonics = estimate_rpm(freq, amp_mat)
    except KeyError:
        raise HTTPException(404, "Session not found")

    return {
        "freq_hz": freq.tolist(),
        "amp_matrix": amp_mat.tolist(),
        "throttle_bins": list(range(1, 101)),
        "rpm_fundamental": fund.tolist(),
        "rpm_harmonics": harmonics.tolist(),
    }


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


def _to_json(obj):
    """Convert numpy arrays in nested dicts to lists for JSON serialization."""
    import numpy as np

    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: _to_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_json(v) for v in obj]
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    return obj


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
            get_trace(df, "gyro", ax) or [],
            get_trace(df, "setpoint", ax) or [],
            get_trace(df, "pterm", ax) or [],
            get_trace(df, "iterm", ax) or [],
            get_trace(df, "dterm", ax) or [],
            get_trace(df, "fterm", ax) or [],
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

    return {"stats": stats, "motor_noise": motor_noise}


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
