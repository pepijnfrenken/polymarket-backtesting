from __future__ import annotations

import pytest
from pydantic import ValidationError

from pmdata.models import (
    Interval,
    Market,
    Orderbook,
    OrderbookLevel,
    PriceBar,
    PricePoint,
    Trade,
)


class TestInterval:
    def test_str_values(self):
        assert Interval.ONE_MINUTE == "1m"
        assert Interval.ONE_HOUR == "1h"
        assert Interval.SIX_HOURS == "6h"
        assert Interval.ONE_DAY == "1d"

    def test_all_members_exist(self):
        members = {i.value for i in Interval}
        assert "1m" in members
        assert "1h" in members
        assert "6h" in members
        assert "1d" in members
        assert "1w" in members
        assert "max" in members
        assert "all" in members


class TestPricePoint:
    def test_valid(self):
        pt = PricePoint(t=1000, p=0.75)
        assert pt.t == 1000
        assert pt.p == 0.75

    def test_serialization(self):
        pt = PricePoint(t=1000, p=0.5)
        d = pt.model_dump()
        assert d == {"t": 1000, "p": 0.5}

    def test_missing_fields(self):
        with pytest.raises(ValidationError):
            PricePoint(t=1000)  # type: ignore[call-arg]


class TestPriceBar:
    def test_valid(self):
        bar = PriceBar(timestamp=1000, open=0.5, high=0.9, low=0.3, close=0.7, volume=42.0)
        assert bar.open == 0.5
        assert bar.high == 0.9
        assert bar.low == 0.3
        assert bar.close == 0.7
        assert bar.volume == 42.0

    def test_serialization_roundtrip(self):
        bar = PriceBar(timestamp=1000, open=0.1, high=0.2, low=0.05, close=0.15, volume=5.0)
        d = bar.model_dump()
        bar2 = PriceBar(**d)
        assert bar == bar2


class TestOrderbookLevel:
    def test_valid(self):
        level = OrderbookLevel(price=0.55, size=100.0)
        assert level.price == 0.55
        assert level.size == 100.0


class TestOrderbook:
    def test_defaults(self):
        ob = Orderbook(
            timestamp=1000,
            market="0xabc",
            token_id="0x123",
            bids=[],
            asks=[],
        )
        assert ob.is_synthetic is False

    def test_synthetic_flag(self):
        ob = Orderbook(
            timestamp=1000,
            market="",
            token_id="tok",
            bids=[OrderbookLevel(price=0.49, size=100.0)],
            asks=[OrderbookLevel(price=0.51, size=100.0)],
            is_synthetic=True,
        )
        assert ob.is_synthetic is True
        assert ob.bids[0].price == 0.49


class TestTrade:
    def test_valid(self):
        trade = Trade(
            timestamp=1000,
            price=0.6,
            size=50.0,
            side="BUY",
            order_id="ord_1",
            token_id="tok_1",
        )
        assert trade.side == "BUY"
        assert trade.price == 0.6


class TestMarket:
    def _raw(self, **overrides) -> dict:
        base = {
            "id": "mkt_1",
            "question": "Will it happen?",
            "condition_id": "cond_abc",
            "clob_token_ids": ["tok_yes", "tok_no"],
            "outcomes": ["Yes", "No"],
            "active": True,
            "closed": False,
            "resolved": False,
        }
        base.update(overrides)
        return base

    def test_valid_list_fields(self):
        m = Market(**self._raw())
        assert m.clob_token_ids == ["tok_yes", "tok_no"]
        assert m.outcomes == ["Yes", "No"]

    def test_json_string_clob_token_ids(self):
        m = Market(**self._raw(clob_token_ids='["tok_a","tok_b"]'))
        assert m.clob_token_ids == ["tok_a", "tok_b"]

    def test_json_string_outcomes(self):
        m = Market(**self._raw(outcomes='["Yes","No"]'))
        assert m.outcomes == ["Yes", "No"]

    def test_optional_fields_default_none(self):
        m = Market(**self._raw())
        assert m.resolved_outcome is None
        assert m.end_date_iso is None

    def test_optional_fields_set(self):
        m = Market(**self._raw(resolved_outcome="Yes", end_date_iso="2025-12-31"))
        assert m.resolved_outcome == "Yes"
        assert m.end_date_iso == "2025-12-31"

    def test_serialization(self):
        m = Market(**self._raw())
        d = m.model_dump()
        assert d["id"] == "mkt_1"
        assert isinstance(d["clob_token_ids"], list)
