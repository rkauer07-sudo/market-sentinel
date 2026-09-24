from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time


_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
ADDRESS_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


def _b58decode(value: str) -> bytes:
    number = 0
    for char in value:
        number = number * 58 + _B58.index(char)
    body = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    return b"\0" * (len(value) - len(value.lstrip("1"))) + body


def normalize_address(value: str) -> str:
    """Solana public key (base58, 32 bytes). Base58 is case-sensitive."""
    value = str(value or "").strip()
    if not ADDRESS_RE.fullmatch(value) or len(_b58decode(value)) != 32:
        raise ValueError("Endereço de carteira Solana inválido")
    return value


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


def _signature_bytes(signature: str) -> bytes:
    signature = str(signature or "").strip()
    if re.fullmatch(r"(0x)?[0-9a-fA-F]{128}", signature):
        return bytes.fromhex(signature.removeprefix("0x"))
    try:
        raw = _b58decode(signature)
    except ValueError:
        raw = b""
    if len(raw) == 64:
        return raw
    try:
        raw = base64.b64decode(signature, validate=True)
    except (ValueError, TypeError):
        raw = b""
    if len(raw) != 64:
        raise ValueError("Assinatura em formato inválido")
    return raw


def verify_signature(address: str, message: str, signature: str) -> bool:
    """Ed25519 check of a Solana wallet `signMessage` over the UTF-8 text."""
    try:
        from nacl.exceptions import BadSignatureError
        from nacl.signing import VerifyKey
    except ImportError as exc:  # pragma: no cover - dependency guard for partial installs
        raise RuntimeError("Dependência PyNaCl não instalada") from exc
    try:
        VerifyKey(_b58decode(normalize_address(address))).verify(
            message.encode("utf-8"), _signature_bytes(signature))
        return True
    except (BadSignatureError, ValueError):
        return False


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
