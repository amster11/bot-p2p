"""Расчёт маршрутов. Только формулы — никакого ИИ.

Функции чистые: получают уже загруженные данные, ничего не запрашивают.
"""

from __future__ import annotations

from decimal import Decimal

from .models import AdSide, NetworkInfo, OrderBook, P2PAd, RouteResult, RouteStep

ZERO = Decimal(0)
HUNDRED = Decimal(100)


def pct(value: Decimal | float | int) -> Decimal:
    """Проценты из конфига -> доля: 0.1 -> 0.001."""
    return Decimal(str(value)) / HUNDRED


def buy_with_quote(asks: list[tuple[Decimal, Decimal]], quote: Decimal) -> tuple[Decimal, Decimal]:
    """Купить базовую монету на сумму quote, проходя стакан.

    Возвращает (получено базовой, потрачено котируемой). Если стакана не хватило,
    потрачено будет меньше quote.
    """
    left = quote
    got = ZERO
    for price, qty in asks:
        if left <= 0:
            break
        level_cost = price * qty
        if level_cost >= left:
            got += left / price
            left = ZERO
            break
        got += qty
        left -= level_cost
    return got, quote - left


def sell_base(bids: list[tuple[Decimal, Decimal]], base: Decimal) -> tuple[Decimal, Decimal]:
    """Продать base базовой монеты в стакан. Возвращает (получено котируемой, продано базовой)."""
    left = base
    got = ZERO
    for price, qty in bids:
        if left <= 0:
            break
        take = min(qty, left)
        got += take * price
        left -= take
    return got, base - left


def choose_network(
    withdraw_side: list[NetworkInfo], deposit_side: list[NetworkInfo]
) -> NetworkInfo | None:
    """Самая дешёвая сеть, где на одной бирже открыт вывод, а на другой — депозит.

    Возвращает запись со стороны вывода (в ней комиссия и минимум).
    """
    deposit_ok = {n.network for n in deposit_side if n.deposit_enabled}
    candidates = [n for n in withdraw_side if n.withdraw_enabled and n.network in deposit_ok]
    if not candidates:
        return None
    return min(candidates, key=lambda n: n.withdraw_fee)


