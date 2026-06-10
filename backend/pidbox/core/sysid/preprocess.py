"""Timeframe extraction, gap detection, and signal synchronization."""

from __future__ import annotations

from copy import deepcopy

import numpy as np


def cleanup_series(
    timestamps: np.ndarray,
    values: np.ndarray,
    window_size: int = 50,
    min_valid_ratio: float = 0.3,
) -> tuple[np.ndarray, np.ndarray]:
    """Drop sparse NaN regions and enforce monotonic timestamps."""
    timestamps = np.asarray(timestamps, dtype=float)
    values = np.asarray(values, dtype=float)
    valid_mask = ~np.isnan(values)

    if len(values) == 0:
        return np.array([]), np.array([])

    if np.all(valid_mask):
        sort_idx = np.argsort(timestamps)
        ts = timestamps[sort_idx]
        vals = values[sort_idx]
        if len(ts) > 1:
            mono = np.ones(len(ts), dtype=bool)
            mono[1:] = ts[1:] > ts[:-1]
            return vals[mono], ts[mono]
        return vals, ts

    n = len(values)
    region_mask = np.zeros(n, dtype=bool)
    for i in range(n):
        start_idx = max(0, i - window_size // 2)
        end_idx = min(n, i + window_size // 2 + 1)
        ratio = np.sum(valid_mask[start_idx:end_idx]) / (end_idx - start_idx)
        if ratio >= min_valid_ratio:
            region_mask[i] = True

    expanded = region_mask.copy()
    for i in range(1, n - 1):
        if region_mask[i - 1] or region_mask[i + 1]:
            expanded[i] = True

    final_mask = expanded & valid_mask
    good_ts = timestamps[final_mask]
    good_vals = values[final_mask]

    if len(good_ts) > 0:
        sort_idx = np.argsort(good_ts)
        good_ts = good_ts[sort_idx]
        good_vals = good_vals[sort_idx]
        if len(good_ts) > 1:
            mono = np.ones(len(good_ts), dtype=bool)
            mono[1:] = good_ts[1:] > good_ts[:-1]
            good_ts = good_ts[mono]
            good_vals = good_vals[mono]

    return good_vals, good_ts


def extract_timeframes(flights: list[dict], timeframes: list[dict]) -> list[dict]:
    output: list[dict] = []
    fragment_counter: dict[str, int] = {}
    for timeframe in timeframes:
        flight = deepcopy(flights[timeframe["flight"]])
        fragment_id = fragment_counter.get(flight["name"], 0)
        fragment_counter[flight["name"]] = fragment_id + 1
        flight["name"] = f"{flight['name']}.{fragment_id}"
        start, end = timeframe["start"], timeframe["end"]
        data = flight["data"]
        for series in data:
            mask = (data[series]["timestamps"] > start) & (data[series]["timestamps"] < end)
            data[series]["timestamps"] = data[series]["timestamps"][mask]
            data[series]["values"] = data[series]["values"][mask]
        output.append(flight)
    return output


def slice_gaps_and_interpolate(flights: list[dict]) -> list[dict]:
    """Split flights at gaps and interpolate all signals to a common time grid."""
    flights_output: list[dict] = []

    for flight in flights:
        lowest_frequency = None
        lowest_frequency_name = None
        highest_frequency = None
        highest_frequency_name = None

        for name, series in flight["data"].items():
            ts = series["timestamps"]
            if len(ts) < 2:
                continue
            diff = np.diff(ts)
            frequency = 1.0 / np.median(diff)
            if lowest_frequency is None or frequency < lowest_frequency:
                lowest_frequency = frequency
                lowest_frequency_name = name
            if highest_frequency is None or frequency > highest_frequency:
                highest_frequency = frequency
                highest_frequency_name = name

        if lowest_frequency is None or highest_frequency is None:
            continue

        interval_threshold = 3.0 / lowest_frequency
        earliest_timestamp_all = max(data["timestamps"][0] for data in flight["data"].values())
        latest_timestamp_all = min(data["timestamps"][-1] for data in flight["data"].values())

        master_full = flight["data"][highest_frequency_name]["timestamps"]
        master_timestamps = master_full[
            (master_full > earliest_timestamp_all) & (master_full < latest_timestamp_all)
        ]
        if len(master_timestamps) < 2:
            continue

        earliest_timestamp = master_timestamps[0]
        latest_timestamp = master_timestamps[-1]
        total_time = latest_timestamp - earliest_timestamp

        gaps: list[tuple[float, float]] = []
        for _name, data in flight["data"].items():
            current_full = data["timestamps"]
            current = current_full[
                (current_full > earliest_timestamp) & (current_full < latest_timestamp)
            ]
            augmented = np.concatenate([[earliest_timestamp], current, [latest_timestamp]])
            diff = np.diff(augmented)
            for gap_idx in np.where(diff > interval_threshold)[0]:
                if 0 < gap_idx < len(current):
                    gaps.append((current[gap_idx - 1], current[gap_idx]))

        gaps_sorted = sorted(gaps, key=lambda x: x[0])
        combined_gaps: list[tuple[float, float]] = []
        current_gap_start = None
        current_gap_end = None
        for i, (gap_start, gap_end) in enumerate(gaps_sorted):
            if current_gap_start is None:
                current_gap_start = gap_start
            if current_gap_end is None:
                current_gap_end = gap_end
            if gap_end > current_gap_end:
                current_gap_end = gap_end
            if i < len(gaps_sorted) - 1:
                next_start, _ = gaps_sorted[i + 1]
                if next_start - current_gap_end > interval_threshold:
                    combined_gaps.append((current_gap_start, current_gap_end))
                    current_gap_start = None
                    current_gap_end = None
            else:
                combined_gaps.append((current_gap_start, current_gap_end))

        subflights: list[dict] = []
        current_segment_start = earliest_timestamp
        for gap_start, gap_end in [*combined_gaps, (latest_timestamp, latest_timestamp)]:
            segment_time = gap_start - current_segment_start
            if segment_time > 0.01 * total_time:
                seg_ts = master_timestamps[
                    (master_timestamps > current_segment_start) & (master_timestamps < gap_start)
                ]
                if len(seg_ts) < 2:
                    current_segment_start = gap_end
                    continue
                subflight = {
                    name: {
                        "timestamps": seg_ts,
                        "values": np.interp(seg_ts, data["timestamps"], data["values"]),
                    }
                    for name, data in flight["data"].items()
                }
                subflights.append(subflight)
            current_segment_start = gap_end

        for subflight_i, subflight in enumerate(subflights):
            flights_output.append(
                {
                    "name": f"{flight['name']}_{subflight_i}",
                    "convention": flight["convention"],
                    "motor_source": flight.get("motor_source"),
                    "timestamps": subflight[highest_frequency_name]["timestamps"],
                    "data": subflight,
                }
            )

    return flights_output
