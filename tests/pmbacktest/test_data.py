"""Unit tests for create_data_feed_from_pmdata()."""

from __future__ import annotations

import warnings
from unittest.mock import MagicMock

import pandas as pd
import pytest

from pmbacktest.data import MarketDataFeed, create_data_feed_from_pmdata
from pmbacktest.types import Outcome


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_market(outcomes: list[str], token_ids: list[str]) -> MagicMock:
    """Build a mock Market object."""
    m = MagicMock()
    m.outcomes = outcomes
    m.clob_token_ids = token_ids
    return m


def _make_ohlcv(rows: list[tuple[int, float, float, float, float, float]]) -> pd.DataFrame:
    """Build a mock OHLCV DataFrame indexed by timestamp.

    Each row is (timestamp, open, high, low, close, volume).
    """
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    timestamps, opens, highs, lows, closes, volumes = zip(*rows)
    df = pd.DataFrame(
        {
            "open": list(opens),
            "high": list(highs),
            "low": list(lows),
            "close": list(closes),
            "volume": list(volumes),
        },
        index=pd.Index(list(timestamps), name="timestamp"),
    )
    return df


def _make_client(market_map: dict, ohlcv_map: dict) -> MagicMock:
    """Build a mock PolymarketData client.

    Args:
        market_map: {market_id: mock Market}
        ohlcv_map: {token_id: DataFrame}
    """
    client = MagicMock()
    client.get_market.side_effect = lambda mid: market_map[mid]
    client.get_ohlcv.side_effect = lambda token_id, *_args, **_kwargs: ohlcv_map[token_id]
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSingleMarketConvertsCorrectly:
    """test_single_market_converts_correctly"""

    def test_single_market_converts_correctly(self):
        market = _make_market(["YES", "NO"], ["tok_yes", "tok_no"])
        df = _make_ohlcv([(1_000_000, 0.3, 0.5, 0.2, 0.4, 100.0)])
        client = _make_client({"mkt1": market}, {"tok_yes": df})

        feed = create_data_feed_from_pmdata(client, ["mkt1"], 0, 9_999_999)

        assert isinstance(feed, MarketDataFeed)
        assert len(feed) == 1

        point = list(feed)[0]
        assert point.timestamp == 1_000_000
        assert "mkt1" in point.prices
        assert "mkt1" in point.bars


class TestPricesIncludeYesAndNo:
    """test_prices_include_yes_and_no"""

    def test_prices_include_yes_and_no(self):
        market = _make_market(["YES", "NO"], ["tok_yes", "tok_no"])
        close_price = 0.65
        df = _make_ohlcv([(1_000_000, 0.6, 0.7, 0.5, close_price, 50.0)])
        client = _make_client({"mkt1": market}, {"tok_yes": df})

        feed = create_data_feed_from_pmdata(client, ["mkt1"], 0, 9_999_999)
        point = list(feed)[0]

        yes_price = point.prices["mkt1"][Outcome.YES]
        no_price = point.prices["mkt1"][Outcome.NO]

        assert yes_price == pytest.approx(close_price)
        assert no_price == pytest.approx(1.0 - close_price)


class TestBarsPopulatedFromOhlcv:
    """test_bars_populated_from_ohlcv"""

    def test_bars_populated_from_ohlcv(self):
        market = _make_market(["YES", "NO"], ["tok_yes", "tok_no"])
        ts, o, h, l, c, v = 2_000_000, 0.1, 0.9, 0.05, 0.6, 999.0
        df = _make_ohlcv([(ts, o, h, l, c, v)])
        client = _make_client({"mkt1": market}, {"tok_yes": df})

        feed = create_data_feed_from_pmdata(client, ["mkt1"], 0, 9_999_999)
        point = list(feed)[0]
        bar = point.bars["mkt1"]

        assert bar.timestamp == ts
        assert bar.open == pytest.approx(o)
        assert bar.high == pytest.approx(h)
        assert bar.low == pytest.approx(l)
        assert bar.close == pytest.approx(c)
        assert bar.volume == pytest.approx(v)


class TestMultipleMarketsMerged:
    """test_multiple_markets_merged"""

    def test_multiple_markets_merged(self):
        # mkt_a has timestamps 1000, 2000; mkt_b has 2000, 3000
        mkt_a = _make_market(["YES", "NO"], ["tok_a", "tok_a_no"])
        mkt_b = _make_market(["YES", "NO"], ["tok_b", "tok_b_no"])

        df_a = _make_ohlcv(
            [
                (1000, 0.4, 0.5, 0.3, 0.45, 10.0),
                (2000, 0.5, 0.6, 0.4, 0.55, 20.0),
            ]
        )
        df_b = _make_ohlcv(
            [
                (2000, 0.3, 0.4, 0.2, 0.35, 30.0),
                (3000, 0.6, 0.7, 0.5, 0.65, 40.0),
            ]
        )
        client = _make_client(
            {"mkt_a": mkt_a, "mkt_b": mkt_b},
            {"tok_a": df_a, "tok_b": df_b},
        )

        feed = create_data_feed_from_pmdata(client, ["mkt_a", "mkt_b"], 0, 9_999_999)
        points = list(feed)

        # Union of {1000, 2000, 3000}
        assert len(points) == 3

        # At ts=1000 only mkt_a is present
        pt_1000 = next(p for p in points if p.timestamp == 1000)
        assert "mkt_a" in pt_1000.prices
        assert "mkt_b" not in pt_1000.prices

        # At ts=2000 both are present
        pt_2000 = next(p for p in points if p.timestamp == 2000)
        assert "mkt_a" in pt_2000.prices
        assert "mkt_b" in pt_2000.prices

        # At ts=3000 mkt_a forward-fills from ts=2000
        pt_3000 = next(p for p in points if p.timestamp == 3000)
        assert "mkt_a" in pt_3000.prices
        assert pt_3000.prices["mkt_a"][Outcome.YES] == pytest.approx(0.55)
        assert "mkt_b" in pt_3000.prices


