"""Проверка доступа к биржам: python -m p2phunter.probe

Запускать на VPS (или локально) после заполнения .env. Для каждой биржи пробует получить
стакан, сети и P2P-объявления и печатает, что работает, а что нет.
"""

from __future__ import annotations

import asyncio

import httpx

from .config import build_alias_map, load_config, load_secrets
from .exchanges import ADAPTERS, ExchangeError
from .models import AdSide


async def probe_one(name: str, adapter, asset: str, fiat: str, payment_ids: list[str]) -> None:
    print(f"\n=== {name} ===")
    try:
        book = await adapter.fetch_order_book("BTC")
        print(f"  стакан BTC/USDT: bid {book.bids[0][0]}  ask {book.asks[0][0]}")
    except (ExchangeError, IndexError, KeyError) as e:
        print(f"  стакан: ОШИБКА {e}")
    try:
        nets = await adapter.fetch_networks(asset)
        print(f"  сети {asset}: {len(nets)}")
        for n in nets:
            print(f"    {n.raw_network:<20} -> {n.network:<10} деп {'да' if n.deposit_enabled else 'нет'}"
                  f"  вывод {'да' if n.withdraw_enabled else 'нет'}  комиссия {n.withdraw_fee}"
                  f"  мин {n.withdraw_min}")
    except (ExchangeError, KeyError) as e:
        print(f"  сети: ОШИБКА {e}")
    for side in (AdSide.SELL, AdSide.BUY):
        try:
            ads = await adapter.fetch_p2p_ads(asset, fiat, side, payment_ids)
            print(f"  P2P {asset}/{fiat}, авторы {'продают' if side is AdSide.SELL else 'покупают'}:"
                  f" {len(ads)} объявлений")
            for a in ads[:3]:
                print(f"    {a.price} {fiat}  лимит {a.min_fiat}–{a.max_fiat}  {a.seller_name}"
                      f" ({a.seller_orders} сделок, {a.seller_completion:.0%})  оплата {a.payment_methods}")
        except (ExchangeError, KeyError) as e:
            print(f"  P2P: ОШИБКА {e}")


async def main() -> None:
    cfg = load_config()
    sec = load_secrets()
    aliases = build_alias_map(cfg.network_aliases)
    asset = cfg.work.assets[0]
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:
        for name, cls in ADAPTERS.items():
            ex = cfg.exchanges.get(name)
            if ex is not None and not ex.enabled:
                continue
            k = sec.api_keys.get(name, {})
            adapter = cls(client, k.get("key", ""), k.get("secret", ""), k.get("passphrase", ""), aliases)
            payment_ids = list(ex.payment_methods.values()) if ex else []
            await probe_one(name, adapter, asset, cfg.work.fiat, payment_ids)


if __name__ == "__main__":
    asyncio.run(main())
