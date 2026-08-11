from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    core_assets: frozenset[str]
    timeframes: tuple[str, ...]
    analysis: dict
    runtime: dict
    telegram_token: str | None
    telegram_chat_id: str | None


def load_settings(path: str | Path = "config.yaml") -> Settings:
    load_dotenv()
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    runtime = dict(raw["runtime"])
    if os.getenv("DATABASE_PATH"):
        runtime["database_path"] = os.environ["DATABASE_PATH"]
    return Settings(
        core_assets=frozenset(x.upper() for x in raw["core_assets"]),
        timeframes=tuple(raw["timeframes"]),
        analysis=raw["analysis"],
        runtime=runtime,
        telegram_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
    )
