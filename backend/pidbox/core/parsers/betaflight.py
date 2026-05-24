"""Betaflight blackbox log parser via blackbox_decode."""

from __future__ import annotations

import glob
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from pidbox.config import (
    DEFAULT_EPOCH_END_TRIM_SEC,
    DEFAULT_EPOCH_START_SEC,
    US2SEC,
    require_decoder,
)
from pidbox.core.debug_modes import debug_mode_indices
from pidbox.core.parsers.base import LoadedLog, LogParser, register_parser
from pidbox.core.parsers.common import (
    compute_derived_columns,
    extract_setup_info_from_header,
    parse_bf_version,
    parse_pidf,
    read_csv_log,
)


def _decode_blackbox(source: Path, use_inav: bool = False) -> tuple[list[Path], str]:
    """Run blackbox_decode and return list of CSV paths."""
    workdir = Path(tempfile.mkdtemp(prefix="pidbox_decode_"))
    dest = workdir / source.name
    shutil.copy2(source, dest)

    if use_inav:
        decoder = require_decoder("BLACKBOX_DECODE_INAV", "blackbox_decode_INAV")
    else:
        decoder = require_decoder("BLACKBOX_DECODE", "blackbox_decode")

    cmd = [str(decoder), str(dest)]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=workdir)
    decode_output = result.stdout + result.stderr

    if result.returncode != 0 and not decode_output:
        raise RuntimeError(
            f"{decoder.name} failed (exit {result.returncode}) for {source.name}"
        )

    base = dest.stem
    csv_files = sorted(Path(p) for p in glob.glob(str(workdir / f"{base}*.csv")))
    csv_files = [
        p
        for p in csv_files
        if not any(x in p.name.lower() for x in (".event", ".gps"))
        and p.stat().st_size > 1000
    ]

    # Clean event/gps side files
    for pattern in ("*.event", "*.gps.gpx", "*.gps.csv"):
        for f in glob.glob(str(workdir / pattern)):
            Path(f).unlink(missing_ok=True)

    return csv_files, decode_output


def _extract_log_durations(decode_output: str) -> list[str]:
    durations = []
    for m in re.finditer(r"duration", decode_output):
        snippet = decode_output[m.start() : m.start() + 80].split("\n")[0]
        durations.append(snippet.strip())
    return durations


@register_parser
class BetaflightParser(LogParser):
    firmware_key = "betaflight"
    display_name = "Betaflight"
    extensions = (".bbl", ".bfl", ".txt", ".btfl", ".csv")

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
            csv_paths, _ = _decode_blackbox(path, use_inav=False)
            header_source = path

        if log_indices is not None:
            csv_paths = [csv_paths[i] for i in log_indices if i < len(csv_paths)]

        setup_info = extract_setup_info_from_header(header_source, log_index=0)
        logs: list[LoadedLog] = []

        for i, csv_path in enumerate(csv_paths):
            df = read_csv_log(csv_path)
            df = compute_derived_columns(df, firmware="betaflight")
            lograte = round((1000 / np.median(np.diff(df["time_us"].values))) * 10) / 10

            if ext != ".csv":
                setup_info = extract_setup_info_from_header(header_source, log_index=i)

            fw_type, fw_major, fw_minor = parse_bf_version(setup_info)
            dbg_idx = debug_mode_indices(fw_type, fw_major, fw_minor)

            try:
                debug_mode = int(
                    next(v for k, v in setup_info if k.strip() == "debug_mode")
                )
            except StopIteration:
                debug_mode = (
                    dbg_idx["GYRO_FILTERED"]
                    if dbg_idx["GYRO_SCALED"] == -1
                    else dbg_idx["GYRO_SCALED"]
                )

            try:
                gyro_debug_axis = int(
                    next(v for k, v in setup_info if k.strip() == "gyro_debug_axis")
                )
            except StopIteration:
                gyro_debug_axis = 0

            roll_pidf, pitch_pidf, yaw_pidf = parse_pidf(setup_info)
            duration_sec = (df["time_us"].iloc[-1] - df["time_us"].iloc[0]) / US2SEC

            logs.append(
                LoadedLog(
                    name=csv_path.name,
                    source_path=str(path),
                    dataframe=df,
                    setup_info=setup_info,
                    lograte_khz=lograte,
                    fw_type=fw_type,
                    fw_major=fw_major,
                    fw_minor=fw_minor,
                    debug_mode=debug_mode,
                    debug_indices=dbg_idx,
                    gyro_debug_axis=gyro_debug_axis,
                    roll_pidf=roll_pidf,
                    pitch_pidf=pitch_pidf,
                    yaw_pidf=yaw_pidf,
                    default_epoch_start=DEFAULT_EPOCH_START_SEC,
                    default_epoch_end=round(duration_sec - DEFAULT_EPOCH_END_TRIM_SEC, 1),
                )
            )
        return logs


@register_parser
class EmuflightParser(BetaflightParser):
    firmware_key = "emuflight"
    display_name = "Emuflight"


@register_parser
class FettecParser(BetaflightParser):
    firmware_key = "fettec"
    display_name = "FETTEC"


@register_parser
class RotorflightParser(BetaflightParser):
    firmware_key = "rotorflight"
    display_name = "Rotorflight"


@register_parser
class KissParser(BetaflightParser):
    firmware_key = "kiss"
    display_name = "KISS Ultra"
