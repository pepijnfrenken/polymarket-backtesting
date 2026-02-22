from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from pmdata.models import Orderbook, OrderbookLevel, PriceBar, Trade


@dataclass
class SynthesisConfig:
    depth_levels: int = 10
    spread_multiplier: float = 1.0
    min_spread: float = 0.01
    max_spread: float = 0.08
    base_depth_usdc: float = 5000.0
    liquidity_decay: float = 0.85


def _estimate_spread(recent_trades: list[Trade]) -> float:
    if len(recent_trades) < 2:
        return 0.02
    prices = [t.price for t in recent_trades[-50:]]
    if len(prices) < 2:
        return 0.02
    stdev = statistics.stdev(prices)
    return max(0.005, min(0.10, stdev * 2.0))


def _build_levels(
    mid: float,
    spread_half: float,
    depth_levels: int,
    base_depth: float,
    decay: float,
    side: str,
) -> list[OrderbookLevel]:
    levels: list[OrderbookLevel] = []
    for i in range(depth_levels):
        offset = spread_half * (1 + i * 0.5)
        if side == "bid":
            price = round(max(0.01, mid - offset), 4)
        else:
            price = round(min(0.99, mid + offset), 4)
        depth = base_depth * (decay**i) / max(price, 1 - price)
        levels.append(OrderbookLevel(price=price, size=round(depth, 2)))
    return levels


def synthesize_orderbook(
    token_id: str,
    timestamp: int,
    recent_trades: list[Trade],
    price_bars: list[PriceBar],
    config: SynthesisConfig | None = None,
) -> Orderbook:
    cfg = config or SynthesisConfig()

    if recent_trades:
        close_to_ts = sorted(recent_trades, key=lambda t: abs(t.timestamp - timestamp))
        closest = close_to_ts[:20]
        mid = statistics.mean(t.price for t in closest)
    elif price_bars:
        close_bar = min(price_bars, key=lambda b: abs(b.timestamp - timestamp))
        mid = close_bar.close
    else:
        mid = 0.50

    mid = max(0.01, min(0.99, mid))

    raw_spread = _estimate_spread(recent_trades) if recent_trades else 0.02
    spread = max(cfg.min_spread, min(cfg.max_spread, raw_spread * cfg.spread_multiplier))
    spread_half = spread / 2.0

    age_weight = _age_decay(recent_trades, timestamp, cfg.liquidity_decay)
    effective_depth = cfg.base_depth_usdc * age_weight

    bids = _build_levels(
        mid, spread_half, cfg.depth_levels, effective_depth, cfg.liquidity_decay, "bid"
    )
    asks = _build_levels(
        mid, spread_half, cfg.depth_levels, effective_depth, cfg.liquidity_decay, "ask"
    )

    return Orderbook(
        timestamp=timestamp,
        market="",
        token_id=token_id,
        bids=sorted(bids, key=lambda lv: lv.price, reverse=True),
        asks=sorted(asks, key=lambda lv: lv.price),
        is_synthetic=True,
    )


def _age_decay(trades: list[Trade], target_ts: int, decay: float) -> float:
    if not trades:
        return 0.3
    nearest = min(trades, key=lambda t: abs(t.timestamp - target_ts))
    age_hours = abs(nearest.timestamp - target_ts) / 3600.0
    return max(0.1, math.exp(-decay * age_hours / 24.0))


def synthesize_orderbook_series(
    token_id: str,
    timestamps: list[int],
    all_trades: list[Trade],
    price_bars: list[PriceBar],
    config: SynthesisConfig | None = None,
) -> list[Orderbook]:
    return [
        synthesize_orderbook(
            token_id=token_id,
            timestamp=ts,
            recent_trades=[t for t in all_trades if t.timestamp <= ts],
            price_bars=[b for b in price_bars if b.timestamp <= ts],
            config=config,
        )
        for ts in timestamps
    ]
