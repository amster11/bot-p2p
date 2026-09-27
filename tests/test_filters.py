from decimal import Decimal as D

from p2phunter.filters import clean_ads, price_outliers, seller_reject_reason
from p2phunter.models import AdSide, P2PAd


def ad(ad_id, price, orders=500, completion="0.98"):
    return P2PAd("bybit", ad_id, AdSide.SELL, "USDT", "RUB", D(price), D(1000), D(100000), D(1000),
                 ("sber",), f"u{ad_id}", orders, D(completion))


def test_seller_filters():
    assert seller_reject_reason(ad("1", 90, orders=3), 50, D("0.9"))
    assert seller_reject_reason(ad("1", 90, completion="0.5"), 50, D("0.9"))
    assert seller_reject_reason(ad("1", 90), 50, D("0.9")) is None


def test_price_outlier():
    ads = [ad("1", 90), ad("2", 91), ad("3", 90.5), ad("4", 70)]
    assert price_outliers(ads, D("0.05")) == {"4"}


def test_clean_ads():
    ads = [ad("1", 90), ad("2", 91), ad("3", 90.5, orders=1), ad("4", 70)]
    assert [a.ad_id for a in clean_ads(ads, 50, D("0.9"), D("0.05"))] == ["1", "2"]
