from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class AssetClass(StrEnum):
    CRYPTO = "crypto"
    COMMODITY = "tokenized_commodity"
    STOCK = "us_tokenized_stock"


@dataclass(frozen=True, slots=True)
class Market:
    venue: str
    symbol: str
    base: str
    quote: str
    market_type: str
    asset_class: AssetClass
    daily_quote_volume: float = 0.0
    funding_rate: float | None = None
    open_interest: float | None = None
    metadata: dict = field(default_factory=dict, compare=False, hash=False)

    @property
    def key(self) -> str:
        return f"{self.venue}:{self.symbol}"


@dataclass(frozen=True, slots=True)
class Candle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float = 0.0


@dataclass(slots=True)
class Opportunity:
    market: Market
    timeframe: str
    direction: str
    setup: str
    entry: float
    stop: float
    target1: float
    target2: float | None
    risk_reward: float
    score: int
    reasons: list[str]
    risks: list[str]
    candle_timestamp: int
    score_breakdown: dict[str, int] = field(default_factory=dict)
    confirmation_count: int = 0

    @property
    def fingerprint(self) -> str:
        zone = round(self.entry / max(abs(self.entry - self.stop), 1e-12), 1)
        return f"{self.market.key}:{self.timeframe}:{self.direction}:{self.setup}:{zone}"


@dataclass(slots=True)
class PotentialOpportunity:
    market: Market
    timeframe: str
    direction: str
    scenario: str
    trigger_price: float
    invalidation_price: float
    target: float
    readiness: int
    conditions: list[str]
    risks: list[str]
    candle_timestamp: int
