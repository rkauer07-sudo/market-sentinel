import json
import os
import sqlite3
import time
from pathlib import Path
import httpx
from .models import Opportunity


class Store:
    def __init__(self, path: str):
        self.remote_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.remote_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        self.remote_bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "sentinel")
        self.remote_object = os.getenv("SUPABASE_DB_OBJECT", "sentinel.db")
        self.upload_remote = os.getenv("SYNC_DB_UPLOAD", "false").lower() in {"1", "true", "yes"}
        self.remote_error: str | None = None
        self.path = Path(path)
        if self.remote_url and self.remote_key:
            self.path = Path(os.getenv("SYNC_DB_LOCAL_PATH", "/tmp/market-sentinel.db"))
            try:
                self._download_remote()
            except Exception as exc:
                self.remote_error = f"{type(exc).__name__}: {exc}"
        self.last_remote_sync = time.time()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS alerts (
          fingerprint TEXT PRIMARY KEY, sent_at INTEGER NOT NULL, candle_timestamp INTEGER NOT NULL,
          venue TEXT NOT NULL, symbol TEXT NOT NULL, timeframe TEXT NOT NULL, score INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS runs (
          started_at INTEGER NOT NULL, finished_at INTEGER, markets INTEGER DEFAULT 0,
          opportunities INTEGER DEFAULT 0, errors INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS signals (
          id INTEGER PRIMARY KEY AUTOINCREMENT, signal_key TEXT UNIQUE NOT NULL,
          fingerprint TEXT NOT NULL, venue TEXT NOT NULL, symbol TEXT NOT NULL,
          asset_class TEXT NOT NULL, market_type TEXT NOT NULL, timeframe TEXT NOT NULL,
          direction TEXT NOT NULL, setup TEXT NOT NULL, entry REAL NOT NULL, stop REAL NOT NULL,
          target1 REAL NOT NULL, target2 REAL, risk_reward REAL NOT NULL, score INTEGER NOT NULL,
          opened_at INTEGER NOT NULL, candle_timestamp INTEGER NOT NULL, status TEXT NOT NULL,
          closed_at INTEGER, close_price REAL, resolution_reason TEXT,
          max_favorable_pct REAL DEFAULT 0, max_adverse_pct REAL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status, opened_at DESC);
        CREATE TABLE IF NOT EXISTS signal_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT, signal_id INTEGER NOT NULL,
          created_at INTEGER NOT NULL, event_type TEXT NOT NULL, message TEXT NOT NULL,
          price REAL, FOREIGN KEY(signal_id) REFERENCES signals(id)
        );
        CREATE TABLE IF NOT EXISTS candidate_snapshots (
          id INTEGER PRIMARY KEY CHECK (id=1), updated_at INTEGER NOT NULL, payload_json TEXT NOT NULL
        );
        """)
        self._ensure_column("signals", "reasons_json", "TEXT NOT NULL DEFAULT '[]'")
        self._ensure_column("signals", "risks_json", "TEXT NOT NULL DEFAULT '[]'")
        self._ensure_column("signals", "score_breakdown_json", "TEXT NOT NULL DEFAULT '{}'")
        self._ensure_column("signals", "confirmation_count", "INTEGER NOT NULL DEFAULT 0")
        self.db.commit()

    def save_candidates(self, candidates):
        payload = [{
            "venue": c.market.venue, "symbol": c.market.symbol,
            "asset_class": c.market.asset_class.value, "timeframe": c.timeframe,
            "direction": c.direction, "scenario": c.scenario,
            "trigger_price": c.trigger_price, "invalidation_price": c.invalidation_price,
            "target": c.target, "readiness": c.readiness, "conditions": c.conditions,
            "risks": c.risks, "candle_timestamp": c.candle_timestamp,
        } for c in candidates]
        self.db.execute("""INSERT INTO candidate_snapshots(id,updated_at,payload_json) VALUES(1,?,?)
            ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at,payload_json=excluded.payload_json""",
            (int(time.time()), json.dumps(payload, ensure_ascii=False)))
        self.db.commit()

    def candidates(self) -> list[dict]:
        row = self.db.execute("SELECT payload_json FROM candidate_snapshots WHERE id=1").fetchone()
        return json.loads(row[0]) if row else []

    def snapshot_updated_at(self) -> int | None:
        row = self.db.execute("SELECT updated_at FROM candidate_snapshots WHERE id=1").fetchone()
        return row[0] if row else None

    def should_send(self, op: Opportunity, cooldown_hours: int) -> bool:
        row = self.db.execute("SELECT sent_at, candle_timestamp FROM alerts WHERE fingerprint=?", (op.fingerprint,)).fetchone()
        if not row: return True
        return op.candle_timestamp > row[1] and int(time.time()) - row[0] >= cooldown_hours * 3600

    def mark_sent(self, op: Opportunity):
        self.db.execute("""INSERT INTO alerts VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(fingerprint) DO UPDATE SET sent_at=excluded.sent_at,
            candle_timestamp=excluded.candle_timestamp, score=excluded.score""",
            (op.fingerprint, int(time.time()), op.candle_timestamp, op.market.venue,
             op.market.symbol, op.timeframe, op.score))
        self.db.commit()

    def register_signal(self, op: Opportunity) -> tuple[int, bool]:
        active = self.db.execute("""SELECT id FROM signals WHERE venue=? AND symbol=? AND timeframe=?
            AND direction=? AND status='ACTIVE'""", (op.market.venue, op.market.symbol, op.timeframe, op.direction)).fetchone()
        if active: return active[0], False
        key = f"{op.fingerprint}:{op.candle_timestamp}"
        cursor = self.db.execute("""INSERT OR IGNORE INTO signals
            (signal_key,fingerprint,venue,symbol,asset_class,market_type,timeframe,direction,setup,
             entry,stop,target1,target2,risk_reward,score,opened_at,candle_timestamp,status,reasons_json,risks_json,
             score_breakdown_json,confirmation_count)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'ACTIVE',?,?,?,?)""",
            (key, op.fingerprint, op.market.venue, op.market.symbol, op.market.asset_class.value,
             op.market.market_type, op.timeframe, op.direction, op.setup, op.entry, op.stop,
             op.target1, op.target2, op.risk_reward, op.score, int(time.time()), op.candle_timestamp,
             json.dumps(op.reasons, ensure_ascii=False), json.dumps(op.risks, ensure_ascii=False),
             json.dumps(op.score_breakdown, ensure_ascii=False), op.confirmation_count))
        if not cursor.rowcount:
            row = self.db.execute("SELECT id FROM signals WHERE signal_key=?", (key,)).fetchone()
            return row[0], False
        signal_id = cursor.lastrowid
        self._event(signal_id, "CREATED", f"Oportunidade registrada: {op.setup}", op.entry)
        self.db.commit()
        return signal_id, True

    def reconcile(self, market, timeframe: str, candles, expiry_bars: int) -> list[dict]:
        columns = self._signal_columns()
        rows = self.db.execute("""SELECT * FROM signals WHERE venue=? AND symbol=?
            AND timeframe=? AND status='ACTIVE'""", (market.venue, market.symbol, timeframe)).fetchall()
        resolutions = []
        for values in rows:
            signal = dict(zip(columns, values))
            observed = [c for c in candles[:-1] if c.timestamp >= signal["candle_timestamp"]]
            if not observed: continue
            entry = signal["entry"]
            status = reason = price = None
            used = observed
            for index, candle in enumerate(observed):
                if signal["direction"] == "LONG":
                    stop_hit = candle.low <= signal["stop"]
                    target2_hit = signal["target2"] is not None and candle.high >= signal["target2"]
                    target1_hit = candle.high >= signal["target1"]
                else:
                    stop_hit = candle.high >= signal["stop"]
                    target2_hit = signal["target2"] is not None and candle.low <= signal["target2"]
                    target1_hit = candle.low <= signal["target1"]
                # OHLC cannot reveal intrabar ordering, so a bar touching both is scored conservatively.
                if stop_hit:
                    status, price = "FAILED", signal["stop"]
                    reason = "Stop/invalidação atingido antes de confirmação inequívoca do alvo"
                elif target2_hit:
                    status, price = "SUCCESS_T2", signal["target2"]
                    reason = "Segundo alvo atingido; oportunidade plenamente concretizada"
                elif target1_hit:
                    status, price = "SUCCESS_T1", signal["target1"]
                    reason = "Primeiro alvo atingido; oportunidade concretizada"
                if status:
                    used = observed[:index + 1]
                    break
            if signal["direction"] == "LONG":
                favorable = (max(c.high for c in used) - entry) / entry * 100
                adverse = (entry - min(c.low for c in used)) / entry * 100
            else:
                favorable = (entry - min(c.low for c in used)) / entry * 100
                adverse = (max(c.high for c in used) - entry) / entry * 100
            self.db.execute("UPDATE signals SET max_favorable_pct=?, max_adverse_pct=? WHERE id=?",
                            (max(favorable, signal["max_favorable_pct"]), max(adverse, signal["max_adverse_pct"]), signal["id"]))
            if not status and len(observed) >= expiry_bars:
                status, price = "EXPIRED", observed[-1].close
                reason = f"Expirada após {expiry_bars} candles sem atingir alvo ou stop"
            if status:
                self.db.execute("""UPDATE signals SET status=?,closed_at=?,close_price=?,resolution_reason=? WHERE id=?""",
                                (status, int(time.time()), price, reason, signal["id"]))
                self._event(signal["id"], status, reason, price)
                signal.update(status=status, closed_at=int(time.time()), close_price=price,
                              resolution_reason=reason, max_favorable_pct=max(favorable, signal["max_favorable_pct"]),
                              max_adverse_pct=max(adverse, signal["max_adverse_pct"]))
                resolutions.append(signal)
        self.db.commit()
        return resolutions

    def signals(self, status: str | None = None, limit: int = 200) -> list[dict]:
        columns = self._signal_columns()
        if status:
            rows = self.db.execute("SELECT * FROM signals WHERE status=? ORDER BY opened_at DESC LIMIT ?", (status, limit)).fetchall()
        else:
            rows = self.db.execute("SELECT * FROM signals ORDER BY opened_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._decode_signal(dict(zip(columns, row))) for row in rows]

    def signal(self, signal_id: int) -> dict | None:
        columns = self._signal_columns()
        row = self.db.execute("SELECT * FROM signals WHERE id=?", (signal_id,)).fetchone()
        return self._decode_signal(dict(zip(columns, row))) if row else None

    def events(self, limit: int = 300) -> list[dict]:
        rows = self.db.execute("""SELECT e.id,e.signal_id,e.created_at,e.event_type,e.message,e.price,
            s.venue,s.symbol,s.timeframe,s.direction FROM signal_events e JOIN signals s ON s.id=e.signal_id
            ORDER BY e.created_at DESC,e.id DESC LIMIT ?""", (limit,)).fetchall()
        keys = ["id","signal_id","created_at","event_type","message","price","venue","symbol","timeframe","direction"]
        return [dict(zip(keys, row)) for row in rows]

    def signal_stats(self) -> dict:
        rows = self.db.execute("SELECT status,COUNT(*) FROM signals GROUP BY status").fetchall()
        counts = dict(rows); resolved = sum(v for k, v in counts.items() if k != "ACTIVE")
        wins = counts.get("SUCCESS_T1", 0) + counts.get("SUCCESS_T2", 0)
        return {"counts": counts, "resolved": resolved, "wins": wins,
                "success_rate": round(wins / resolved * 100, 1) if resolved else None}

    def _event(self, signal_id: int, event_type: str, message: str, price: float | None = None):
        self.db.execute("INSERT INTO signal_events(signal_id,created_at,event_type,message,price) VALUES(?,?,?,?,?)",
                        (signal_id, int(time.time()), event_type, message, price))

    def _signal_columns(self):
        return [row[1] for row in self.db.execute("PRAGMA table_info(signals)").fetchall()]

    def _decode_signal(self, signal: dict) -> dict:
        signal["reasons"] = json.loads(signal.pop("reasons_json", "[]") or "[]")
        signal["risks"] = json.loads(signal.pop("risks_json", "[]") or "[]")
        signal["score_breakdown"] = json.loads(signal.pop("score_breakdown_json", "{}") or "{}")
        return signal

    def _ensure_column(self, table: str, column: str, definition: str):
        columns = {row[1] for row in self.db.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            self.db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _remote_object_url(self):
        return f"{self.remote_url}/storage/v1/object/{self.remote_bucket}/{self.remote_object}"

    def _remote_headers(self):
        headers = {"apikey": self.remote_key}
        # New sb_secret_* keys are opaque API keys and are rejected as Bearer
        # JWTs. Legacy service_role JWTs still require Authorization.
        if not self.remote_key.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {self.remote_key}"
        return headers

    def _download_remote(self):
        response = httpx.get(self._remote_object_url(), headers=self._remote_headers(), timeout=30)
        if response.status_code == 404:
            return
        response.raise_for_status()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not response.content.startswith(b"SQLite format 3"):
            raise RuntimeError("O objeto baixado do Supabase não é um banco SQLite válido")
        temporary = self.path.with_suffix(".download")
        temporary.write_bytes(response.content)
        temporary.replace(self.path)
        self.remote_error = None

    def _upload_remote(self):
        response = httpx.post(self._remote_object_url(), headers={**self._remote_headers(), "x-upsert": "true",
            "Content-Type": "application/octet-stream"}, content=self.path.read_bytes(), timeout=60)
        response.raise_for_status()

    def sync_from_remote(self):
        if not self.remote_url or not self.remote_key or self.upload_remote or time.time() - self.last_remote_sync < 30:
            return
        self.db.close()
        try:
            self._download_remote()
        except Exception as exc:
            self.remote_error = f"{type(exc).__name__}: {exc}"
        finally:
            self.db = sqlite3.connect(self.path, check_same_thread=False)
            self.last_remote_sync = time.time()

    def close(self):
        self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self.db.close()
        if self.upload_remote and self.remote_url and self.remote_key:
            self._upload_remote()
