"""Log parser interface and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class LoadedLog:
    """Normalized log data ready for analysis."""

    name: str
    source_path: str
    dataframe: Any  # pd.DataFrame
    setup_info: list[tuple[str, str]]
    lograte_khz: float
    fw_type: str
    fw_major: int
    fw_minor: int
    debug_mode: int
    debug_indices: dict[str, int]
    gyro_debug_axis: int
    roll_pidf: str
    pitch_pidf: str
    yaw_pidf: str
    default_epoch_start: float
    default_epoch_end: float
    metadata: dict[str, Any] = field(default_factory=dict)


class LogParser(ABC):
    firmware_key: str
    display_name: str
    extensions: tuple[str, ...]

    @abstractmethod
    def can_parse(self, path: Path) -> bool:
        ...

    @abstractmethod
    def parse(
        self, path: Path, log_indices: list[int] | None = None
    ) -> list[LoadedLog]:
        ...


PARSERS: dict[str, type[LogParser]] = {}


def register_parser(cls: type[LogParser]) -> type[LogParser]:
    PARSERS[cls.firmware_key] = cls
    return cls


def get_parser(firmware: str) -> LogParser:
    key = firmware.lower().replace(" ", "")
    if key not in PARSERS:
        raise ValueError(f"Unknown firmware: {firmware}. Available: {list(PARSERS)}")
    return PARSERS[key]()
