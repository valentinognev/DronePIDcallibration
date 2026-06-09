"""Session management and log data storage."""

from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from pidbox.config import CACHE_DIR, UPLOAD_DIR, ensure_dirs
from pidbox.core.loader import LoadedLog, empty_parse_error_message, load_log_file


@dataclass
class SessionFile:
    file_id: str
    original_name: str
    logs: list[LoadedLog] = field(default_factory=list)
    epoch_start: list[float] = field(default_factory=list)
    epoch_end: list[float] = field(default_factory=list)
    parse_warnings: list[str] = field(default_factory=list)


@dataclass
class Session:
    session_id: str
    firmware: str
    files: list[SessionFile] = field(default_factory=list)
    upload_dir: Path = field(default_factory=Path)


class SessionManager:
    def __init__(self) -> None:
        ensure_dirs()
        self._sessions: dict[str, Session] = {}

    def create(self, firmware: str = "betaflight") -> Session:
        session_id = str(uuid.uuid4())
        upload_dir = UPLOAD_DIR / session_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        session = Session(session_id=session_id, firmware=firmware, upload_dir=upload_dir)
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            raise KeyError(f"Session {session_id} not found")
        return self._sessions[session_id]

    def delete(self, session_id: str) -> None:
        session = self.get(session_id)
        if session.upload_dir.exists():
            shutil.rmtree(session.upload_dir, ignore_errors=True)
        cache = CACHE_DIR / session_id
        if cache.exists():
            shutil.rmtree(cache, ignore_errors=True)
        del self._sessions[session_id]

    def add_file(
        self,
        session_id: str,
        filename: str,
        content: bytes,
        log_indices: list[int] | None = None,
    ) -> SessionFile:
        session = self.get(session_id)
        file_id = str(uuid.uuid4())
        dest = session.upload_dir / filename
        dest.write_bytes(content)

        try:
            logs = load_log_file(dest, session.firmware, log_indices=log_indices)
        except Exception as e:
            dest.unlink(missing_ok=True)
            detail = empty_parse_error_message(dest, session.firmware)
            cause = str(e).strip()
            if cause and cause not in detail:
                detail = f"{detail} ({cause})"
            raise ValueError(detail) from e
        if not logs:
            dest.unlink(missing_ok=True)
            raise ValueError(empty_parse_error_message(dest, session.firmware))

        parse_warnings: list[str] = []
        for log in logs:
            for msg in log.metadata.get("missing_data", []):
                if msg not in parse_warnings:
                    parse_warnings.append(msg)

        sf = SessionFile(
            file_id=file_id,
            original_name=filename,
            logs=logs,
            parse_warnings=parse_warnings,
        )
        for log in logs:
            sf.epoch_start.append(log.default_epoch_start)
            sf.epoch_end.append(log.default_epoch_end)
        session.files.append(sf)
        return sf

    def get_log(self, session_id: str, file_idx: int, log_idx: int = 0) -> LoadedLog:
        session = self.get(session_id)
        if file_idx >= len(session.files):
            raise IndexError("file_idx out of range")
        sf = session.files[file_idx]
        if log_idx >= len(sf.logs):
            raise IndexError("log_idx out of range")
        return sf.logs[log_idx]

    def set_epoch(
        self, session_id: str, file_idx: int, log_idx: int, start: float, end: float
    ) -> None:
        session = self.get(session_id)
        sf = session.files[file_idx]
        sf.epoch_start[log_idx] = start
        sf.epoch_end[log_idx] = end

    def cleanup(self) -> None:
        for sid in list(self._sessions):
            self.delete(sid)

    def cache_dataframe(self, session_id: str, key: str, df: pd.DataFrame) -> Path:
        path = CACHE_DIR / session_id / f"{key}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path)
        return path


session_manager = SessionManager()
