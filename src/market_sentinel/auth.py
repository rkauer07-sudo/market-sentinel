from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time


ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


def normalize_address(value: str) -> str:
    value = str(value or "").strip()
    if not ADDRESS_RE.fullmatch(value):
        raise ValueError("Endereço de carteira inválido")
    return value.lower()


def new_wallet_challenge(address: str, host: str) -> tuple[str, str, int]:
    address = normalize_address(address)
    host = re.sub(r"[^a-zA-Z0-9.:-]", "", str(host))[:255] or "market-sentinel"
    nonce = secrets.token_urlsafe(24)
    expires_at = int(time.time()) + 5 * 60
    message = (
        "Market Sentinel\n\n"
        "Assine para entrar. Esta assinatura não envia transações nem concede acesso aos seus fundos.\n\n"
        f"Domínio: {host}\nCarteira: {address}\nNonce: {nonce}\nExpira em: {expires_at}"
    )
    return nonce, message, expires_at


def recover_address(message: str, signature: str) -> str:
    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct
    except ImportError as exc:  # pragma: no cover - dependency guard for partial installs
        raise RuntimeError("Dependência Web3 não instalada") from exc
    recovered = Account.recover_message(encode_defunct(text=message), signature=signature)
    return normalize_address(recovered)


def create_session(address: str, secret: str, max_age: int = 30 * 24 * 3600) -> str:
    payload = json.dumps({"sub": normalize_address(address), "exp": int(time.time()) + max_age},
                         separators=(",", ":")).encode()
    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=")
    signature = hmac.new(secret.encode(), encoded, hashlib.sha256).digest()
    return f"{encoded.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def read_session(token: str | None, secret: str) -> str | None:
    try:
        encoded, supplied = str(token or "").split(".", 1)
        expected = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).digest()
        supplied_bytes = base64.urlsafe_b64decode(supplied + "=" * (-len(supplied) % 4))
        if not hmac.compare_digest(expected, supplied_bytes):
            return None
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if int(payload["exp"]) < int(time.time()):
            return None
        return normalize_address(payload["sub"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
