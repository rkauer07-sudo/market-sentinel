import argparse
import asyncio
import json
import logging
import os

import httpx

from .app import Sentinel
from .config import load_settings
from .solana_intel import SolanaIntelService


async def execute(args):
    if args.command == "solana-intel-once":
        async with httpx.AsyncClient(
            timeout=30,
            headers={"User-Agent": "market-sentinel/0.3"},
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        ) as client:
            snapshot = await SolanaIntelService(client).snapshot(force=True)
        print(json.dumps(snapshot["summary"], ensure_ascii=False, sort_keys=True))
        return

    settings = load_settings(args.config); sentinel = Sentinel(settings)
    try:
        if args.command == "once":
            opportunities = await sentinel.scan_once()
            for op in opportunities:
                print(f"{op.score:3d} {op.market.key:35s} {op.timeframe:3s} {op.direction:5s} RR={op.risk_reward:.2f} {op.setup}")
            print(f"{len(opportunities)} oportunidade(s)")
        elif args.command == "markets":
            await sentinel.refresh_markets()
            for _, market in sorted(sentinel.markets, key=lambda x: (x[1].asset_class, x[1].base, x[1].venue)):
                print(f"{market.asset_class.value:24s} {market.venue:12s} {market.symbol:24s} vol24h={market.daily_quote_volume:,.0f}")
        elif args.command == "audit-failures":
            repaired = await sentinel.audit_failures()
            print(f"{len(repaired)} falha(s) reclassificada(s) como sucesso")
        else: await sentinel.run_forever()
    finally: await sentinel.close()


def main():
    parser = argparse.ArgumentParser(description="Monitor técnico read-only para cripto e RWAs")
    parser.add_argument("command", nargs="?", choices=[
        "run", "once", "markets", "audit-failures", "solana-intel-once",
    ], default="run")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try: asyncio.run(execute(args))
    except KeyboardInterrupt: pass


if __name__ == "__main__": main()
