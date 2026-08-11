"""Automatic FastAPI entrypoint for Vercel."""

from __future__ import annotations

import os
from pathlib import Path

from market_sentinel.web import create_app


ROOT = Path(__file__).resolve().parent
os.environ.setdefault("DATABASE_PATH", "/tmp/market-sentinel.db")

app = create_app(str(ROOT / "config.yaml"))