def p2p_route(
    amount_fiat: Decimal,
    buy_ad: P2PAd,
    sell_ad: P2PAd,
    buy_fee: Decimal,
    sell_fee: Decimal,
    network: NetworkInfo | None,
) -> RouteResult:
    """Купить монету по P2P на бирже A -> (перевести) -> продать по P2P на бирже B.

    buy_ad — объявление, где автор продаёт (мы покупаем); sell_ad — где автор покупает.
    buy_fee/sell_fee — доли (0.001 = 0.1%). network — сеть перевода, None если биржа одна.
    """
    same_exchange = buy_ad.exchange == sell_ad.exchange
    res = RouteResult(
        kind="p2p",
        buy_exchange=buy_ad.exchange,
        sell_exchange=sell_ad.exchange,
        asset=buy_ad.asset,
        network=None if same_exchange else (network.network if network else None),
        amount_in=amount_fiat,
        amount_out=ZERO,
        unit=buy_ad.fiat,
        links=[u for u in (buy_ad.url, sell_ad.url) if u],
    )

    if buy_ad.side is not AdSide.SELL or sell_ad.side is not AdSide.BUY:
        res.rejects.append("перепутаны стороны объявлений")
        return res
    if buy_ad.asset != sell_ad.asset or buy_ad.fiat != sell_ad.fiat:
        res.rejects.append("разные монеты или валюты")
        return res

    if not buy_ad.min_fiat <= amount_fiat <= buy_ad.max_fiat:
        res.rejects.append(
            f"сумма {amount_fiat} вне лимитов покупки {buy_ad.min_fiat}–{buy_ad.max_fiat}"
        )

    qty = amount_fiat / buy_ad.price
    if qty > buy_ad.available:
        res.rejects.append(f"у продавца доступно только {buy_ad.available} {buy_ad.asset}")
    qty_after_fee = qty * (1 - buy_fee)
    res.steps.append(
        RouteStep(f"P2P-покупка на {buy_ad.exchange} у {buy_ad.seller_name} по {buy_ad.price}",
                  amount_fiat, qty_after_fee, buy_ad.fiat, buy_ad.asset)
    )

    qty_arrived = qty_after_fee
    if not same_exchange:
        if network is None:
            res.rejects.append("нет общей сети: вывод или депозит закрыт")
        else:
            if qty_after_fee < network.withdraw_min:
                res.rejects.append(f"меньше минимального вывода {network.withdraw_min}")
            qty_arrived = qty_after_fee - network.withdraw_fee
            res.steps.append(
                RouteStep(f"Перевод {buy_ad.exchange} → {sell_ad.exchange} по сети {network.network}"
                          f" (комиссия {network.withdraw_fee})",
                          qty_after_fee, qty_arrived, buy_ad.asset, buy_ad.asset)
            )

    if qty_arrived <= 0:
        res.rejects.append("после комиссий ничего не остаётся")
        return res
    if qty_arrived > sell_ad.available:
        res.rejects.append(f"покупатель берёт только {sell_ad.available} {sell_ad.asset}")

    fiat_out = qty_arrived * sell_ad.price * (1 - sell_fee)
    if not sell_ad.min_fiat <= fiat_out <= sell_ad.max_fiat:
        res.rejects.append(
            f"сумма продажи {fiat_out:.2f} вне лимитов {sell_ad.min_fiat}–{sell_ad.max_fiat}"
        )
    res.steps.append(
        RouteStep(f"P2P-продажа на {sell_ad.exchange} покупателю {sell_ad.seller_name} по {sell_ad.price}",
                  qty_arrived, fiat_out, sell_ad.asset, sell_ad.fiat)
    )
    res.amount_out = fiat_out
    return res


def spot_route(
    amount_quote: Decimal,
    buy_book: OrderBook,
    sell_book: OrderBook,
    buy_fee: Decimal,
    sell_fee: Decimal,
    network: NetworkInfo | None,
) -> RouteResult:
    """Купить монету за USDT на споте биржи A -> перевести -> продать за USDT на споте B."""
    base, quote = buy_book.symbol.split("/")
    res = RouteResult(
        kind="spot",
        buy_exchange=buy_book.exchange,
        sell_exchange=sell_book.exchange,
        asset=base,
        network=network.network if network else None,
        amount_in=amount_quote,
        amount_out=ZERO,
        unit=quote,
    )
    if buy_book.symbol != sell_book.symbol:
        res.rejects.append("разные торговые пары")
        return res

    got, spent = buy_with_quote(buy_book.asks, amount_quote)
    if spent < amount_quote:
        res.rejects.append(f"в стакане {buy_book.exchange} не хватает объёма на покупку")
    got_after_fee = got * (1 - buy_fee)
    res.steps.append(RouteStep(f"Покупка {base} на {buy_book.exchange}", amount_quote,
                               got_after_fee, quote, base))

    if network is None:
        res.rejects.append("нет общей сети: вывод или депозит закрыт")
        return res
    if got_after_fee < network.withdraw_min:
        res.rejects.append(f"меньше минимального вывода {network.withdraw_min}")
    arrived = got_after_fee - network.withdraw_fee
    res.steps.append(RouteStep(f"Перевод по сети {network.network} (комиссия {network.withdraw_fee})",
                               got_after_fee, arrived, base, base))
    if arrived <= 0:
        res.rejects.append("после комиссий ничего не остаётся")
        return res

    out, sold = sell_base(sell_book.bids, arrived)
    if sold < arrived:
        res.rejects.append(f"в стакане {sell_book.exchange} не хватает объёма на продажу")
    out_after_fee = out * (1 - sell_fee)
    res.steps.append(RouteStep(f"Продажа {base} на {sell_book.exchange}", arrived, out_after_fee,
                               base, quote))
    res.amount_out = out_after_fee
    return res
