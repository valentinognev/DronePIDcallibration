"""INAV blackbox parser (uses blackbox_decode_INAV)."""

from __future__ import annotations

import glob
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from pidbox.config import US2SEC, default_epoch_bounds, require_decoder
from pidbox.core.debug_modes import debug_mode_indices
from pidbox.core.parsers.base import LoadedLog, LogParser, register_parser
from pidbox.core.parsers.common import (
    compute_derived_columns,
    extract_setup_info_from_header,
    parse_bf_version,
    parse_pidf,
    read_csv_log,
)


@register_parser
class InavParser(LogParser):
    firmware_key = "inav"
    display_name = "INAV"
    extensions = (".bbl", ".bfl", ".txt", ".csv")

    def can_parse(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def parse(
        self, path: Path, log_indices: list[int] | None = None
    ) -> list[LoadedLog]:
        ext = path.suffix.lower()
        if ext == ".csv":
            csv_paths = [path]
            header_source = path
        else:
            workdir = Path(tempfile.mkdtemp(prefix="pidbox_inav_"))
            dest = workdir / path.name
            shutil.copy2(path, dest)
            decoder = require_decoder("BLACKBOX_DECODE_INAV", "blackbox_decode_INAV")
            subprocess.run([str(decoder), str(dest)], capture_output=True, cwd=workdir)
            csv_paths = sorted(
                p
                for p in Path(workdir).glob(f"{dest.stem}*.csv")
                if p.stat().st_size > 1000 and ".gps" not in p.name.lower()
            )
            header_source = path

        if log_indices is not None:
            csv_paths = [csv_paths[i] for i in log_indices if i < len(csv_paths)]

        logs: list[LoadedLog] = []
        for i, csv_path in enumerate(csv_paths):
            df = read_csv_log(csv_path)
            df = compute_derived_columns(df, firmware="inav")
            lograte = round((1000 / np.median(np.diff(df["time_us"].values))) * 10) / 10
            setup_info = extract_setup_info_from_header(header_source, log_index=i)
            fw_type, fw_major, fw_minor = parse_bf_version(setup_info)
            dbg_idx = debug_mode_indices(fw_type, fw_major, fw_minor)
            roll_pidf, pitch_pidf, yaw_pidf = parse_pidf(setup_info)
            duration_sec = (df["time_us"].iloc[-1] - df["time_us"].iloc[0]) / US2SEC
            epoch_start, epoch_end = default_epoch_bounds(duration_sec)

            logs.append(
                LoadedLog(
                    name=csv_path.name,
                    source_path=str(path),
                    dataframe=df,
                    setup_info=setup_info,
                    lograte_khz=lograte,
                    fw_type=fw_type or "INAV",
                    fw_major=fw_major,
                    fw_minor=fw_minor,
                    debug_mode=dbg_idx.get("GYRO_SCALED", 6),
                    debug_indices=dbg_idx,
                    gyro_debug_axis=0,
                    roll_pidf=roll_pidf,
                    pitch_pidf=pitch_pidf,
                    yaw_pidf=yaw_pidf,
                    default_epoch_start=epoch_start,
                    default_epoch_end=epoch_end,
                )
            )
        return logs
