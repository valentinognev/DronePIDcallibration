"""Log loading orchestration."""

from __future__ import annotations

from pathlib import Path

# Import parsers to register them
from pidbox.core.parsers import ardupilot  # noqa: F401
from pidbox.core.parsers import betaflight  # noqa: F401
from pidbox.core.parsers import inav  # noqa: F401
from pidbox.core.parsers import quicksilver  # noqa: F401
from pidbox.core.parsers.base import LoadedLog, get_parser


def load_log_file(
    path: Path,
    firmware: str,
    log_indices: list[int] | None = None,
) -> list[LoadedLog]:
    parser = get_parser(firmware)
    return parser.parse(path, log_indices=log_indices)


def list_firmwares() -> list[dict[str, str]]:
    from pidbox.core.parsers.base import PARSERS

    return [
        {"key": k, "display_name": cls.display_name}
        for k, cls in PARSERS.items()
    ]
