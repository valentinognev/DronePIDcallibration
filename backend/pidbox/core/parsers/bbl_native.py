"""Optional pure-Python blackbox parser (future replacement for blackbox_decode).

This module defines the interface; full BBL binary parsing can be implemented
using the Betaflight blackbox field definitions when blackbox_decode is unavailable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class BlackboxParser(ABC):
    @abstractmethod
    def decode(self, path: Path, output_dir: Path) -> list[Path]:
        ...


class BlackboxDecodeBinary(BlackboxParser):
    """Current implementation: shell out to blackbox_decode."""

    def __init__(self, decoder_path: str = "blackbox_decode") -> None:
        self.decoder_path = decoder_path

    def decode(self, path: Path, output_dir: Path) -> list[Path]:
        from pidbox.core.parsers.betaflight import _decode_blackbox

        csv_paths, _ = _decode_blackbox(path, use_inav=False)
        return csv_paths


class PurePythonBlackboxParser(BlackboxParser):
    """Placeholder for future pure-Python implementation."""

    def decode(self, path: Path, output_dir: Path) -> list[Path]:
        raise NotImplementedError(
            "Pure-Python BBL parser not yet implemented. "
            "Install blackbox_decode or set BLACKBOX_DECODE env var."
        )
