"""User settings persistence."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from pidbox.api.schemas import UserSettings
from pidbox.config import DATA_DIR, ensure_dirs

router = APIRouter()
SETTINGS_PATH = DATA_DIR / "defaults.json"


@router.get("", response_model=UserSettings)
def get_settings():
    ensure_dirs()
    if SETTINGS_PATH.exists():
        return UserSettings(**json.loads(SETTINGS_PATH.read_text()))
    return UserSettings()


@router.put("", response_model=UserSettings)
def save_settings(settings: UserSettings):
    ensure_dirs()
    SETTINGS_PATH.write_text(settings.model_dump_json(indent=2))
    return settings
