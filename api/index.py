"""Vercel ASGI entrypoint.

Vercel's filesystem is read-only except for /tmp, so the local SQLite fallback
must live there. For the persistent 24/7 monitor use the Render/Docker service.
"""

from __future__ import annotations

import os
from pathlib import Path

from market_sentinel.web import create_app


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("DATABASE_PATH", "/tmp/market-sentinel.db")

app = create_app(str(ROOT / "config.yaml"))
