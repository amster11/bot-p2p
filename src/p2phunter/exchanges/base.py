"""Единый интерфейс биржи. Каждая биржа — отдельный модуль, который его реализует.

Чтобы добавить биржу: создать exchanges/<name>.py с классом-наследником
ExchangeAdapter, реализовать три метода и зарегистрировать класс в exchanges/__init__.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

import httpx

from ..models import AdSide, NetworkInfo, OrderBook, P2PAd


class ExchangeError(Exception):
    """Биржа не ответила, ответила ошибкой или поменяла формат ответа."""


class ExchangeAdapter(ABC):
    name: str = ""

    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: str = "",
        api_secret: str = "",
        passphrase: str = "",
        alias_map: dict[str, str] | None = None,
    ) -> None:
        self.client = client
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.alias_map = alias_map or {}

    def norm_network(self, raw: str) -> str:
        return self.alias_map.get(raw.upper(), raw.upper())

    async def _request(self, method: str, url: str, **kw: Any) -> Any:
        try:
            r = await self.client.request(method, url, timeout=15, **kw)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as e:
            raise ExchangeError(f"{self.name}: {method} {url}: {e}") from e

    @abstractmethod
    async def fetch_order_book(self, base: str, quote: str = "USDT", depth: int = 50) -> OrderBook:
        """Спотовый стакан пары base/quote."""

    @abstractmethod
    async def fetch_networks(self, asset: str) -> list[NetworkInfo]:
        """Сети монеты: открыт ли депозит/вывод, комиссия и минимум вывода."""

    @abstractmethod
    async def fetch_p2p_ads(
        self, asset: str, fiat: str, side: AdSide, payment_ids: list[str]
    ) -> list[P2PAd]:
        """P2P-объявления. side — сторона автора объявления (SELL = у него можно купить)."""


def D(x: Any) -> Decimal:
    """Безопасное преобразование ответа биржи в Decimal."""
    if x is None or x == "":
        return Decimal(0)
    return Decimal(str(x))


def levels(rows: list[list[Any]]) -> list[tuple[Decimal, Decimal]]:
    return [(D(r[0]), D(r[1])) for r in rows]
