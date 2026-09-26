"""VIP access paid with USDC on Solana through the Market Sentinel program.

Flow
----
1. A logged-in user asks for a payment intent, optionally with a discount code
   (table ``discount_codes``, created by hand in the database: 5–100 %, one use
   per wallet). We mint a random 32-byte ``reference`` public key and a memo and
   persist them with the discounted amount. A 100 % code grants VIP right away.
2. The wallet signs a transaction that calls the on-chain program
   ``VIP_PROGRAM_ID`` (contracts/vip-payment), which checks the destination is
   the treasury's USDC account and forwards the amount (``TransferChecked``).
   The reference rides along as a read-only account for lookup.
3. The backend finds the transaction with ``getSignaturesForAddress(reference)``
   (or a pasted signature), re-validates everything on-chain — program invoked,
   amount received by ``VIP_TREASURY_WALLET`` — and extends the VIP period by
   ``VIP_DAYS``. A signature can be redeemed only once.

When ``VIP_PROGRAM_ID`` is not set, plain USDC transfers are accepted (legacy).

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
        # Tolera espaços/aspas coladas por engano no painel do Vercel.
        self.treasury = os.getenv("VIP_TREASURY_WALLET", "").strip().strip("'\"").strip()
        self.price = float(os.getenv("VIP_PRICE_USDC", "10"))
        self.days = int(os.getenv("VIP_DAYS", "31"))
        self.mint = os.getenv("VIP_USDC_MINT", USDC_MINT).strip()
        helius = os.getenv("HELIUS_API_KEY", "").strip()
        default_rpc = (f"https://mainnet.helius-rpc.com/?api-key={helius}" if helius
                       else "https://api.mainnet-beta.solana.com")
        self.rpc_url = os.getenv("SOLANA_RPC_URL", "").strip() or default_rpc
        self.intent_ttl = int(os.getenv("VIP_INTENT_TTL_SECONDS", str(24 * 3600)))
        self.program_id = os.getenv("VIP_PROGRAM_ID", "").strip().strip("'\"").strip()
        admins = os.getenv("VIP_ADMIN_WALLETS", "")
        self.admin_wallets = {x.strip() for x in admins.split(",") if x.strip()}

    # ------------------------------------------------------------------ config
    @property
    def enabled(self) -> bool:
        return is_solana_address(self.treasury)

    @property
    def amount_units(self) -> int:
        return self.units(self.price)

    @staticmethod
    def units(amount_usdc: float) -> int:
        return int(round(float(amount_usdc) * 10 ** USDC_DECIMALS))

    @property
    def contract(self) -> bool:
        return is_solana_address(self.program_id)

    @property
    def disabled_reason(self) -> str | None:
        if self.enabled:
            return None
        if not self.treasury:
            return "A variável VIP_TREASURY_WALLET não chegou ao servidor (ausente ou sem redeploy)."
        if self.treasury.startswith("0x"):
            return "VIP_TREASURY_WALLET contém um endereço EVM (0x…); use um endereço Solana."
        return "VIP_TREASURY_WALLET não é um endereço Solana válido."

    def public_config(self) -> dict:
        return {"enabled": self.enabled, "reason": self.disabled_reason,
                "price_usdc": self.price, "days": self.days,
                "treasury": self.treasury if self.enabled else None, "mint": self.mint,
                "program_id": self.program_id if self.contract else None,
                "contract": self.contract, "network": "solana"}

    def is_vip(self, user: dict | None) -> bool:
        if not user:
            return False
        if str(user.get("wallet_address", "")) in self.admin_wallets:
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
    def discount_for(self, wallet_address: str, code: str | None) -> dict | None:
        """Validate a discount code for this wallet. None when no code given."""
        if not str(code or "").strip():
            return None
        row = self.social.discount_code(code)
        now = int(time.time())
        if not row or not int(row.get("active") or 0):
            raise PaymentError("Código de desconto inválido")
        if row.get("expires_at") and int(row["expires_at"]) < now:
            raise PaymentError("Este código de desconto expirou")
        percent = int(row["percent"])
        if percent < 5 or percent > 100:
            raise PaymentError("Código de desconto inválido")
        if self.social.discount_used_by(row["code"], wallet_address):
            raise PaymentError("Você já usou este código de desconto")
        if row.get("max_uses") is not None and self.social.discount_uses(row["code"]) >= int(row["max_uses"]):
            raise PaymentError("Este código de desconto já atingiu o limite de usos")
        return {"code": row["code"], "percent": percent}

    def price_with(self, percent: int) -> float:
        units = self.amount_units * (100 - int(percent)) // 100
        return units / 10 ** USDC_DECIMALS

    def create_intent(self, wallet_address: str, code: str | None = None) -> dict:
        if not self.enabled:
            raise PaymentError("Pagamentos VIP ainda não configurados (VIP_TREASURY_WALLET)")
        discount = self.discount_for(wallet_address, code)
        percent = discount["percent"] if discount else 0
        amount = self.price_with(percent)
        reference = b58encode(secrets.token_bytes(32))
        memo = f"MS-VIP-{secrets.token_hex(4).upper()}"
        now = int(time.time())
        intent = {"reference": reference, "wallet_address": wallet_address, "memo": memo,
                  "amount_usdc": amount, "base_amount_usdc": self.price,
                  "discount_code": discount["code"] if discount else None,
                  "discount_percent": percent, "created_at": now,
                  "expires_at": now + self.intent_ttl, "status": "pending"}
        if amount <= 0:
            # 100 %: nada a pagar on-chain; libera na hora e consome o código.
            if not self.social.redeem_discount(discount["code"], wallet_address, reference):
                raise PaymentError("Você já usou este código de desconto")
            intent.update(status="paid", paid_at=now)
            self.social.save_payment_intent(intent)
            user = self.social.extend_vip(wallet_address, self.days * 86400, "discount_code")
            return {**intent, "user": user, "days": self.days}
        self.social.save_payment_intent(intent)
        return {**intent, **self.payment_request(reference, memo, amount)}

    def payment_request(self, reference: str, memo: str, amount: float | None = None) -> dict:
        from urllib.parse import quote
        amount = self.price if amount is None else amount
        price = f"{amount:g}"
        url = (f"solana:{self.treasury}?amount={price}&spl-token={self.mint}"
               f"&reference={reference}&label={quote('Market Sentinel')}"
               f"&message={quote(f'VIP {self.days} dias')}&memo={quote(memo)}")
        return {"solana_pay_url": None if self.contract else url, "treasury": self.treasury,
                "mint": self.mint, "program_id": self.program_id if self.contract else None,
                "contract": self.contract, "decimals": USDC_DECIMALS,
                "amount_units": self.units(amount), "days": self.days}

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
    def _program_ids(tx: dict) -> set[str]:
        message = (tx.get("transaction") or {}).get("message") or {}
        keys = [k.get("pubkey") if isinstance(k, dict) else k for k in message.get("accountKeys") or []]
        found = set()
        for ix in message.get("instructions") or []:
            if ix.get("programId"):
                found.add(ix["programId"])
            elif isinstance(ix.get("programIdIndex"), int) and ix["programIdIndex"] < len(keys):
                found.add(keys[ix["programIdIndex"]])
        return found

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
        if self.contract and self.program_id not in self._program_ids(tx):
            return "A transação não passou pelo contrato de pagamento do Market Sentinel"
        bound = intent["reference"] in self._account_keys(tx) or intent["memo"] in self._memos(tx)
        if not bound:
            return "A transação não contém a referência/memo deste pagamento"
        block_time = int(tx.get("blockTime") or 0)
        if block_time and block_time < int(intent["created_at"]) - 300:
            return "A transação é anterior a este pedido de pagamento"
        expected = float(intent.get("amount_usdc") or self.price)
        if self._treasury_delta(meta) < self.units(expected):
            return f"Valor recebido menor que {expected:g} USDC na carteira do projeto"
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
            if intent.get("discount_code"):
                # Pagou: consome o código (idempotente por carteira).
                self.social.redeem_discount(intent["discount_code"], wallet_address, reference)
            user = self.social.extend_vip(wallet_address, self.days * 86400)
            return {"status": "paid", "signature": candidate, "user": user}
        if not signature and int(intent["expires_at"]) < int(time.time()):
            return {"status": "expired", "reason": "Pedido expirado; gere um novo pagamento"}
        return {"status": "pending", "reason": reason}
