"""Разбор ответов бирж на примерах в формате их документации (без сети)."""

import httpx

from p2phunter.exchanges import BitgetAdapter, BybitAdapter, MexcAdapter
from p2phunter.models import AdSide

ALIASES = {"TRX": "TRC20", "TRC20": "TRC20"}


def client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_bybit_book_and_networks_and_p2p():
    def handler(req: httpx.Request):
        if req.url.path == "/v5/market/orderbook":
            return httpx.Response(200, json={"retCode": 0, "result": {
                "s": "BTCUSDT", "b": [["100", "1"]], "a": [["101", "2"]], "ts": 1700000000000}})
        if req.url.path == "/v5/asset/coin/query-info":
            assert req.headers["X-BAPI-API-KEY"] == "k" and req.headers["X-BAPI-SIGN"]
            return httpx.Response(200, json={"retCode": 0, "result": {"rows": [{"coin": "USDT", "chains": [
                {"chain": "TRX", "chainDeposit": "1", "chainWithdraw": "0", "withdrawFee": "1",
                 "withdrawMin": "10"}]}]}})
        if req.url.path == "/fiat/otc/item/online":
            return httpx.Response(200, json={"ret_code": 0, "result": {"items": [
                {"id": "42", "nickName": "bob", "price": "91.5", "lastQuantity": "500",
                 "minAmount": "1000", "maxAmount": "40000", "payments": ["582"],
                 "recentOrderNum": 321, "recentExecuteRate": 97}]}})
        return httpx.Response(404)

    async with client(handler) as c:
        ex = BybitAdapter(c, "k", "s", alias_map=ALIASES)
        book = await ex.fetch_order_book("BTC")
        assert str(book.bids[0][0]) == "100" and book.symbol == "BTC/USDT"
        [n] = await ex.fetch_networks("USDT")
        assert n.network == "TRC20" and n.deposit_enabled and not n.withdraw_enabled
        [a] = await ex.fetch_p2p_ads("USDT", "RUB", AdSide.SELL, ["582"])
        assert a.seller_orders == 321 and str(a.seller_completion) == "0.97"


async def test_mexc_networks():
    def handler(req: httpx.Request):
        assert "signature=" in str(req.url) and req.headers["X-MEXC-APIKEY"] == "k"
        return httpx.Response(200, json=[{"coin": "USDT", "networkList": [
            {"network": "Tron(TRC20)", "netWork": "TRX", "depositEnable": True,
             "withdrawEnable": True, "withdrawFee": "1", "withdrawMin": "5"}]}])

    async with client(handler) as c:
        [n] = await MexcAdapter(c, "k", "s", alias_map=ALIASES).fetch_networks("USDT")
        assert n.network == "TRC20" and n.withdraw_enabled


async def test_bitget_networks_public():
    def handler(req: httpx.Request):
        return httpx.Response(200, json={"code": "00000", "data": [{"coin": "USDT", "chains": [
            {"chain": "TRC20", "rechargeable": "true", "withdrawable": "false",
             "withdrawFee": "1.5", "minWithdrawAmount": "10"}]}]})

    async with client(handler) as c:
        [n] = await BitgetAdapter(c, alias_map=ALIASES).fetch_networks("USDT")
        assert n.deposit_enabled and not n.withdraw_enabled and str(n.withdraw_fee) == "1.5"
