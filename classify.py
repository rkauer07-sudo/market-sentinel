from __future__ import annotations

import re

from .models import AssetClass

COMMODITY_TERMS = {
    "GOLD", "XAU", "PAXG", "XAUT", "SILVER", "XAG", "OIL", "WTI", "BRENT",
    "NATGAS", "COPPER", "PLATINUM", "PALLADIUM", "CORN", "WHEAT",
    "SOY", "COFFEE", "COCOA", "SUGAR", "COTTON",
}

# Nado's public asset schema currently has names but no asset-class field.
# This allowlist covers its listed US equities/ETFs and is deliberately
# conservative so crypto/pre-IPO/non-US products are never mislabeled.
US_SECURITY_TICKERS = {
    "AAPL", "AMD", "AMZN", "AVGO", "BBX", "CRCL", "DELL", "GOOGL", "INTC",
    "META", "MRVL", "MSFT", "MSTR", "MU", "NBIS", "NVDA", "PENG", "QQQ",
    "SNDK", "SPY", "TSLA",
}


def classify(base: str, raw: dict, core_assets: frozenset[str]) -> AssetClass | None:
    upper = base.upper()
    blob = " ".join(str(v) for v in raw.values()).upper()
    category = str(raw.get("category", "")).lower()
    clean = upper.split(":")[-1].replace("-PERP", "")
    if "WRAPPED BACKED" in blob:
        clean = clean.lstrip("W").rstrip("X")
    if category in {"indices", "index", "fx", "preipo"}:
        return None
    if category in {"stock", "stocks"} or raw.get("rwaMarketType") == "STOCK" or \
            re.search(r"(^|[_.:])US($|[_.:])", upper) or clean in US_SECURITY_TICKERS or \
            "WRAPPED BACKED" in blob:
        return AssetClass.STOCK
    if category in {"commodity", "commodities"} or any(term in upper or term in blob for term in COMMODITY_TERMS):
        return AssetClass.COMMODITY
    if clean in core_assets:
        return AssetClass.CRYPTO
    return None
