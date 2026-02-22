from __future__ import annotations

import datetime
import sys

from pmdata import PolymarketData

TOKEN_ID = "21742633143463906290569050155826241533067272736897614950488156847949938836455"
end_dt = datetime.datetime(2024, 11, 5, tzinfo=datetime.UTC)
start_dt = end_dt - datetime.timedelta(days=7)
end_ts = int(end_dt.timestamp())
start_ts = int(start_dt.timestamp())

with PolymarketData() as pm:
    df = pm.get_ohlcv(TOKEN_ID, start=start_ts, end=end_ts, interval="1h")

if df.empty:
    print("No data returned — token may be inactive or too new.", file=sys.stderr)
    sys.exit(1)

print(f"Fetched {len(df)} hourly bars")
print(f"Range:  {df.index.min()} -> {df.index.max()}")
print()
print(df.head(10).to_string())
