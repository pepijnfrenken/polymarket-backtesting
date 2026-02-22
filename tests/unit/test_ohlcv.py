from __future__ import annotations

import pytest

from pmdata.models import PriceBar, PricePoint
from pmdata.synthesis.ohlcv import _infer_interval_secs, compute_ohlcv, resample_bars, to_dataframe


def _pts(pairs: list[tuple[int, float]]) -> list[PricePoint]:
    return [PricePoint(t=t, p=p) for t, p in pairs]


class TestComputeOhlcv:
    def test_empty_input_returns_empty(self):
        assert compute_ohlcv([]) == []

    def test_unknown_interval_raises(self):
        with pytest.raises(ValueError, match="Unknown interval"):
            compute_ohlcv(_pts([(0, 0.5)]), interval="3m")

    def test_single_point_single_bar(self):
        bars = compute_ohlcv(_pts([(60, 0.5)]), interval="1m")
        assert len(bars) == 1
        b = bars[0]
        assert b.open == b.high == b.low == b.close == 0.5
        assert b.volume == 1.0

    def test_two_points_same_bucket(self):
        bars = compute_ohlcv(_pts([(0, 0.4), (30, 0.6)]), interval="1m")
        assert len(bars) == 1
        b = bars[0]
        assert b.open == 0.4
        assert b.close == 0.6
        assert b.high == 0.6
        assert b.low == 0.4
        assert b.volume == 2.0

    def test_two_points_different_buckets(self):
        bars = compute_ohlcv(_pts([(0, 0.4), (60, 0.6)]), interval="1m")
        assert len(bars) == 2
        assert bars[0].close == 0.4
        assert bars[1].close == 0.6

    def test_bucket_alignment(self):
        bars = compute_ohlcv(_pts([(59, 0.3), (61, 0.7)]), interval="1m")
        assert len(bars) == 2
        assert bars[0].timestamp == 0
        assert bars[1].timestamp == 60

    def test_multiple_bars_ordering(self):
        pts = _pts([(i * 60, float(i) / 10) for i in range(5)])
        bars = compute_ohlcv(pts, interval="1m")
        timestamps = [b.timestamp for b in bars]
        assert timestamps == sorted(timestamps)

    def test_hour_interval(self):
        pts = _pts([(0, 0.5), (1800, 0.6), (3600, 0.7)])
        bars = compute_ohlcv(pts, interval="1h")
        assert len(bars) == 2
        assert bars[0].volume == 2.0
        assert bars[1].volume == 1.0

    def test_volume_is_point_count(self):
        pts = _pts([(i * 10, 0.5) for i in range(6)])
        bars = compute_ohlcv(pts, interval="1m")
        assert bars[0].volume == 6.0


class TestToDataframe:
    def test_empty_returns_empty_df(self):
        df = to_dataframe([])
        assert df.empty
        assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]

    def test_index_is_timestamp(self):
        bars = compute_ohlcv(_pts([(0, 0.5), (60, 0.6)]), interval="1m")
        df = to_dataframe(bars)
        assert df.index.name == "timestamp"
        assert len(df) == 2

    def test_column_names(self):
        bars = compute_ohlcv(_pts([(0, 0.5)]), interval="1m")
        df = to_dataframe(bars)
        assert set(df.columns) == {"open", "high", "low", "close", "volume"}


class TestResampleBars:
    def _make_1m_bars(self, n: int) -> list[PriceBar]:
        return [
            PriceBar(timestamp=i * 60, open=0.5, high=0.6, low=0.4, close=0.55, volume=1.0)
            for i in range(n)
        ]

    def test_empty_returns_empty(self):
        assert resample_bars([], "1h") == []

    def test_unknown_target_raises(self):
        bars = self._make_1m_bars(60)
        with pytest.raises(ValueError, match="Unknown target interval"):
            resample_bars(bars, "3m")

    def test_finer_interval_raises(self):
        bars = [
            PriceBar(timestamp=i * 3600, open=0.5, high=0.6, low=0.4, close=0.55, volume=10.0)
            for i in range(5)
        ]
        with pytest.raises(ValueError, match="finer"):
            resample_bars(bars, "1m")

    def test_1m_to_1h(self):
        bars = self._make_1m_bars(120)
        resampled = resample_bars(bars, "1h")
        assert len(resampled) == 2
        for r in resampled:
            assert r.volume == 60.0

    def test_ohlcv_aggregation_correctness(self):
        bars = [
            PriceBar(timestamp=0, open=0.1, high=0.9, low=0.05, close=0.3, volume=5.0),
            PriceBar(timestamp=60, open=0.3, high=0.8, low=0.2, close=0.5, volume=3.0),
        ]
        resampled = resample_bars(bars, "1h")
        assert len(resampled) == 1
        r = resampled[0]
        assert r.open == 0.1
        assert r.high == 0.9
        assert r.low == 0.05
        assert r.close == 0.5
        assert r.volume == 8.0


class TestInferIntervalSecs:
    def test_single_bar_defaults_60(self):
        bars = [PriceBar(timestamp=0, open=0.5, high=0.6, low=0.4, close=0.5, volume=1.0)]
        assert _infer_interval_secs(bars) == 60

    def test_1m_bars(self):
        bars = [
            PriceBar(timestamp=i * 60, open=0.5, high=0.6, low=0.4, close=0.5, volume=1.0)
            for i in range(5)
        ]
        assert _infer_interval_secs(bars) == 60

    def test_1h_bars(self):
        bars = [
            PriceBar(timestamp=i * 3600, open=0.5, high=0.6, low=0.4, close=0.5, volume=1.0)
            for i in range(5)
        ]
        assert _infer_interval_secs(bars) == 3600
