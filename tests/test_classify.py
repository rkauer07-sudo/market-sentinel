from market_sentinel.classify import classify
from market_sentinel.models import AssetClass


CORE = frozenset({"BTC", "ETH", "SOL"})


def test_core_crypto(): assert classify("BTC", {}, CORE) == AssetClass.CRYPTO
def test_backpack_stock(): assert classify("MU.US", {"rwaMarketType": "STOCK"}, CORE) == AssetClass.STOCK
def test_commodity(): assert classify("XAU", {}, CORE) == AssetClass.COMMODITY
def test_index(): assert classify("SPX", {"category": "indices"}, CORE) == AssetClass.INDEX
def test_unknown_is_excluded(): assert classify("FAKE", {}, CORE) is None
