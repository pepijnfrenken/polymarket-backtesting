from __future__ import annotations

from collections import defaultdict

import pandas as pd

from pmdata.models import PriceBar, PricePoint

_INTERVAL_SECONDS: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "6h": 21600,
    "1d": 86400,
}


def compute_ohlcv(
    points: list[PricePoint],
    interval: str = "1m",
) -> list[PriceBar]:
    if not points:
        return []
    bucket_secs = _INTERVAL_SECONDS.get(interval)
    if bucket_secs is None:
        raise ValueError(f"Unknown interval {interval!r}. Valid: {list(_INTERVAL_SECONDS)}")

    buckets: dict[int, list[PricePoint]] = defaultdict(list)
    for pt in points:
        key = (pt.t // bucket_secs) * bucket_secs
        buckets[key].append(pt)

    bars: list[PriceBar] = []
    for ts in sorted(buckets):
        bucket = buckets[ts]
        prices = [p.p for p in bucket]
        bars.append(
            PriceBar(
                timestamp=ts,
                open=prices[0],
                high=max(prices),
                low=min(prices),
                close=prices[-1],
                volume=float(len(prices)),
            )
        )
    return bars


def to_dataframe(bars: list[PriceBar]) -> pd.DataFrame:
    if not bars:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
    return pd.DataFrame(
        [b.model_dump() for b in bars],
    ).set_index("timestamp")


def resample_bars(bars: list[PriceBar], target_interval: str) -> list[PriceBar]:
    if not bars:
        return []
    src_secs = _infer_interval_secs(bars)
    tgt_secs = _INTERVAL_SECONDS.get(target_interval)
    if tgt_secs is None:
        raise ValueError(f"Unknown target interval {target_interval!r}")
    if tgt_secs < src_secs:
        raise ValueError("Cannot resample to a finer interval than source data")

    df = to_dataframe(bars).reset_index()
    df["bucket"] = (df["timestamp"] // tgt_secs) * tgt_secs
    agg = (
        df.groupby("bucket")
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        .reset_index()
    )
    return [
        PriceBar(
            timestamp=int(row["bucket"]),
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"],
        )
        for _, row in agg.iterrows()
    ]


def _infer_interval_secs(bars: list[PriceBar]) -> int:
    if len(bars) < 2:
        return 60
    gaps = [bars[i + 1].timestamp - bars[i].timestamp for i in range(min(10, len(bars) - 1))]
    return int(sorted(gaps)[len(gaps) // 2]) or 60
