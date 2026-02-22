from __future__ import annotations

import httpx
import pytest
import respx

from pmdata.api.clob import _CLOB_BASE, ClobClient


@pytest.fixture
def client() -> ClobClient:
    c = ClobClient()
    yield c
    c.close()


class TestGetPricesHistory:
    @respx.mock
    def test_returns_price_points(self, client: ClobClient):
        respx.get(f"{_CLOB_BASE}/prices-history").mock(
            return_value=httpx.Response(
                200,
                json={"history": [{"t": 1000, "p": 0.5}, {"t": 1060, "p": 0.6}]},
            )
        )
        pts = client.get_prices_history("tok1", start_ts=1000, end_ts=2000)
        assert len(pts) == 2
        assert pts[0].t == 1000
        assert pts[0].p == 0.5
        assert pts[1].t == 1060

    @respx.mock
    def test_empty_history(self, client: ClobClient):
        respx.get(f"{_CLOB_BASE}/prices-history").mock(
            return_value=httpx.Response(200, json={"history": []})
        )
        pts = client.get_prices_history("tok1")
        assert pts == []

    @respx.mock
    def test_missing_history_key(self, client: ClobClient):
        respx.get(f"{_CLOB_BASE}/prices-history").mock(return_value=httpx.Response(200, json={}))
        pts = client.get_prices_history("tok1")
        assert pts == []

    @respx.mock
    def test_sends_token_id_param(self, client: ClobClient):
        route = respx.get(f"{_CLOB_BASE}/prices-history").mock(
            return_value=httpx.Response(200, json={"history": []})
        )
        client.get_prices_history("my_token")
        assert route.called
        request = route.calls[0].request
        assert b"my_token" in request.url.query

    @respx.mock
    def test_sends_start_end_ts(self, client: ClobClient):
        route = respx.get(f"{_CLOB_BASE}/prices-history").mock(
            return_value=httpx.Response(200, json={"history": []})
        )
        client.get_prices_history("tok", start_ts=500, end_ts=999)
        request = route.calls[0].request
        query = request.url.query.decode()
        assert "startTs=500" in query
        assert "endTs=999" in query


class TestGetOrderbook:
    @respx.mock
    def test_returns_orderbook(self, client: ClobClient):
        respx.get(f"{_CLOB_BASE}/book").mock(
            return_value=httpx.Response(
                200,
                json={
                    "timestamp": 1234567890,
                    "market": "0xabc",
                    "bids": [{"price": "0.48", "size": "100"}],
                    "asks": [{"price": "0.52", "size": "80"}],
                },
            )
        )
        ob = client.get_orderbook("tok1")
        assert ob.market == "0xabc"
        assert ob.token_id == "tok1"
        assert ob.is_synthetic is False
        assert len(ob.bids) == 1
        assert ob.bids[0].price == 0.48
        assert len(ob.asks) == 1
        assert ob.asks[0].price == 0.52

    @respx.mock
    def test_empty_bids_asks(self, client: ClobClient):
        respx.get(f"{_CLOB_BASE}/book").mock(
            return_value=httpx.Response(200, json={"market": "x", "bids": [], "asks": []})
        )
        ob = client.get_orderbook("tok1")
        assert ob.bids == []
        assert ob.asks == []

    @respx.mock
    def test_http_error_propagates(self, client: ClobClient):
        respx.get(f"{_CLOB_BASE}/book").mock(return_value=httpx.Response(400, text="bad request"))
        with pytest.raises(httpx.HTTPStatusError):
            client.get_orderbook("tok1")
