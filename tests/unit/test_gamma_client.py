from __future__ import annotations

import httpx
import pytest
import respx
from tenacity import RetryError

from pmdata.api.gamma import _GAMMA_BASE, GammaClient

_MARKET_RAW = {
    "id": "1",
    "question": "Will X happen?",
    "conditionId": "cond1",
    "clobTokenIds": '["tok_yes","tok_no"]',
    "outcomes": '["Yes","No"]',
    "active": True,
    "closed": False,
    "resolved": False,
}


@pytest.fixture
def client() -> GammaClient:
    c = GammaClient()
    yield c
    c.close()


class TestGetMarkets:
    @respx.mock
    def test_returns_markets(self, client: GammaClient):
        respx.get(f"{_GAMMA_BASE}/markets").mock(
            return_value=httpx.Response(200, json=[_MARKET_RAW])
        )
        markets = client.get_markets()
        assert len(markets) == 1
        m = markets[0]
        assert m.id == "1"
        assert m.question == "Will X happen?"
        assert m.clob_token_ids == ["tok_yes", "tok_no"]
        assert m.outcomes == ["Yes", "No"]
        assert m.active is True

    @respx.mock
    def test_empty_response(self, client: GammaClient):
        respx.get(f"{_GAMMA_BASE}/markets").mock(return_value=httpx.Response(200, json=[]))
        markets = client.get_markets()
        assert markets == []

    @respx.mock
    def test_active_filter_sent(self, client: GammaClient):
        route = respx.get(f"{_GAMMA_BASE}/markets").mock(return_value=httpx.Response(200, json=[]))
        client.get_markets(active=True)
        request = route.calls[0].request
        assert b"active=true" in request.url.query

    @respx.mock
    def test_http_error_propagates(self, client: GammaClient):
        respx.get(f"{_GAMMA_BASE}/markets").mock(return_value=httpx.Response(500, text="error"))
        with pytest.raises(RetryError):
            client.get_markets()


class TestGetMarket:
    @respx.mock
    def test_returns_single_market(self, client: GammaClient):
        respx.get(f"{_GAMMA_BASE}/markets/1").mock(
            return_value=httpx.Response(200, json=_MARKET_RAW)
        )
        m = client.get_market("1")
        assert m.id == "1"
        assert m.condition_id == "cond1"

    @respx.mock
    def test_resolved_market(self, client: GammaClient):
        raw = {**_MARKET_RAW, "resolved": True, "resolvedOutcome": "Yes"}
        respx.get(f"{_GAMMA_BASE}/markets/1").mock(return_value=httpx.Response(200, json=raw))
        m = client.get_market("1")
        assert m.resolved is True
        assert m.resolved_outcome == "Yes"


class TestIterAllMarkets:
    @respx.mock
    def test_stops_when_page_smaller_than_size(self, client: GammaClient):
        respx.get(f"{_GAMMA_BASE}/markets").mock(
            return_value=httpx.Response(200, json=[_MARKET_RAW])
        )
        markets = client.iter_all_markets(page_size=100)
        assert len(markets) == 1
