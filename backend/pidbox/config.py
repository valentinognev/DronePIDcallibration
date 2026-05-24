"""Application configuration."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

DATA_DIR = Path(os.environ.get("PIDBOX_DATA_DIR", Path.home() / ".cache" / "pidbox"))
CACHE_DIR = DATA_DIR / "cache"
UPLOAD_DIR = DATA_DIR / "uploads"

DEFAULT_EPOCH_START_SEC = 2.0
DEFAULT_EPOCH_END_TRIM_SEC = 1.0
DOWNSAMPLE_MULTIPLIER = 5
US2SEC = 1_000_000
MAX_MOTOR_OUTPUT = 2000


def project_root() -> Path:
    """Repository root (parent of backend/)."""
    if root := os.environ.get("PIDBOX_ROOT"):
        return Path(root)
    return Path(__file__).resolve().parents[2]


def resolve_decoder_path(env_var: str, binary_name: str) -> Path | None:
    """
    Resolve blackbox decoder binary.

    Search order:
      1. Explicit env var path (BLACKBOX_DECODE / BLACKBOX_DECODE_INAV)
      2. $PIDBOX_ROOT/tools/bin/<binary_name>
      3. shutil.which(binary_name) on PATH
    """
    if raw := os.environ.get(env_var):
        path = Path(raw)
        if path.is_file() and os.access(path, os.X_OK):
            return path

    local = project_root() / "tools" / "bin" / binary_name
    if local.is_file() and os.access(local, os.X_OK):
        return local

    if found := shutil.which(binary_name):
        return Path(found)

    return None


def require_decoder(env_var: str, binary_name: str) -> Path:
    path = resolve_decoder_path(env_var, binary_name)
    if path is None:
        root = project_root()
        raise FileNotFoundError(
            f"{binary_name} not found. Run ./install.sh from {root} to build it locally, "
            f"or set {env_var} to the decoder executable."
        )
    return path


def ensure_dirs() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
