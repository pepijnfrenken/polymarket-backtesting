from __future__ import annotations

from pmdata.models import Orderbook, PriceBar, Trade
from pmdata.synthesis.orderbook import (
    SynthesisConfig,
    _age_decay,
    _build_levels,
    _estimate_spread,
    synthesize_orderbook,
    synthesize_orderbook_series,
)


def _trade(ts: int, price: float, size: float = 10.0) -> Trade:
    return Trade(timestamp=ts, price=price, size=size, side="BUY", order_id=str(ts), token_id="tok")


def _bar(ts: int, close: float) -> PriceBar:
    return PriceBar(timestamp=ts, open=close, high=close, low=close, close=close, volume=1.0)


class TestEstimateSpread:
    def test_single_trade_returns_default(self):
        assert _estimate_spread([_trade(0, 0.5)]) == 0.02

    def test_zero_trades_returns_default(self):
        assert _estimate_spread([]) == 0.02

    def test_identical_prices_returns_min(self):
        trades = [_trade(i, 0.5) for i in range(10)]
        spread = _estimate_spread(trades)
        assert spread == 0.005

    def test_spread_clamped_max(self):
        trades = [_trade(0, 0.01), _trade(1, 0.99)]
        spread = _estimate_spread(trades)
        assert spread <= 0.10

    def test_spread_clamped_min(self):
        trades = [_trade(i, 0.5 + 0.0001 * i) for i in range(5)]
        spread = _estimate_spread(trades)
        assert spread >= 0.005


class TestBuildLevels:
    def test_bid_prices_below_mid(self):
        mid = 0.5
        spread_half = 0.02
        levels = _build_levels(mid, spread_half, 5, 5000.0, 0.85, "bid")
        assert all(lv.price < mid for lv in levels)

    def test_ask_prices_above_mid(self):
        mid = 0.5
        spread_half = 0.02
        levels = _build_levels(mid, spread_half, 5, 5000.0, 0.85, "ask")
        assert all(lv.price > mid for lv in levels)

    def test_depth_levels_count(self):
        levels = _build_levels(0.5, 0.01, 10, 5000.0, 0.85, "bid")
        assert len(levels) == 10

    def test_bid_price_floor(self):
        levels = _build_levels(0.02, 0.05, 5, 5000.0, 0.85, "bid")
        assert all(lv.price >= 0.01 for lv in levels)

    def test_ask_price_ceiling(self):
        levels = _build_levels(0.98, 0.05, 5, 5000.0, 0.85, "ask")
        assert all(lv.price <= 0.99 for lv in levels)

    def test_size_positive(self):
        levels = _build_levels(0.5, 0.02, 5, 5000.0, 0.85, "bid")
        assert all(lv.size > 0 for lv in levels)


class TestAgeDecay:
    def test_no_trades_returns_low_weight(self):
        weight = _age_decay([], 1000, 0.85)
        assert weight == 0.3

    def test_recent_trade_high_weight(self):
        trades = [_trade(1000, 0.5)]
        weight = _age_decay(trades, 1000, 0.85)
        assert weight > 0.9

    def test_old_trade_lower_weight(self):
        recent = [_trade(1000, 0.5)]
        old = [_trade(1000 - 48 * 3600, 0.5)]
        w_recent = _age_decay(recent, 1000, 0.85)
        w_old = _age_decay(old, 1000, 0.85)
        assert w_recent > w_old

    def test_weight_never_below_min(self):
        very_old = [_trade(0, 0.5)]
        weight = _age_decay(very_old, 365 * 24 * 3600, 0.85)
        assert weight >= 0.1


class TestSynthesizeOrderbook:
    def test_returns_orderbook(self):
        ob = synthesize_orderbook("tok", 1000, [], [])
        assert isinstance(ob, Orderbook)
        assert ob.is_synthetic is True
        assert ob.token_id == "tok"

    def test_bid_ask_spread_positive(self):
        trades = [_trade(i * 100, 0.5) for i in range(10)]
        ob = synthesize_orderbook("tok", 1000, trades, [])
        best_bid = ob.bids[0].price
        best_ask = ob.asks[0].price
        assert best_ask > best_bid

    def test_bids_sorted_descending(self):
        trades = [_trade(i * 100, 0.5) for i in range(10)]
        ob = synthesize_orderbook("tok", 1000, trades, [])
        prices = [lv.price for lv in ob.bids]
        assert prices == sorted(prices, reverse=True)

    def test_asks_sorted_ascending(self):
        trades = [_trade(i * 100, 0.5) for i in range(10)]
        ob = synthesize_orderbook("tok", 1000, trades, [])
        prices = [lv.price for lv in ob.asks]
        assert prices == sorted(prices)

    def test_mid_from_trades(self):
        trades = [_trade(1000, 0.7) for _ in range(5)]
        ob = synthesize_orderbook("tok", 1000, trades, [])
        mid = (ob.bids[0].price + ob.asks[0].price) / 2.0
        assert abs(mid - 0.7) < 0.1

    def test_mid_from_price_bars_when_no_trades(self):
        bars = [_bar(900, 0.65)]
        ob = synthesize_orderbook("tok", 1000, [], bars)
        mid = (ob.bids[0].price + ob.asks[0].price) / 2.0
        assert abs(mid - 0.65) < 0.1

    def test_fallback_mid_050_when_no_data(self):
        ob = synthesize_orderbook("tok", 1000, [], [])
        mid = (ob.bids[0].price + ob.asks[0].price) / 2.0
        assert abs(mid - 0.50) < 0.1

    def test_custom_config_depth_levels(self):
        cfg = SynthesisConfig(depth_levels=3)
        ob = synthesize_orderbook("tok", 1000, [], [], config=cfg)
        assert len(ob.bids) == 3
        assert len(ob.asks) == 3

    def test_all_prices_in_range(self):
        trades = [_trade(i * 100, 0.5) for i in range(10)]
        ob = synthesize_orderbook("tok", 1000, trades, [])
        for lv in ob.bids + ob.asks:
            assert 0.0 < lv.price < 1.0

    def test_timestamp_set_correctly(self):
        ob = synthesize_orderbook("tok", 9999, [], [])
        assert ob.timestamp == 9999

    def test_spread_within_config_bounds(self):
        cfg = SynthesisConfig(min_spread=0.01, max_spread=0.08)
        trades = [_trade(i * 100, 0.5 + 0.05 * (i % 3)) for i in range(20)]
        ob = synthesize_orderbook("tok", 2000, trades, [], config=cfg)
        spread = ob.asks[0].price - ob.bids[0].price
        assert cfg.min_spread <= spread <= cfg.max_spread + 0.01


class TestSynthesizeOrderbookSeries:
    def test_returns_one_per_timestamp(self):
        timestamps = [1000, 2000, 3000]
        result = synthesize_orderbook_series("tok", timestamps, [], [])
        assert len(result) == 3

    def test_timestamps_preserved(self):
        timestamps = [1000, 2000]
        result = synthesize_orderbook_series("tok", timestamps, [], [])
        assert result[0].timestamp == 1000
        assert result[1].timestamp == 2000

    def test_trades_filtered_by_timestamp(self):
        trades = [_trade(500, 0.4), _trade(1500, 0.6)]
        result = synthesize_orderbook_series("tok", [1000, 2000], trades, [])
        mid_at_1000 = (result[0].bids[0].price + result[0].asks[0].price) / 2.0
        mid_at_2000 = (result[1].bids[0].price + result[1].asks[0].price) / 2.0
        assert abs(mid_at_1000 - 0.4) < 0.1
        assert abs(mid_at_2000 - 0.5) < 0.15
