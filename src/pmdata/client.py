from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pmdata.api.clob import ClobClient
from pmdata.api.gamma import GammaClient
from pmdata.api.subgraph import SubgraphClient
from pmdata.cache.impl import ParquetPriceCache, SQLiteMetadataCache
from pmdata.models import Market, Orderbook, PriceBar, PricePoint, Trade
from pmdata.synthesis.ohlcv import compute_ohlcv, to_dataframe
from pmdata.synthesis.orderbook import SynthesisConfig, synthesize_orderbook

if TYPE_CHECKING:
    from pathlib import Path

    import pandas as pd


class PolymarketData:
    def __init__(
        self,
        cache_dir: Path | None = None,
        clob_timeout: float = 30.0,
        gamma_timeout: float = 30.0,
        subgraph_timeout: float = 60.0,
    ) -> None:
        self._clob = ClobClient(timeout=clob_timeout)
        self._gamma = GammaClient(timeout=gamma_timeout)
        self._subgraph = SubgraphClient(timeout=subgraph_timeout)
        self._price_cache = ParquetPriceCache(cache_dir=cache_dir)
        self._meta_cache = SQLiteMetadataCache(cache_dir=cache_dir)

    def get_markets(
        self,
        active: bool | None = None,
        closed: bool | None = None,
        limit: int = 100,
        order: str | None = None,
        ascending: bool | None = None,
        start_date_min: str | None = None,
        start_date_max: str | None = None,
    ) -> list[Market]:
        return self._gamma.get_markets(
            active=active,
            closed=closed,
            limit=limit,
            order=order,
            ascending=ascending,
            start_date_min=start_date_min,
            start_date_max=start_date_max,
        )

    def get_all_markets(
        self,
        active: bool | None = None,
        closed: bool | None = None,
        order: str | None = None,
        ascending: bool | None = None,
        start_date_min: str | None = None,
        start_date_max: str | None = None,
    ) -> list[Market]:
        return self._gamma.iter_all_markets(
            active=active,
            closed=closed,
            order=order,
            ascending=ascending,
            start_date_min=start_date_min,
            start_date_max=start_date_max,
        )

    def get_market(self, market_id: str) -> Market:
        cached = self._meta_cache.load_market(market_id)
        if cached:
            return Market(**cached)
        market = self._gamma.get_market(market_id)
        self._meta_cache.save_market(market_id, market.model_dump())
        return market

    def get_raw_prices(
        self,
        token_id: str,
        start: datetime | int,
        end: datetime | int,
        fidelity: int = 1,
    ) -> list[PricePoint]:
        return self._clob.get_prices_history(
            token_id=token_id,
            start_ts=_to_ts(start),
            end_ts=_to_ts(end),
            fidelity=fidelity,
        )

    def get_ohlcv(
        self,
        token_id: str,
        start: datetime | int,
        end: datetime | int,
        interval: str = "1m",
        use_cache: bool = True,
        fidelity: int = 1,
    ) -> pd.DataFrame:
        start_ts = _to_ts(start)
        end_ts = _to_ts(end)

        # Skip cache when fidelity != 1 to avoid serving wrong data
        if use_cache and fidelity == 1 and self._price_cache.has_bars(token_id):
            df = self._price_cache.load_bars(token_id)
            if df is not None and not df.empty:
                idx = df.index
                mask = (idx >= start_ts) & (idx <= end_ts)
                sliced = df.loc[mask]
                if not sliced.empty:
                    return sliced

        points = self._clob.get_prices_history(
            token_id=token_id,
            start_ts=start_ts,
            end_ts=end_ts,
            fidelity=fidelity,
        )
        bars = compute_ohlcv(points, interval=interval)
        df = to_dataframe(bars)
        # Only cache when fidelity == 1 to avoid coherency issues
        if use_cache and fidelity == 1:
            self._price_cache.save_bars(token_id, df)
            self._meta_cache.save_fetch_info(token_id, start_ts, end_ts)
        return df

    def get_trades(
        self,
        token_id: str,
        start: datetime | int,
        end: datetime | int,
    ) -> list[Trade]:
        return self._subgraph.get_order_filled_events(
            token_id=token_id,
            start_ts=_to_ts(start),
            end_ts=_to_ts(end),
        )

    def get_live_orderbook(self, token_id: str) -> Orderbook:
        return self._clob.get_orderbook(token_id)

    def get_synthetic_orderbook(
        self,
        token_id: str,
        timestamp: datetime | int,
        lookback_days: int = 7,
        config: SynthesisConfig | None = None,
    ) -> Orderbook:
        ts = _to_ts(timestamp)
        start_ts = ts - lookback_days * 86400

        trades = self._subgraph.get_order_filled_events(
            token_id=token_id,
            start_ts=start_ts,
            end_ts=ts,
        )
        bars_df = self.get_ohlcv(
            token_id=token_id,
            start=start_ts,
            end=ts,
            interval="1h",
            use_cache=True,
        )
        bars = [
            PriceBar(
                timestamp=int(idx),
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )
            for idx, row in bars_df.iterrows()
        ]
        return synthesize_orderbook(
            token_id=token_id,
            timestamp=ts,
            recent_trades=trades,
            price_bars=bars,
            config=config,
        )

    def fetch_and_cache(
        self,
        token_id: str,
        days: int = 90,
        interval: str = "1m",
    ) -> pd.DataFrame:
        end_ts = int(time.time())
        start_ts = end_ts - days * 86400
        return self.get_ohlcv(
            token_id=token_id,
            start=start_ts,
            end=end_ts,
            interval=interval,
            use_cache=True,
        )

    def close(self) -> None:
        self._clob.close()
        self._gamma.close()
        self._meta_cache.close()

    def __enter__(self) -> PolymarketData:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _to_ts(value: datetime | int) -> int:
    if isinstance(value, datetime):
        return int(value.replace(tzinfo=UTC).timestamp())
    return int(value)
