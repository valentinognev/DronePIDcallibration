"""Log loading orchestration."""

from __future__ import annotations

from pathlib import Path

# Import parsers to register them
from pidbox.core.parsers import ardupilot  # noqa: F401
from pidbox.core.parsers import betaflight  # noqa: F401
from pidbox.core.parsers import inav  # noqa: F401
from pidbox.core.parsers import px4  # noqa: F401
from pidbox.core.parsers import quicksilver  # noqa: F401
from pidbox.core.parsers.base import LoadedLog, get_parser


def load_log_file(
    path: Path,
    firmware: str,
    log_indices: list[int] | None = None,
) -> list[LoadedLog]:
    parser = get_parser(firmware)
    return parser.parse(path, log_indices=log_indices)


def empty_parse_error_message(path: Path, session_firmware: str) -> str:
    """Build a user-facing message when parsing yields no logs."""
    from pidbox.core.parsers.base import PARSERS

    msg = "No logs could be parsed from this file."
    if path.suffix.lower() == ".ulg":
        msg += " Use firmware 'px4' for PX4 ULOG files."

    expected = [
        key
        for key, cls in PARSERS.items()
        if key != session_firmware and cls().can_parse(path)
    ]
    if expected:
        hints = ", ".join(f"'{k}'" for k in expected)
        msg += f" This file may require firmware {hints} (session is '{session_firmware}')."
    else:
        msg += f" Session firmware is '{session_firmware}'."

    return msg


def list_firmwares() -> list[dict[str, str]]:
    from pidbox.core.parsers.base import PARSERS

    return [
        {"key": k, "display_name": cls.display_name}
        for k, cls in PARSERS.items()
    ]
