"""Отсев подозрительных объявлений."""

from __future__ import annotations

from decimal import Decimal
from statistics import median

from .models import P2PAd


def seller_reject_reason(ad: P2PAd, min_orders: int, min_completion: Decimal) -> str | None:
    if ad.seller_orders < min_orders:
        return f"у {ad.seller_name} всего {ad.seller_orders} сделок"
    if ad.seller_completion < min_completion:
        return f"у {ad.seller_name} завершено {ad.seller_completion:.0%} сделок"
    return None


def price_outliers(ads: list[P2PAd], max_deviation: Decimal) -> set[str]:
    """ad_id объявлений, чья цена отклоняется от медианы больше чем на max_deviation (доля)."""
    if len(ads) < 3:
        return set()
    mid = Decimal(median(a.price for a in ads))
    return {a.ad_id for a in ads if abs(a.price - mid) / mid > max_deviation}


def clean_ads(
    ads: list[P2PAd], min_orders: int, min_completion: Decimal, max_deviation: Decimal
) -> list[P2PAd]:
    """Оставить только объявления надёжных продавцов с ценой в рынке."""
    outliers = price_outliers(ads, max_deviation)
    return [
        a for a in ads
        if a.ad_id not in outliers and seller_reject_reason(a, min_orders, min_completion) is None
    ]
