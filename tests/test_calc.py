from decimal import Decimal as D

from p2phunter.calc import buy_with_quote, choose_network, p2p_route, pct, sell_base, spot_route
from p2phunter.models import AdSide, NetworkInfo, OrderBook, P2PAd


def ad(exchange, side, price, min_f="1000", max_f="500000", avail="10000", ad_id="1"):
    return P2PAd(exchange, ad_id, side, "USDT", "RUB", D(price), D(min_f), D(max_f), D(avail),
                 ("sber",), "trader", 500, D("0.98"))


def net(exchange, name, dep=True, wd=True, fee="1", mn="10"):
    return NetworkInfo(exchange, "USDT", name, name, dep, wd, D(fee), D(mn))


def test_pct():
    assert pct("0.1") == D("0.001")


def test_buy_walks_levels():
    asks = [(D(100), D(1)), (D(110), D(2))]
    got, spent = buy_with_quote(asks, D(210))
    assert got == D(2) and spent == D(210)  # 1 по 100 + 1 по 110


def test_buy_book_too_thin():
    got, spent = buy_with_quote([(D(100), D(1))], D(500))
    assert got == D(1) and spent == D(100)


def test_sell_walks_levels():
    got, sold = sell_base([(D(100), D(1)), (D(90), D(5))], D(2))
    assert got == D(190) and sold == D(2)


def test_choose_cheapest_open_network():
    a = [net("a", "TRC20", fee="1"), net("a", "TON", fee="0.1"), net("a", "SOL", wd=False, fee="0")]
    b = [net("b", "TRC20"), net("b", "TON"), net("b", "SOL")]
    assert choose_network(a, b).network == "TON"
    b_closed = [net("b", "TRC20"), net("b", "TON", dep=False)]
    assert choose_network(a, b_closed).network == "TRC20"
    assert choose_network(a, [net("b", "ERC20")]) is None


def test_p2p_route_profit_by_hand():
    # 100 000 ₽ / 90 = 1111.111 USDT, -1 USDT за вывод, * 93 ₽
    r = p2p_route(D(100000), ad("bybit", AdSide.SELL, "90"), ad("mexc", AdSide.BUY, "93"),
                  D(0), D(0), net("bybit", "TRC20", fee="1"))
    assert r.ok, r.rejects
    expected = (D(100000) / D(90) - 1) * D(93)
    assert r.amount_out == expected
    assert round(r.profit_pct, 2) == D("3.24")
    assert len(r.steps) == 3


def test_p2p_route_same_exchange_no_transfer():
    r = p2p_route(D(100000), ad("bybit", AdSide.SELL, "90"), ad("bybit", AdSide.BUY, "91"),
                  D(0), D(0), None)
    assert r.ok and r.network is None and len(r.steps) == 2


def test_p2p_route_rejects_limits_and_network():
    r = p2p_route(D(100000), ad("bybit", AdSide.SELL, "90", max_f="50000"),
                  ad("mexc", AdSide.BUY, "93", avail="100"), D(0), D(0), None)
    joined = " ".join(r.rejects)
    assert "лимитов покупки" in joined
    assert "нет общей сети" in joined
    assert "покупатель берёт только" in joined


def test_p2p_route_fee_eats_profit():
    r = p2p_route(D(100000), ad("bybit", AdSide.SELL, "90"), ad("mexc", AdSide.BUY, "90.5"),
                  pct("0.5"), pct("0.5"), net("bybit", "TRC20", fee="1"))
    assert r.profit < 0


def test_spot_route():
    buy = OrderBook("bybit", "TON/USDT", [], [(D(5), D(1000))], 0)
    sell = OrderBook("bitget", "TON/USDT", [(D("5.2"), D(1000))], [], 0)
    r = spot_route(D(1000), buy, sell, pct("0.1"), pct("0.1"),
                   NetworkInfo("bybit", "TON", "TON", "TON", True, True, D("0.1"), D(1)))
    assert r.ok, r.rejects
    arrived = D(200) * D("0.999") - D("0.1")
    assert r.amount_out == arrived * D("5.2") * D("0.999")
    assert r.profit > 0
