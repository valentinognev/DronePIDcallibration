"""Application configuration."""

from __future__ import annotations

import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("PIDBOX_DATA_DIR", Path.home() / ".cache" / "pidbox"))
CACHE_DIR = DATA_DIR / "cache"
UPLOAD_DIR = DATA_DIR / "uploads"

BLACKBOX_DECODE = os.environ.get("BLACKBOX_DECODE", "blackbox_decode")
BLACKBOX_DECODE_INAV = os.environ.get("BLACKBOX_DECODE_INAV", "blackbox_decode_INAV")

DEFAULT_EPOCH_START_SEC = 2.0
DEFAULT_EPOCH_END_TRIM_SEC = 1.0
DOWNSAMPLE_MULTIPLIER = 5
US2SEC = 1_000_000
MAX_MOTOR_OUTPUT = 2000


def ensure_dirs() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
