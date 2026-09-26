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
        CREATE TABLE IF NOT EXISTS vip_payments (
          reference TEXT PRIMARY KEY, wallet_address TEXT NOT NULL, memo TEXT NOT NULL,
          amount_usdc REAL NOT NULL, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending', signature TEXT UNIQUE, paid_at INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_vip_payments_wallet ON vip_payments(wallet_address, created_at DESC);
        """)
        # Códigos de desconto (criados manualmente no banco) + feedback/contato.
        self.store._run_script("""
        CREATE TABLE IF NOT EXISTS discount_codes (
          code TEXT PRIMARY KEY, percent INTEGER NOT NULL CHECK (percent BETWEEN 5 AND 100),
          active INTEGER NOT NULL DEFAULT 1, max_uses INTEGER, expires_at INTEGER,
          note TEXT, created_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS discount_redemptions (
          code TEXT NOT NULL, wallet_address TEXT NOT NULL, reference TEXT NOT NULL,
          redeemed_at INTEGER NOT NULL, PRIMARY KEY (code, wallet_address)
        );
        CREATE TABLE IF NOT EXISTS feedback_messages (
          id INTEGER PRIMARY KEY AUTOINCREMENT, wallet_address TEXT, contact TEXT,
          body TEXT NOT NULL, created_at INTEGER NOT NULL, read_at INTEGER, client_hash TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback_messages(id DESC);
        CREATE INDEX IF NOT EXISTS idx_feedback_client ON feedback_messages(client_hash, created_at DESC)
        """)
        self.store._ensure_column("vip_payments", "base_amount_usdc", "REAL")
        self.store._ensure_column("vip_payments", "discount_code", "TEXT")
        self.store._ensure_column("vip_payments", "discount_percent", "INTEGER NOT NULL DEFAULT 0")
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
        self.store.db.execute("""UPDATE auth_nonces SET used_at=? WHERE nonce_hash=?
            AND wallet_address=? AND used_at IS NULL AND expires_at>?""",
            (now, nonce_hash, address, now))
        # changes() é portável entre sqlite3 e libsql/Turso (rowcount não é).
        changed = self.store.db.execute("SELECT changes()").fetchone()[0]
        self.store.db.commit()
        return changed == 1

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

    def users(self, addresses) -> dict[str, dict]:
        """Batch lookup used to decorate chat messages (VIP highlight)."""
        addresses = sorted({str(a) for a in addresses if a})
        if not addresses:
            return {}
        fields = ("wallet_address", "plan", "current_period_end")
        if self.remote:
            rows = self._request("GET", "sentinel_users", params={
                "select": ",".join(fields),
                "wallet_address": f"in.({','.join(addresses)})"}) or []
            return {row["wallet_address"]: row for row in rows}
        marks = ",".join("?" * len(addresses))
        rows = self.store.db.execute(
            f"SELECT {','.join(fields)} FROM users WHERE wallet_address IN ({marks})",
            tuple(addresses)).fetchall()
        return {row[0]: dict(zip(fields, row)) for row in rows}

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
        self.store.db.execute("""INSERT INTO chat_messages(wallet_address,body,created_at)
            VALUES(?,?,?)""", (address, body, now))
        message_id = int(self.store.db.execute("SELECT last_insert_rowid()").fetchone()[0])
        self.store.db.commit()
        return {"id": message_id, "wallet_address": address, "body": body, "created_at": now}

    # ------------------------------------------------------------ VIP payments
    _payment_fields = ("reference", "wallet_address", "memo", "amount_usdc", "created_at",
                       "expires_at", "status", "signature", "paid_at", "base_amount_usdc",
                       "discount_code", "discount_percent")

    def save_payment_intent(self, intent: dict) -> None:
        row = {key: intent.get(key) for key in self._payment_fields}
        if self.remote:
            self._request("POST", "sentinel_vip_payments", payload=row, prefer="return=minimal")
            return
        self.store.db.execute(
            f"INSERT INTO vip_payments({','.join(self._payment_fields)}) VALUES({','.join('?' * len(row))})",
            tuple(row.values()))
        self.store.db.commit()

    def _payment_where(self, column: str, value: str) -> dict | None:
        if self.remote:
            rows = self._request("GET", "sentinel_vip_payments", params={
                "select": ",".join(self._payment_fields), column: f"eq.{value}", "limit": "1"})
            return rows[0] if rows else None
        row = self.store.db.execute(
            f"SELECT {','.join(self._payment_fields)} FROM vip_payments WHERE {column}=?",
            (value,)).fetchone()
        return dict(zip(self._payment_fields, row)) if row else None

    def payment_intent(self, reference: str) -> dict | None:
        return self._payment_where("reference", reference)

    def payment_by_signature(self, signature: str) -> dict | None:
        return self._payment_where("signature", signature)

    def mark_payment_paid(self, reference: str, signature: str, paid_at: int) -> bool:
        """Atomically flip pending -> paid; the UNIQUE signature blocks reuse."""
        if self.remote:
            try:
                rows = self._request("PATCH", "sentinel_vip_payments", params={
                    "reference": f"eq.{reference}", "status": "eq.pending"},
                    payload={"status": "paid", "signature": signature, "paid_at": paid_at},
                    prefer="return=representation")
            except SocialUnavailable as exc:
                if "23505" in str(exc) or "duplicate" in str(exc).lower():
                    return False
                raise
            return bool(rows)
        try:
            self.store.db.execute(
                "UPDATE vip_payments SET status='paid', signature=?, paid_at=? "
                "WHERE reference=? AND status='pending'", (signature, paid_at, reference))
        except Exception as exc:  # sqlite3 / libsql IntegrityError
            if "UNIQUE" in str(exc).upper():
                return False
            raise
        changed = self.store.db.execute("SELECT changes()").fetchone()[0]
        self.store.db.commit()
        return changed == 1

    def _local_only(self, feature: str) -> None:
        if self.remote:
            raise SocialUnavailable(f"{feature} exige o banco Turso/SQLite (Supabase foi descontinuado)")

    # --------------------------------------------------------- discount codes
    @staticmethod
    def normalize_code(code: str) -> str:
        return "".join(str(code or "").split()).upper()[:64]

    def discount_code(self, code: str) -> dict | None:
        """Row of an existing code (any state); matching is case-insensitive."""
        self._local_only("Códigos de desconto")
        code = self.normalize_code(code)
        if not code:
            return None
        fields = ("code", "percent", "active", "max_uses", "expires_at")
        row = self.store.db.execute(
            f"SELECT {','.join(fields)} FROM discount_codes WHERE UPPER(code)=?", (code,)).fetchone()
        return dict(zip(fields, row)) if row else None

    def discount_uses(self, code: str) -> int:
        row = self.store.db.execute("SELECT COUNT(*) FROM discount_redemptions WHERE code=?",
                                    (code,)).fetchone()
        return int(row[0] if row else 0)

    def discount_used_by(self, code: str, address: str) -> bool:
        return self.store.db.execute(
            "SELECT 1 FROM discount_redemptions WHERE code=? AND wallet_address=?",
            (code, address)).fetchone() is not None

    def redeem_discount(self, code: str, address: str, reference: str) -> bool:
        """Records the use; False when this wallet had already used the code."""
        self._local_only("Códigos de desconto")
        try:
            self.store.db.execute("""INSERT INTO discount_redemptions
                (code,wallet_address,reference,redeemed_at) VALUES(?,?,?,?)""",
                (code, address, reference, int(time.time())))
        except Exception as exc:  # sqlite3 / libsql IntegrityError
            if "UNIQUE" in str(exc).upper() or "PRIMARY" in str(exc).upper():
                return False
            raise
        self.store.db.commit()
        return True

    # ------------------------------------------------------- feedback/contact
    _feedback_fields = ("id", "wallet_address", "contact", "body", "created_at", "read_at")

    def add_feedback(self, body: str, contact: str | None, address: str | None,
                     client_hash: str) -> dict:
        self._local_only("Feedback")
        body = str(body or "").strip()
        contact = " ".join(str(contact or "").split())[:200] or None
        if len(body) < 3 or len(body) > 2000:
            raise ValueError("A mensagem deve ter entre 3 e 2000 caracteres")
        now = int(time.time())
        recent = self.store.db.execute(
            "SELECT COUNT(*), MAX(created_at) FROM feedback_messages WHERE client_hash=? AND created_at>?",
            (client_hash, now - 3600)).fetchone()
        if recent and int(recent[0] or 0) >= 5:
            raise ValueError("Limite de mensagens atingido. Tente novamente em uma hora.")
        if recent and recent[1] and now - int(recent[1]) < 20:
            raise ValueError("Aguarde alguns segundos antes de enviar outra mensagem")
        self.store.db.execute("""INSERT INTO feedback_messages
            (wallet_address,contact,body,created_at,client_hash) VALUES(?,?,?,?,?)""",
            (address, contact, body, now, client_hash))
        message_id = int(self.store.db.execute("SELECT last_insert_rowid()").fetchone()[0])
        self.store.db.commit()
        return {"id": message_id, "created_at": now}

    def feedback(self, limit: int = 200) -> list[dict]:
        self._local_only("Feedback")
        rows = self.store.db.execute(
            f"SELECT {','.join(self._feedback_fields)} FROM feedback_messages ORDER BY id DESC LIMIT ?",
            (max(1, min(int(limit), 500)),)).fetchall()
        return [dict(zip(self._feedback_fields, row)) for row in rows]

    def mark_feedback_read(self, message_id: int, read: bool = True) -> None:
        self._local_only("Feedback")
        self.store.db.execute("UPDATE feedback_messages SET read_at=? WHERE id=?",
                              (int(time.time()) if read else None, int(message_id)))
        self.store.db.commit()

    def extend_vip(self, address: str, seconds: int, provider: str = "solana_usdc") -> dict:
        now = int(time.time())
        current = self.user(address) or {}
        start = max(now, int(current.get("current_period_end") or 0))
        fields = {"plan": "vip", "subscription_status": "active",
                  "subscription_provider": provider, "current_period_end": start + seconds}
        if self.remote:
            rows = self._request("PATCH", "sentinel_users", params={
                "wallet_address": f"eq.{address}"}, payload=fields, prefer="return=representation")
            return rows[0] if rows else {**current, **fields}
        self.store.db.execute(
            "UPDATE users SET plan=?, subscription_status=?, subscription_provider=?, "
            "current_period_end=? WHERE wallet_address=?", (*fields.values(), address))
        self.store.db.commit()
        return self.user(address) or {**current, **fields}
