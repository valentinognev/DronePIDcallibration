"""ArduPilot DataFlash binary log parser."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from pidbox.config import DEFAULT_EPOCH_END_TRIM_SEC, DEFAULT_EPOCH_START_SEC, US2SEC
from pidbox.core.debug_modes import debug_mode_indices
from pidbox.core.parsers.base import LoadedLog, LogParser, register_parser


def _read_ardupilot_bin(path: Path) -> tuple[pd.DataFrame, list[tuple[str, str]]]:
    """Parse ArduPilot .bin using pymavlink DFReader."""
    try:
        from pymavlink import DFReader
    except ImportError as e:
        raise ImportError("pymavlink required for ArduPilot logs") from e

    reader = DFReader.DFReader_binary(str(path))
    messages: dict[str, list] = {}
    params: dict[str, str] = {}

    while True:
        msg = reader.recv_msg()
        if msg is None:
            break
        mtype = msg.get_type()
        if mtype == "PARM":
            params[getattr(msg, "Name", "")] = str(getattr(msg, "Value", ""))
            continue
        d = msg.to_dict()
        if mtype not in messages:
            messages[mtype] = []
        messages[mtype].append(d)

    # Build gyro/PID dataframe from ATT, RATE, PIDR etc.
    rows: list[dict] = []
    if "RATE" in messages:
        for m in messages["RATE"]:
            rows.append(
                {
                    "time_us": m.get("TimeUS", 0),
                    "gyroADC_0_": m.get("R", 0),
                    "gyroADC_1_": m.get("P", 0),
                    "gyroADC_2_": m.get("Y", 0),
                    "setpoint_0_": m.get("DesRoll", 0),
                    "setpoint_1_": m.get("DesPitch", 0),
                    "setpoint_2_": m.get("DesYaw", 0),
                }
            )
    elif "ATT" in messages:
        for m in messages["ATT"]:
            rows.append(
                {
                    "time_us": m.get("TimeUS", 0),
                    "gyroADC_0_": m.get("Roll", 0),
                    "gyroADC_1_": m.get("Pitch", 0),
                    "gyroADC_2_": m.get("Yaw", 0),
                }
            )

    if not rows:
        raise ValueError("No usable RATE/ATT messages in ArduPilot log")

    df = pd.DataFrame(rows).sort_values("time_us").reset_index(drop=True)

    setup: list[tuple[str, str]] = [
        ("Firmware revision", "ArduPilot"),
        ("source", path.name),
    ]
    for k, v in sorted(params.items())[:200]:
        setup.append((k, v))

    return df, setup


@register_parser
class ArdupilotParser(LogParser):
    firmware_key = "ardupilot"
    display_name = "ArduPilot"
    extensions = (".bin", ".log")

    def can_parse(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def parse(
        self, path: Path, log_indices: list[int] | None = None
    ) -> list[LoadedLog]:
        df, setup_info = _read_ardupilot_bin(path)
        lograte = round((1000 / np.median(np.diff(df["time_us"].values))) * 10) / 10
        dbg_idx = debug_mode_indices("ArduPilot", 0, 0)
        duration_sec = (df["time_us"].iloc[-1] - df["time_us"].iloc[0]) / US2SEC

        return [
            LoadedLog(
                name=path.name,
                source_path=str(path),
                dataframe=df,
                setup_info=setup_info,
                lograte_khz=lograte,
                fw_type="ArduPilot",
                fw_major=0,
                fw_minor=0,
                debug_mode=0,
                debug_indices=dbg_idx,
                gyro_debug_axis=0,
                roll_pidf="",
                pitch_pidf="",
                yaw_pidf="",
                default_epoch_start=DEFAULT_EPOCH_START_SEC,
                default_epoch_end=round(duration_sec - DEFAULT_EPOCH_END_TRIM_SEC, 1),
            )
        ]
