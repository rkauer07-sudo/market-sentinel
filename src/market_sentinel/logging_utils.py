from __future__ import annotations

import logging


class OperationalLogHandler(logging.Handler):
    """Persist only application events, never noisy third-party HTTP traces."""

    def __init__(self, store):
        super().__init__(level=logging.INFO)
        self.store = store

    def filter(self, record: logging.LogRecord) -> bool:
        return record.name.startswith("market_sentinel")

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.store.add_operational_log(
                record.levelname,
                record.getMessage(),
                int(record.created),
                component=record.name.removeprefix("market_sentinel.") or "core",
                event=getattr(record, "event", None),
            )
        except Exception:
            # Logging must never take the scanner down.
            self.handleError(record)
