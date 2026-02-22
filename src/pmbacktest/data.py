"""Data feed integration for historical market data."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from pmbacktest.strategies import Bar
from pmbacktest.types import Outcome

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pmdata.client import PolymarketData


# Type alias for price data
Prices = dict[str, dict[Outcome, float]]


@dataclass
class MarketDataPoint:
    """Single point of market data."""

    timestamp: int
    prices: dict[str, dict[Outcome, float]]
    bars: dict[str, Bar] = field(default_factory=dict)


class MarketDataFeed:
    """Data feed that iterates through historical market data.

    This class provides an iterator interface for feeding historical
    price data into the backtest engine.

    Attributes:
        data: List of MarketDataPoint sorted by timestamp
        interval: Time interval between data points
    """

    def __init__(
        self,
        data: list[MarketDataPoint] | None = None,
        interval: str = "1h",
    ):
        """Initialize data feed.

        Args:
            data: List of market data points
            interval: Time interval ("1m", "5m", "15m", "1h", "6h", "1d")
        """
        self._data = data or []
        self.interval = interval
        self._index = 0

    def __len__(self) -> int:
        """Return number of data points."""
        return len(self._data)

    def __iter__(self) -> Iterator[MarketDataPoint]:
        """Iterate through data points."""
        self._index = 0
        return self

    def __next__(self) -> MarketDataPoint:
        """Get next data point."""
        if self._index >= len(self._data):
            raise StopIteration
        point = self._data[self._index]
        self._index += 1
        return point

    def add_data_point(self, point: MarketDataPoint) -> None:
        """Add a data point to the feed.

        Args:
            point: Market data point to add
        """
        self._data.append(point)

    def sort(self) -> None:
        """Sort data by timestamp."""
        self._data.sort(key=lambda x: x.timestamp)

    def get_price_range(
        self,
        market_id: str,
        start_ts: int,
        end_ts: int,
    ) -> list[tuple[int, float]]:
        """Get price range for a market.

        Args:
            market_id: Market identifier
            start_ts: Start timestamp
            end_ts: End timestamp

        Returns:
            List of (timestamp, price) tuples
        """
        result = []
        for point in self._data:
            if start_ts <= point.timestamp <= end_ts:
                prices = point.prices.get(market_id, {})
                if Outcome.YES in prices:
                    result.append((point.timestamp, prices[Outcome.YES]))
        return result


class MockDataFeed(MarketDataFeed):
    """Generate mock data for testing.

    Attributes:
        num_points: Number of data points to generate
        num_markets: Number of markets to simulate
    """

    def __init__(
        self,
        num_points: int = 100,
        num_markets: int = 1,
        start_price: float = 0.5,
        interval: str = "1h",
    ):
        """Initialize mock data feed.

        Args:
            num_points: Number of data points
            num_markets: Number of markets
            start_price: Starting price
            interval: Time interval
        """
        import random

        super().__init__(interval=interval)

        base_ts = int(datetime(2024, 1, 1).timestamp())
        interval_seconds = self._get_interval_seconds()

        for i in range(num_points):
            timestamp = base_ts + i * interval_seconds
            prices = {}
            bars = {}

            for m in range(num_markets):
                market_id = f"market_{m}"
                # Random walk with mean reversion
                change = random.gauss(0, 0.02)
                price = 0.5 + change
                price = max(0.05, min(0.95, price))  # Clamp

                prices[market_id] = {
                    Outcome.YES: price,
                    Outcome.NO: 1 - price,
                }

                # Generate bar
                open_price = price
                high_price = price + abs(random.gauss(0, 0.01))
                low_price = price - abs(random.gauss(0, 0.01))
                close_price = price + random.gauss(0, 0.005)
                close_price = max(0.01, min(0.99, close_price))

                bars[market_id] = Bar(
                    timestamp=timestamp,
                    open=open_price,
                    high=high_price,
                    low=low_price,
                    close=close_price,
                    volume=random.uniform(1000, 10000),
                )

            self._data.append(
                MarketDataPoint(
                    timestamp=timestamp,
                    prices=prices,
                    bars=bars,
                )
            )

    def _get_interval_seconds(self) -> int:
        """Convert interval string to seconds."""
        mapping = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "1h": 3600,
            "6h": 21600,
            "1d": 86400,
        }
        return mapping.get(self.interval, 3600)


def create_data_feed_from_pmdata(
    pmdata_client: PolymarketData,
    market_ids: list[str],
    start: int | datetime,
    end: int | datetime,
    interval: str = "1h",
) -> MarketDataFeed:
    """Create data feed from PolymarketData client.

    Args:
        pmdata_client: PolymarketData instance
        market_ids: List of market IDs (condition IDs or Gamma market IDs)
        start: Start timestamp (unix int or datetime)
        end: End timestamp (unix int or datetime)
        interval: OHLCV interval ("1m", "5m", "15m", "1h", "6h", "1d")

    Returns:
        MarketDataFeed with historical data sorted by timestamp

    Raises:
        ValueError: If a market has more than 2 outcomes (non-binary market)
    """
    # Collect per-market data: {market_id: {timestamp: (Bar, yes_price)}}
    market_ts_data: dict[str, dict[int, tuple[Bar, float]]] = {}

    for market_id in market_ids:
        market = pmdata_client.get_market(market_id)

        if len(market.outcomes) != 2:
            raise ValueError(
                f"Market {market_id!r} has {len(market.outcomes)} outcomes; "
                "only binary markets (exactly 2 outcomes) are supported."
            )

        # Find YES token id case-insensitively
        yes_token_id: str | None = None
        for outcome_label, token_id in zip(market.outcomes, market.clob_token_ids, strict=True):
            if outcome_label.lower() == Outcome.YES:
                yes_token_id = token_id
                break

        if yes_token_id is None:
            warnings.warn(
                f"Market {market_id!r} has no 'yes' outcome; skipping.",
                stacklevel=2,
            )
            continue

        df = pmdata_client.get_ohlcv(yes_token_id, start, end, interval)

        if df is None or df.empty:
            warnings.warn(
                f"Market {market_id!r} returned empty OHLCV data; skipping.",
                stacklevel=2,
            )
            continue

        ts_map: dict[int, tuple[Bar, float]] = {}
        for idx, row in df.iterrows():
            ts = int(idx)
            bar = Bar(
                timestamp=ts,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            )
            yes_price = float(row["close"])
            ts_map[ts] = (bar, yes_price)

        market_ts_data[market_id] = ts_map

    # Collect union of all timestamps across markets
    all_timestamps: set[int] = set()
    for ts_map in market_ts_data.values():
        all_timestamps.update(ts_map.keys())

    sorted_timestamps = sorted(all_timestamps)

    # Forward-fill: track last known data per market
    last_bar: dict[str, Bar] = {}
    last_yes_price: dict[str, float] = {}

    points: list[MarketDataPoint] = []
    for ts in sorted_timestamps:
        prices: dict[str, dict[Outcome, float]] = {}
        bars: dict[str, Bar] = {}

        for mid, ts_map in market_ts_data.items():
            if ts in ts_map:
                bar, yes_price = ts_map[ts]
                last_bar[mid] = bar
                last_yes_price[mid] = yes_price

            if mid in last_yes_price:
                yp = last_yes_price[mid]
                prices[mid] = {Outcome.YES: yp, Outcome.NO: 1.0 - yp}
                bars[mid] = last_bar[mid]

        points.append(MarketDataPoint(timestamp=ts, prices=prices, bars=bars))

    feed = MarketDataFeed(data=points, interval=interval)
    feed.sort()
    return feed
