"""Bitget.

Спот и сети — официальный API v2 (https://www.bitget.com/api-doc/spot/intro); сети публичные, ключ не нужен.
P2P — официальный API только для мерчантов; публичный эндпоинт сайта ещё предстоит разобрать (см. README).
"""

from __future__ import annotations

from ..models import AdSide, NetworkInfo, OrderBook, P2PAd
from .base import D, ExchangeAdapter, ExchangeError, levels

API = "https://api.bitget.com"


class BitgetAdapter(ExchangeAdapter):
    name = "bitget"

    async def _get(self, path: str, params: dict) -> object:
        data = await self._request("GET", f"{API}{path}", params=params)
        if data.get("code") != "00000":
            raise ExchangeError(f"bitget {path}: {data.get('msg')}")
        return data["data"]

    async def fetch_order_book(self, base: str, quote: str = "USDT", depth: int = 50) -> OrderBook:
        d = await self._get("/api/v2/spot/market/orderbook",
                            {"symbol": f"{base}{quote}", "type": "step0", "limit": depth})
        return OrderBook(self.name, f"{base}/{quote}", levels(d["bids"]), levels(d["asks"]),
                         int(d["ts"]) / 1000)

    async def fetch_networks(self, asset: str) -> list[NetworkInfo]:
        d = await self._get("/api/v2/spot/public/coins", {"coin": asset})
        out = []
        for coin in d:
            for ch in coin.get("chains", []):
                raw = ch.get("chain", "")
                out.append(NetworkInfo(
                    exchange=self.name, asset=asset, network=self.norm_network(raw), raw_network=raw,
                    deposit_enabled=str(ch.get("rechargeable")).lower() == "true",
                    withdraw_enabled=str(ch.get("withdrawable")).lower() == "true",
                    # extraWithdrawFee (доля от суммы, бывает у отдельных монет) пока не учитывается
                    withdraw_fee=D(ch.get("withdrawFee")),
                    withdraw_min=D(ch.get("minWithdrawAmount")),
                ))
        return out

    async def fetch_p2p_ads(
        self, asset: str, fiat: str, side: AdSide, payment_ids: list[str]
    ) -> list[P2PAd]:
        raise ExchangeError("bitget p2p: ещё не реализовано — нужен разбор эндпоинта с доступом к сайту")
