from abc import ABC, abstractmethod
import httpx
from ..models import Candle, Market


class VenueAdapter(ABC):
    name: str

    def __init__(self, client: httpx.AsyncClient, core_assets: frozenset[str]):
        self.client = client
        self.core_assets = core_assets

    @abstractmethod
    async def discover_markets(self) -> list[Market]: ...

    @abstractmethod
    async def candles(self, market: Market, timeframe: str, limit: int = 300) -> list[Candle]: ...
