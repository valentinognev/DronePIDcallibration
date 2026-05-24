"""QuickSilver JSON log parser."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from pidbox.config import US2SEC, default_epoch_bounds
from pidbox.core.debug_modes import debug_mode_indices
from pidbox.core.parsers.base import LoadedLog, LogParser, register_parser
from pidbox.core.parsers.common import compute_derived_columns, parse_pidf


def _json_to_csv(json_path: Path, out_csv: Path) -> list[tuple[str, str]]:
    """Convert QuickSilver JSON export to CSV."""
    with open(json_path) as f:
        data = json.load(f)

    # Flatten nested structure - QS JSON has frames array
    frames = data.get("frames", data.get("data", []))
    if not frames:
        raise ValueError("No frames found in QuickSilver JSON")

    df = pd.json_normalize(frames)
    df.to_csv(out_csv, index=False)

    setup: list[tuple[str, str]] = [
        ("Firmware revision", "QuickSilver"),
        ("Craft name", data.get("craftName", "")),
    ]
    if "header" in data:
        for k, v in data["header"].items():
            setup.append((str(k), str(v)))
    return setup


@register_parser
class QuickSilverParser(LogParser):
    firmware_key = "quicksilver"
    display_name = "QuickSilver"
    extensions = (".json", ".btfl")

    def can_parse(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def parse(
        self, path: Path, log_indices: list[int] | None = None
    ) -> list[LoadedLog]:
        workdir = Path(tempfile.mkdtemp(prefix="pidbox_qs_"))
        csv_path = workdir / f"{path.stem}.01.csv"
        setup_info = _json_to_csv(path, csv_path)
        df = pd.read_csv(csv_path, low_memory=False)

        if "time_us" not in df.columns and "time" in df.columns:
            df["time_us"] = df["time"].astype(float) * US2SEC

        df = compute_derived_columns(df, firmware="betaflight")
        lograte = round((1000 / np.median(np.diff(df["time_us"].values))) * 10) / 10
        dbg_idx = debug_mode_indices("QuickSilver", 0, 0)
        roll_pidf, pitch_pidf, yaw_pidf = parse_pidf(setup_info)
        duration_sec = (df["time_us"].iloc[-1] - df["time_us"].iloc[0]) / US2SEC
        epoch_start, epoch_end = default_epoch_bounds(duration_sec)

        return [
            LoadedLog(
                name=csv_path.name,
                source_path=str(path),
                dataframe=df,
                setup_info=setup_info,
                lograte_khz=lograte,
                fw_type="QuickSilver",
                fw_major=0,
                fw_minor=0,
                debug_mode=6,
                debug_indices=dbg_idx,
                gyro_debug_axis=0,
                roll_pidf=roll_pidf,
                pitch_pidf=pitch_pidf,
                yaw_pidf=yaw_pidf,
                default_epoch_start=epoch_start,
                default_epoch_end=epoch_end,
            )
        ]
