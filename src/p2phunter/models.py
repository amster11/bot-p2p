"""Общие структуры данных. Все денежные величины — Decimal."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class AdSide(str, Enum):
    """Сторона объявления с точки зрения автора объявления."""

    SELL = "sell"  # автор продаёт монету — пользователь у него покупает
    BUY = "buy"  # автор покупает монету — пользователь ему продаёт


@dataclass(frozen=True)
class OrderBook:
    exchange: str
    symbol: str  # в формате BASE/QUOTE, например BTC/USDT
    bids: list[tuple[Decimal, Decimal]]  # (цена, количество), по убыванию цены
    asks: list[tuple[Decimal, Decimal]]  # (цена, количество), по возрастанию цены
    ts: float


@dataclass(frozen=True)
class P2PAd:
    exchange: str
    ad_id: str
    side: AdSide
    asset: str
    fiat: str
    price: Decimal  # фиат за 1 монету
    min_fiat: Decimal
    max_fiat: Decimal
    available: Decimal  # сколько монеты доступно по объявлению
    payment_methods: tuple[str, ...]
    seller_name: str
    seller_orders: int
    seller_completion: Decimal  # 0..1
    url: str = ""


@dataclass(frozen=True)
class NetworkInfo:
    exchange: str
    asset: str
    network: str  # нормализованное имя сети (см. network_aliases в конфиге)
    raw_network: str  # как сеть называет биржа
    deposit_enabled: bool
    withdraw_enabled: bool
    withdraw_fee: Decimal  # в единицах монеты
    withdraw_min: Decimal


@dataclass
class RouteStep:
    text: str
    amount_in: Decimal
    amount_out: Decimal
    unit_in: str
    unit_out: str


@dataclass
class RouteResult:
    kind: str  # "p2p" или "spot"
    buy_exchange: str
    sell_exchange: str
    asset: str
    network: str | None
    amount_in: Decimal
    amount_out: Decimal
    unit: str  # валюта входа и выхода (RUB для P2P, USDT для спота)
    steps: list[RouteStep] = field(default_factory=list)
    rejects: list[str] = field(default_factory=list)  # причины, по которым связка не годится
    links: list[str] = field(default_factory=list)

    @property
    def profit(self) -> Decimal:
        return self.amount_out - self.amount_in

    @property
    def profit_pct(self) -> Decimal:
        if not self.amount_in:
            return Decimal(0)
        return self.profit / self.amount_in * 100

    @property
    def ok(self) -> bool:
        return not self.rejects