class TestTimestampsSorted:
    """test_timestamps_sorted"""

    def test_timestamps_sorted(self):
        market = _make_market(["YES", "NO"], ["tok_yes", "tok_no"])
        # Provide rows out of order
        df = _make_ohlcv(
            [
                (3000, 0.5, 0.6, 0.4, 0.5, 10.0),
                (1000, 0.5, 0.6, 0.4, 0.5, 10.0),
                (2000, 0.5, 0.6, 0.4, 0.5, 10.0),
            ]
        )
        client = _make_client({"mkt1": market}, {"tok_yes": df})

        feed = create_data_feed_from_pmdata(client, ["mkt1"], 0, 9_999_999)
        timestamps = [p.timestamp for p in feed]

        assert timestamps == sorted(timestamps)


class TestEmptyOhlcvSkipsMarket:
    """test_empty_ohlcv_skips_market"""

    def test_empty_ohlcv_skips_market(self):
        market = _make_market(["YES", "NO"], ["tok_yes", "tok_no"])
        empty_df = _make_ohlcv([])
        client = _make_client({"mkt1": market}, {"tok_yes": empty_df})

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            feed = create_data_feed_from_pmdata(client, ["mkt1"], 0, 9_999_999)

        assert len(feed) == 0
        # A warning should have been emitted about empty data
        assert any("empty" in str(w.message).lower() for w in caught)


class TestIntervalPassedToFeed:
    """test_interval_passed_to_feed"""

    def test_interval_passed_to_feed(self):
        market = _make_market(["YES", "NO"], ["tok_yes", "tok_no"])
        df = _make_ohlcv([(1_000_000, 0.5, 0.6, 0.4, 0.5, 10.0)])
        client = _make_client({"mkt1": market}, {"tok_yes": df})

        for interval in ("1m", "5m", "15m", "1h", "6h", "1d"):
            feed = create_data_feed_from_pmdata(client, ["mkt1"], 0, 9_999_999, interval=interval)
            assert feed.interval == interval


class TestNonBinaryMarketRaises:
    """test_non_binary_market_raises"""

    def test_non_binary_market_raises(self):
        # Three outcomes → should raise ValueError
        market = _make_market(["YES", "NO", "MAYBE"], ["tok1", "tok2", "tok3"])
        client = MagicMock()
        client.get_market.return_value = market

        with pytest.raises(ValueError, match="binary"):
            create_data_feed_from_pmdata(client, ["mkt1"], 0, 9_999_999)

    def test_single_outcome_raises(self):
        market = _make_market(["YES"], ["tok1"])
        client = MagicMock()
        client.get_market.return_value = market

        with pytest.raises(ValueError):
            create_data_feed_from_pmdata(client, ["mkt1"], 0, 9_999_999)


class TestOutcomeCaseInsensitive:
    """test_outcome_case_insensitive"""

    @pytest.mark.parametrize("yes_label", ["YES", "yes", "Yes", "yEs"])
    def test_outcome_case_insensitive(self, yes_label: str):
        no_label = "NO" if yes_label.upper() == "YES" else "no"
        market = _make_market([yes_label, no_label], ["tok_yes", "tok_no"])
        df = _make_ohlcv([(1_000_000, 0.3, 0.4, 0.2, 0.35, 5.0)])
        client = _make_client({"mkt1": market}, {"tok_yes": df})

        feed = create_data_feed_from_pmdata(client, ["mkt1"], 0, 9_999_999)
        assert len(feed) == 1
        point = list(feed)[0]
        assert Outcome.YES in point.prices["mkt1"]
        assert point.prices["mkt1"][Outcome.YES] == pytest.approx(0.35)


class TestFeedLengthMatchesTimestamps:
    """test_feed_length_matches_timestamps"""

    def test_feed_length_matches_timestamps(self):
        market = _make_market(["YES", "NO"], ["tok_yes", "tok_no"])
        rows = [(1000 * i, 0.5, 0.6, 0.4, 0.5, float(i)) for i in range(1, 8)]
        df = _make_ohlcv(rows)
        client = _make_client({"mkt1": market}, {"tok_yes": df})

        feed = create_data_feed_from_pmdata(client, ["mkt1"], 0, 9_999_999)

        assert len(feed) == len(rows)
        assert len(list(feed)) == len(rows)
