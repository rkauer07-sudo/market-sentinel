"""VIP access paid with USDC on Solana (Solana Pay "transfer request").

Flow
----
1. A logged-in user asks for a payment intent. We mint a random 32-byte
   ``reference`` public key and a short memo code and persist them.
2. The wallet pays ``VIP_PRICE_USDC`` USDC to ``VIP_TREASURY_WALLET`` with the
   reference attached as a read-only account key (Solana Pay spec) — either by
   scanning the QR / ``solana:`` link or through the in-page Phantom button.
3. The backend finds the transaction with ``getSignaturesForAddress(reference)``
   (or a pasted signature), re-validates everything on-chain and extends the
   user's VIP period by ``VIP_DAYS``. A signature can be redeemed only once.

Nothing here ever holds a private key: the server only reads the chain.
"""

from __future__ import annotations

import os
import secrets
import time
from typing import Any

import httpx

USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDC_DECIMALS = 6
_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58encode(raw: bytes) -> str:
    number = int.from_bytes(raw, "big")
    out = ""
    while number:
        number, rem = divmod(number, 58)
        out = _B58[rem] + out
    pad = len(raw) - len(raw.lstrip(b"\0"))
    return "1" * pad + out


def b58decode(value: str) -> bytes:
    number = 0
    for char in value:
        index = _B58.find(char)
        if index < 0:
            raise ValueError("base58 inválido")
        number = number * 58 + index
    body = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    pad = len(value) - len(value.lstrip("1"))
    return b"\0" * pad + body


def is_solana_address(value: str) -> bool:
    try:
        return len(b58decode(str(value or "").strip())) == 32
    except ValueError:
        return False


def is_signature(value: str) -> bool:
    try:
        return len(b58decode(str(value or "").strip())) == 64
    except ValueError:
        return False


class PaymentError(ValueError):
    pass


