"""Debug mode index constants per firmware version."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DebugIndices:
    GYRO_SCALED: int = 6
    GYRO_FILTERED: int = 3
    RC_INTERPOLATION: int = 7
    FFT_FREQ: int = 17
    RPM_FILTER: int = 46
    FEEDFORWARD: int = 59
    DSHOT_RPM_TELEMETRY: int = 37
    CHIRP: int = -1


def debug_mode_indices(fw_type: str, fw_major: int, fw_minor: int) -> dict[str, int]:
    """Return debug mode index constants for a given firmware version."""
    idx = DebugIndices()
    if fw_type == "Betaflight" and fw_major >= 2025:
        idx.GYRO_SCALED = -1
        idx.RC_INTERPOLATION = 6
        idx.FFT_FREQ = 16
        idx.RPM_FILTER = 45
        idx.FEEDFORWARD = 58
        idx.DSHOT_RPM_TELEMETRY = 36
        idx.CHIRP = 119
    return {
        "GYRO_SCALED": idx.GYRO_SCALED,
        "GYRO_FILTERED": idx.GYRO_FILTERED,
        "RC_INTERPOLATION": idx.RC_INTERPOLATION,
        "FFT_FREQ": idx.FFT_FREQ,
        "RPM_FILTER": idx.RPM_FILTER,
        "FEEDFORWARD": idx.FEEDFORWARD,
        "DSHOT_RPM_TELEMETRY": idx.DSHOT_RPM_TELEMETRY,
        "CHIRP": idx.CHIRP,
    }
