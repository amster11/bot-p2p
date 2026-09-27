"""Bybit.

Спот и сети — официальный API v5 (https://bybit-exchange.github.io/docs/v5/intro).
P2P — НЕОФИЦИАЛЬНЫЙ эндпоинт веб-сайта api2.bybit.com; может поменяться без предупреждения.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import urlencode

from ..models import AdSide, NetworkInfo, OrderBook, P2PAd
from .base import D, ExchangeAdapter, ExchangeError, levels

API = "https://api.bybit.com"
P2P_API = "https://api2.bybit.com/fiat/otc/item/online"
RECV_WINDOW = "5000"


class BybitAdapter(ExchangeAdapter):
    name = "bybit"

    async def fetch_order_book(self, base: str, quote: str = "USDT", depth: int = 50) -> OrderBook:
        data = await self._request(
            "GET", f"{API}/v5/market/orderbook",
            params={"category": "spot", "symbol": f"{base}{quote}", "limit": depth},
        )
        if data.get("retCode") != 0:
            raise ExchangeError(f"bybit orderbook: {data.get('retMsg')}")
        r = data["result"]
        return OrderBook(self.name, f"{base}/{quote}", levels(r["b"]), levels(r["a"]), r["ts"] / 1000)

    def _signed_headers(self, query: str) -> dict[str, str]:
        ts = str(int(time.time() * 1000))
        payload = ts + self.api_key + RECV_WINDOW + query
        sign = hmac.new(self.api_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-RECV-WINDOW": RECV_WINDOW,
            "X-BAPI-SIGN": sign,
        }

    async def fetch_networks(self, asset: str) -> list[NetworkInfo]:
        if not self.api_key:
            raise ExchangeError("bybit: для списка сетей нужен API-ключ (только чтение)")
        query = urlencode({"coin": asset})
        data = await self._request(
            "GET", f"{API}/v5/asset/coin/query-info?{query}", headers=self._signed_headers(query)
        )
        if data.get("retCode") != 0:
            raise ExchangeError(f"bybit coin info: {data.get('retMsg')}")
        out = []
        for row in data["result"].get("rows", []):
            for ch in row.get("chains", []):
                raw = ch.get("chain", "")
                out.append(NetworkInfo(
                    exchange=self.name, asset=asset, network=self.norm_network(raw), raw_network=raw,
                    deposit_enabled=str(ch.get("chainDeposit")) == "1",
                    withdraw_enabled=str(ch.get("chainWithdraw")) == "1",
                    withdraw_fee=D(ch.get("withdrawFee")), withdraw_min=D(ch.get("withdrawMin")),
                ))
        return out

    async def fetch_p2p_ads(
        self, asset: str, fiat: str, side: AdSide, payment_ids: list[str]
    ) -> list[P2PAd]:
        # На сайте вкладка «Купить» (авторы продают) — side "1", «Продать» — side "0".
        body = {
            "userId": "", "tokenId": asset, "currencyId": fiat, "payment": payment_ids,
            "side": "1" if side is AdSide.SELL else "0",
            "size": "50", "page": "1", "amount": "", "authMaker": False, "canTrade": False,
        }
        data = await self._request("POST", P2P_API, json=body)
        if data.get("ret_code") not in (0, None):
            raise ExchangeError(f"bybit p2p: {data.get('ret_msg')}")
        action = "1" if side is AdSide.SELL else "0"
        url = f"https://www.bybit.com/fiat/trade/otc/?actionType={action}&token={asset}&fiat={fiat}"
        out = []
        for it in (data.get("result") or {}).get("items", []):
            out.append(P2PAd(
                exchange=self.name, ad_id=str(it["id"]), side=side, asset=asset, fiat=fiat,
                price=D(it["price"]), min_fiat=D(it["minAmount"]), max_fiat=D(it["maxAmount"]),
                available=D(it.get("lastQuantity")),
                payment_methods=tuple(str(p) for p in it.get("payments", [])),
                seller_name=it.get("nickName", ""),
                seller_orders=int(it.get("recentOrderNum") or 0),
                seller_completion=D(it.get("recentExecuteRate")) / 100,
                url=url,
            ))
        return out