class VipPayments:
    def __init__(self, social):
        self.social = social
        self.treasury = os.getenv("VIP_TREASURY_WALLET", "").strip()
        self.price = float(os.getenv("VIP_PRICE_USDC", "10"))
        self.days = int(os.getenv("VIP_DAYS", "31"))
        self.mint = os.getenv("VIP_USDC_MINT", USDC_MINT).strip()
        helius = os.getenv("HELIUS_API_KEY", "").strip()
        default_rpc = (f"https://mainnet.helius-rpc.com/?api-key={helius}" if helius
                       else "https://api.mainnet-beta.solana.com")
        self.rpc_url = os.getenv("SOLANA_RPC_URL", "").strip() or default_rpc
        self.intent_ttl = int(os.getenv("VIP_INTENT_TTL_SECONDS", str(24 * 3600)))
        admins = os.getenv("VIP_ADMIN_WALLETS", "")
        self.admin_wallets = {x.strip().lower() for x in admins.split(",") if x.strip()}

    # ------------------------------------------------------------------ config
    @property
    def enabled(self) -> bool:
        return is_solana_address(self.treasury)

    @property
    def amount_units(self) -> int:
        return int(round(self.price * 10 ** USDC_DECIMALS))

    def public_config(self) -> dict:
        return {"enabled": self.enabled, "price_usdc": self.price, "days": self.days,
                "treasury": self.treasury if self.enabled else None, "mint": self.mint,
                "network": "solana"}

    def is_vip(self, user: dict | None) -> bool:
        if not user:
            return False
        if str(user.get("wallet_address", "")).lower() in self.admin_wallets:
            return True
        end = int(user.get("current_period_end") or 0)
        return user.get("plan") == "vip" and end > int(time.time())

    # ------------------------------------------------------------------- RPC
    def _rpc(self, method: str, params: list) -> Any:
        try:
            response = httpx.post(self.rpc_url, json={"jsonrpc": "2.0", "id": 1, "method": method,
                                                      "params": params}, timeout=20)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise PaymentError(f"RPC Solana indisponível: {exc}") from exc
        if data.get("error"):
            raise PaymentError(f"RPC Solana: {data['error'].get('message', data['error'])}")
        return data.get("result")

    def latest_blockhash(self) -> dict:
        result = self._rpc("getLatestBlockhash", [{"commitment": "confirmed"}])
        value = (result or {}).get("value") or {}
        return {"blockhash": value.get("blockhash"),
                "last_valid_block_height": value.get("lastValidBlockHeight")}

    # --------------------------------------------------------------- intents
    def create_intent(self, wallet_address: str) -> dict:
        if not self.enabled:
            raise PaymentError("Pagamentos VIP ainda não configurados (VIP_TREASURY_WALLET)")
        reference = b58encode(secrets.token_bytes(32))
        memo = f"MS-VIP-{secrets.token_hex(4).upper()}"
        now = int(time.time())
        intent = {"reference": reference, "wallet_address": wallet_address, "memo": memo,
                  "amount_usdc": self.price, "created_at": now,
                  "expires_at": now + self.intent_ttl, "status": "pending"}
        self.social.save_payment_intent(intent)
        return {**intent, **self.payment_request(reference, memo)}

    def payment_request(self, reference: str, memo: str) -> dict:
        from urllib.parse import quote
        price = f"{self.price:g}"
        url = (f"solana:{self.treasury}?amount={price}&spl-token={self.mint}"
               f"&reference={reference}&label={quote('Market Sentinel')}"
               f"&message={quote(f'VIP {self.days} dias')}&memo={quote(memo)}")
        return {"solana_pay_url": url, "treasury": self.treasury, "mint": self.mint,
                "decimals": USDC_DECIMALS, "amount_units": self.amount_units, "days": self.days}

    # ---------------------------------------------------------- verification
    def _treasury_delta(self, meta: dict) -> int:
        def total(rows):
            return sum(int(row.get("uiTokenAmount", {}).get("amount") or 0) for row in rows or []
                       if row.get("mint") == self.mint and row.get("owner") == self.treasury)
        return total(meta.get("postTokenBalances")) - total(meta.get("preTokenBalances"))

    @staticmethod
    def _account_keys(tx: dict) -> set[str]:
        message = (tx.get("transaction") or {}).get("message") or {}
        keys = set()
        for key in message.get("accountKeys") or []:
            keys.add(key.get("pubkey") if isinstance(key, dict) else key)
        loaded = (tx.get("meta") or {}).get("loadedAddresses") or {}
        keys.update(loaded.get("writable") or []); keys.update(loaded.get("readonly") or [])
        return keys

    @staticmethod
    def _memos(tx: dict) -> str:
        chunks = list((tx.get("meta") or {}).get("logMessages") or [])
        message = (tx.get("transaction") or {}).get("message") or {}
        for ix in message.get("instructions") or []:
            if ix.get("program") == "spl-memo" and isinstance(ix.get("parsed"), str):
                chunks.append(ix["parsed"])
        return "\n".join(chunks)

    def validate_transaction(self, tx: dict | None, intent: dict) -> str | None:
        """Return None when ``tx`` pays this intent, else a human reason."""
        if not tx:
            return "Transação ainda não encontrada/confirmada"
        meta = tx.get("meta") or {}
        if meta.get("err") is not None:
            return "A transação falhou na rede Solana"
        bound = intent["reference"] in self._account_keys(tx) or intent["memo"] in self._memos(tx)
        if not bound:
            return "A transação não contém a referência/memo deste pagamento"
        block_time = int(tx.get("blockTime") or 0)
        if block_time and block_time < int(intent["created_at"]) - 300:
            return "A transação é anterior a este pedido de pagamento"
        if self._treasury_delta(meta) < self.amount_units:
            return f"Valor recebido menor que {self.price:g} USDC na carteira do projeto"
        return None

    def _get_transaction(self, signature: str) -> dict | None:
        return self._rpc("getTransaction", [signature, {
            "encoding": "jsonParsed", "commitment": "confirmed",
            "maxSupportedTransactionVersion": 0}])

    def find_signatures(self, reference: str) -> list[str]:
        rows = self._rpc("getSignaturesForAddress", [reference, {"limit": 10,
                                                                 "commitment": "confirmed"}])
        return [row["signature"] for row in rows or [] if not row.get("err")]

    def verify(self, wallet_address: str, reference: str, signature: str | None = None) -> dict:
        intent = self.social.payment_intent(reference)
        if not intent or intent["wallet_address"] != wallet_address:
            raise PaymentError("Pedido de pagamento não encontrado para esta carteira")
        if intent["status"] == "paid":
            return {"status": "paid", "signature": intent.get("signature"),
                    "user": self.social.user(wallet_address)}
        if signature is not None and not is_signature(signature):
            raise PaymentError("Assinatura de transação inválida")
        candidates = [signature] if signature else self.find_signatures(reference)
        reason = "Pagamento ainda não detectado na rede"
        for candidate in candidates:
            if self.social.payment_by_signature(candidate):
                reason = "Esta transação já foi utilizada para liberar um VIP"
                continue
            reason = self.validate_transaction(self._get_transaction(candidate), intent) or ""
            if reason:
                continue
            if not self.social.mark_payment_paid(reference, candidate, int(time.time())):
                reason = "Esta transação já foi utilizada para liberar um VIP"
                continue
            user = self.social.extend_vip(wallet_address, self.days * 86400)
            return {"status": "paid", "signature": candidate, "user": user}
        if not signature and int(intent["expires_at"]) < int(time.time()):
            return {"status": "expired", "reason": "Pedido expirado; gere um novo pagamento"}
        return {"status": "pending", "reason": reason}
