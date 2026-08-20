from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import httpx


class SocialUnavailable(RuntimeError):
    pass


class SocialStore:
    """Wallet identities and chat backed by SQLite locally or Supabase PostgREST."""

    def __init__(self, store):
        self.store = store
        self.remote = bool(store.remote_url and store.remote_key)
        if not self.remote:
            self._ensure_local_schema()

    @property
    def backend(self) -> str:
        return "supabase" if self.remote else "sqlite"

    def _ensure_local_schema(self) -> None:
        self.store.db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
          wallet_address TEXT PRIMARY KEY, display_name TEXT,
          plan TEXT NOT NULL DEFAULT 'free', subscription_status TEXT NOT NULL DEFAULT 'inactive',
          subscription_provider TEXT, external_customer_id TEXT, current_period_end INTEGER,
          created_at INTEGER NOT NULL, last_login_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS auth_nonces (
          nonce_hash TEXT PRIMARY KEY, wallet_address TEXT NOT NULL, message TEXT NOT NULL,
          expires_at INTEGER NOT NULL, used_at INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_auth_nonces_wallet ON auth_nonces(wallet_address, expires_at DESC);
        CREATE TABLE IF NOT EXISTS chat_messages (
          id INTEGER PRIMARY KEY AUTOINCREMENT, wallet_address TEXT NOT NULL,
          body TEXT NOT NULL, created_at INTEGER NOT NULL, deleted_at INTEGER,
          FOREIGN KEY(wallet_address) REFERENCES users(wallet_address)
        );
        CREATE INDEX IF NOT EXISTS idx_chat_messages_created ON chat_messages(id DESC);
        """)
        self.store.db.commit()

    def _headers(self, prefer: str | None = None) -> dict[str, str]:
        headers = {**self.store._remote_headers(), "Content-Type": "application/json"}
        if prefer:
            headers["Prefer"] = prefer
        return headers

    def _request(self, method: str, table: str, *, params: dict | None = None,
                 payload: Any = None, prefer: str | None = None) -> Any:
        try:
            response = httpx.request(
                method, f"{self.store.remote_url}/rest/v1/{table}", params=params,
                json=payload, headers=self._headers(prefer), timeout=15,
            )
        except httpx.HTTPError as exc:
            raise SocialUnavailable(f"Banco social indisponível: {exc}") from exc
        if response.is_error:
            detail = response.text[:300]
            if response.status_code in {404, 406} or "PGRST" in detail:
                raise SocialUnavailable(
                    "Tabelas sociais não configuradas no Supabase; aplique supabase_social.sql"
                )
            raise SocialUnavailable(f"Supabase social respondeu HTTP {response.status_code}: {detail}")
        if not response.content:
            return None
        return response.json()

    @staticmethod
    def _nonce_hash(nonce: str) -> str:
        return hashlib.sha256(nonce.encode()).hexdigest()

    def save_challenge(self, address: str, nonce: str, message: str, expires_at: int) -> None:
        nonce_hash = self._nonce_hash(nonce)
        if self.remote:
            self._request("POST", "sentinel_auth_nonces", payload={
                "nonce_hash": nonce_hash, "wallet_address": address, "message": message,
                "expires_at": expires_at,
            }, prefer="return=minimal")
            return
        self.store.db.execute("DELETE FROM auth_nonces WHERE expires_at < ? OR used_at IS NOT NULL",
                              (int(time.time()) - 3600,))
        self.store.db.execute("""INSERT INTO auth_nonces
            (nonce_hash,wallet_address,message,expires_at,used_at) VALUES(?,?,?,?,NULL)""",
            (nonce_hash, address, message, expires_at))
        self.store.db.commit()

    def challenge_message(self, address: str, nonce: str) -> str | None:
        nonce_hash, now = self._nonce_hash(nonce), int(time.time())
        if self.remote:
            rows = self._request("GET", "sentinel_auth_nonces", params={
                "select": "message", "nonce_hash": f"eq.{nonce_hash}",
                "wallet_address": f"eq.{address}", "used_at": "is.null",
                "expires_at": f"gt.{now}", "limit": "1",
            })
            return rows[0]["message"] if rows else None
        row = self.store.db.execute("""SELECT message FROM auth_nonces WHERE nonce_hash=?
            AND wallet_address=? AND used_at IS NULL AND expires_at>?""",
            (nonce_hash, address, now)).fetchone()
        return row[0] if row else None

    def consume_challenge(self, address: str, nonce: str) -> bool:
        nonce_hash, now = self._nonce_hash(nonce), int(time.time())
        if self.remote:
            rows = self._request("PATCH", "sentinel_auth_nonces", params={
                "nonce_hash": f"eq.{nonce_hash}", "wallet_address": f"eq.{address}",
                "used_at": "is.null", "expires_at": f"gt.{now}",
            }, payload={"used_at": now}, prefer="return=representation")
            return bool(rows)
        cursor = self.store.db.execute("""UPDATE auth_nonces SET used_at=? WHERE nonce_hash=?
            AND wallet_address=? AND used_at IS NULL AND expires_at>?""",
            (now, nonce_hash, address, now))
        self.store.db.commit()
        return cursor.rowcount == 1

    def upsert_user(self, address: str) -> dict:
        now = int(time.time())
        if self.remote:
            rows = self._request("POST", "sentinel_users", params={"on_conflict": "wallet_address"},
                payload={"wallet_address": address, "last_login_at": now},
                prefer="resolution=merge-duplicates,return=representation")
            return rows[0]
        self.store.db.execute("""INSERT INTO users(wallet_address,created_at,last_login_at)
            VALUES(?,?,?) ON CONFLICT(wallet_address) DO UPDATE SET last_login_at=excluded.last_login_at""",
            (address, now, now))
        self.store.db.commit()
        return self.user(address) or {"wallet_address": address, "plan": "free",
                                      "subscription_status": "inactive"}

    def user(self, address: str) -> dict | None:
        fields = ("wallet_address", "display_name", "plan", "subscription_status",
                  "subscription_provider", "external_customer_id", "current_period_end",
                  "created_at", "last_login_at")
        if self.remote:
            rows = self._request("GET", "sentinel_users", params={
                "select": ",".join(fields), "wallet_address": f"eq.{address}", "limit": "1"})
            return rows[0] if rows else None
        row = self.store.db.execute(f"SELECT {','.join(fields)} FROM users WHERE wallet_address=?",
                                    (address,)).fetchone()
        return dict(zip(fields, row)) if row else None

    def messages(self, after_id: int = 0, limit: int = 100) -> list[dict]:
        limit = max(1, min(int(limit), 100))
        if self.remote:
            rows = self._request("GET", "sentinel_chat_messages", params={
                "select": "id,wallet_address,body,created_at", "deleted_at": "is.null",
                "id": f"gt.{max(0, int(after_id))}", "order": "id.asc", "limit": str(limit),
            })
            return rows or []
        rows = self.store.db.execute("""SELECT id,wallet_address,body,created_at FROM chat_messages
            WHERE deleted_at IS NULL AND id>? ORDER BY id ASC LIMIT ?""",
            (max(0, int(after_id)), limit)).fetchall()
        return [dict(zip(("id", "wallet_address", "body", "created_at"), row)) for row in rows]

    def add_message(self, address: str, body: str) -> dict:
        body = " ".join(str(body).split())
        if not body or len(body) > 500:
            raise ValueError("A mensagem deve ter entre 1 e 500 caracteres")
        now = int(time.time())
        if self.remote:
            recent = self._request("GET", "sentinel_chat_messages", params={
                "select": "created_at", "wallet_address": f"eq.{address}",
                "order": "id.desc", "limit": "1",
            })
            if recent and now - int(recent[0]["created_at"]) < 2:
                raise ValueError("Aguarde dois segundos antes de enviar outra mensagem")
            rows = self._request("POST", "sentinel_chat_messages", payload={
                "wallet_address": address, "body": body, "created_at": now,
            }, prefer="return=representation")
            return rows[0]
        recent = self.store.db.execute("""SELECT created_at FROM chat_messages
            WHERE wallet_address=? ORDER BY id DESC LIMIT 1""", (address,)).fetchone()
        if recent and now - int(recent[0]) < 2:
            raise ValueError("Aguarde dois segundos antes de enviar outra mensagem")
        cursor = self.store.db.execute("""INSERT INTO chat_messages(wallet_address,body,created_at)
            VALUES(?,?,?)""", (address, body, now))
        self.store.db.commit()
        return {"id": cursor.lastrowid, "wallet_address": address, "body": body, "created_at": now}
