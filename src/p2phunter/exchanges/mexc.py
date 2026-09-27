"""MEXC.

Спот и сети — официальный API v3 (https://mexcdevelop.github.io/apidocs/spot_v3_en/).
P2P — публичного API нет; эндпоинт веб-сайта ещё предстоит разобрать (см. README).
"""

from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import urlencode

from ..models import AdSide, NetworkInfo, OrderBook, P2PAd
from .base import D, ExchangeAdapter, ExchangeError, levels

API = "https://api.mexc.com"


class MexcAdapter(ExchangeAdapter):
    name = "mexc"

    async def fetch_order_book(self, base: str, quote: str = "USDT", depth: int = 50) -> OrderBook:
        data = await self._request(
            "GET", f"{API}/api/v3/depth", params={"symbol": f"{base}{quote}", "limit": depth}
        )
        if "bids" not in data:
            raise ExchangeError(f"mexc depth: {data}")
        return OrderBook(self.name, f"{base}/{quote}", levels(data["bids"]), levels(data["asks"]),
                         time.time())

    async def fetch_networks(self, asset: str) -> list[NetworkInfo]:
        if not self.api_key:
            raise ExchangeError("mexc: для списка сетей нужен API-ключ (только чтение)")
        query = urlencode({"timestamp": int(time.time() * 1000), "recvWindow": 5000})
        sign = hmac.new(self.api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
        data = await self._request(
            "GET", f"{API}/api/v3/capital/config/getall?{query}&signature={sign}",
            headers={"X-MEXC-APIKEY": self.api_key},
        )
        if not isinstance(data, list):
            raise ExchangeError(f"mexc capital config: {data}")
        out = []
        for coin in data:
            if coin.get("coin") != asset:
                continue
            for n in coin.get("networkList", []):
                raw = n.get("netWork") or n.get("network", "")
                out.append(NetworkInfo(
                    exchange=self.name, asset=asset, network=self.norm_network(raw), raw_network=raw,
                    deposit_enabled=bool(n.get("depositEnable")),
                    withdraw_enabled=bool(n.get("withdrawEnable")),
                    withdraw_fee=D(n.get("withdrawFee")), withdraw_min=D(n.get("withdrawMin")),
                ))
        return out

    async def fetch_p2p_ads(
        self, asset: str, fiat: str, side: AdSide, payment_ids: list[str]
    ) -> list[P2PAd]:
        raise ExchangeError("mexc p2p: ещё не реализовано — нужен разбор эндпоинта с доступом к сайту")
