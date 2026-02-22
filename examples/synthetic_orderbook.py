from __future__ import annotations

import time

from pmdata import PolymarketData
from pmdata.synthesis.orderbook import SynthesisConfig

TOKEN_ID = "21742633143463906290569050155826241533067272736897614950488156847949938836455"

target_ts = int(time.time()) - 3 * 86400

config = SynthesisConfig(depth_levels=5, min_spread=0.01, max_spread=0.06)

with PolymarketData() as pm:
    ob = pm.get_synthetic_orderbook(TOKEN_ID, timestamp=target_ts, lookback_days=14, config=config)

print(f"Synthetic orderbook for {ob.token_id}")
print(f"Timestamp: {ob.timestamp}")
print(f"{'BID':>10}  {'SIZE':>10}  {'ASK':>10}  {'SIZE':>10}")
for bid, ask in zip(ob.bids, ob.asks, strict=False):
    print(f"{bid.price:>10.4f}  {bid.size:>10.2f}  {ask.price:>10.4f}  {ask.size:>10.2f}")
