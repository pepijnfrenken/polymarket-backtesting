# polymarket-data

Python library for retrieving Polymarket historical price data and synthesizing historical orderbooks.

- Fetch OHLCV price bars for any Polymarket token via the CLOB API
- Reconstruct historical orderbook snapshots using a hybrid trade-event + price-history approach
- Local cache (Parquet for bars, SQLite for metadata) — avoid re-fetching the same data
- Rate-limiting and automatic retry baked in to every API client
- CLI tool (`pmdata`) for one-off data pulls and exploration

## Installation

```bash
pip install polymarket-data
```

Requires Python ≥ 3.11.

## Quickstart

```python
from pmdata import PolymarketData

TOKEN_ID = "21742633143463906290569050155826241533067272736897614950488156847949938836455"

with PolymarketData() as pm:
    # OHLCV bars — returns a pandas DataFrame indexed by timestamp
    df = pm.get_ohlcv(TOKEN_ID, start=1_700_000_000, end=1_700_086_400, interval="1h")
    print(df.head())

    # Raw 1-minute price points
    pts = pm.get_raw_prices(TOKEN_ID, start=1_700_000_000, end=1_700_086_400)
    print(f"{len(pts)} price points")

    # Synthetic orderbook at a specific historical timestamp
    ob = pm.get_synthetic_orderbook(TOKEN_ID, timestamp=1_700_043_200, lookback_days=7)
    print(f"Best bid: {ob.bids[0].price:.4f}  Best ask: {ob.asks[0].price:.4f}")
```

## CLI

```
pmdata --help
pmdata markets  --help
pmdata ohlcv    --help
pmdata prices   --help
pmdata orderbook --help
pmdata fetch    --help
```

### Pull OHLCV bars

```bash
# CSV to stdout
pmdata ohlcv --market <TOKEN_ID> --start 2024-01-01 --end 2024-02-01 --interval 1h

# JSON to file
pmdata ohlcv --market <TOKEN_ID> --start 2024-01-01 --end 2024-02-01 \
             --format json --output bars.json

# Parquet to file
pmdata ohlcv --market <TOKEN_ID> --start 2024-01-01 --end 2024-02-01 \
             --format parquet --output bars.parquet
```

### Pull raw price points

```bash
pmdata prices --market <TOKEN_ID> --start 2024-01-01 --end 2024-01-02
pmdata prices --market <TOKEN_ID> --start 2024-01-01 --end 2024-01-02 --format csv
```

### List markets

```bash
pmdata markets --limit 50
pmdata markets --active --format json
```

### Synthetic orderbook

```bash
pmdata orderbook --market <TOKEN_ID> --timestamp 2024-06-01
pmdata orderbook --market <TOKEN_ID> --timestamp 2024-06-01 \
                 --depth-levels 20 --format table
```

### Fetch and cache

Pre-fetches a token's full history and writes it to the local cache for fast subsequent access.

```bash
pmdata fetch --market <TOKEN_ID> --days 90 --interval 1m
```

## Python API

### `PolymarketData`

The unified client. Use as a context manager or call `.close()` manually.

```python
from pathlib import Path
from pmdata import PolymarketData

pm = PolymarketData(
    cache_dir=Path("/tmp/my_cache"),   # default: ~/.pmdata/cache
    clob_timeout=30.0,
    gamma_timeout=30.0,
    subgraph_timeout=60.0,
)
```

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_markets(active, closed, limit)` | `list[Market]` | Paginated market listing |
| `get_all_markets(active, closed)` | `list[Market]` | Fetch every page automatically |
| `get_market(market_id)` | `Market` | Single market (cached in SQLite) |
| `get_raw_prices(token_id, start, end, fidelity)` | `list[PricePoint]` | Raw `{t, p}` price points |
| `get_ohlcv(token_id, start, end, interval, use_cache)` | `pd.DataFrame` | OHLCV bars indexed by timestamp |
| `get_trades(token_id, start, end)` | `list[Trade]` | On-chain trade events via Goldsky |
| `get_live_orderbook(token_id)` | `Orderbook` | Current live orderbook from CLOB |
| `get_synthetic_orderbook(token_id, timestamp, lookback_days, config)` | `Orderbook` | Reconstructed historical orderbook |
| `fetch_and_cache(token_id, days, interval)` | `pd.DataFrame` | Fetch + persist to Parquet cache |

`start` / `end` / `timestamp` accept either a `datetime` or a Unix integer timestamp.

### OHLCV intervals

`1m`, `5m`, `15m`, `1h`, `6h`, `1d`

### Synthetic orderbook configuration

```python
from pmdata.synthesis.orderbook import SynthesisConfig

config = SynthesisConfig(
    depth_levels=20,
    spread_multiplier=1.5,
    min_spread=0.01,
    max_spread=0.08,
    base_depth_usdc=10_000,
    liquidity_decay=0.85,
)

ob = pm.get_synthetic_orderbook(TOKEN_ID, timestamp=ts, config=config)
```

The synthesizer:
1. Finds the 20 nearest on-chain trades to `timestamp` and computes mid price
2. Falls back to the nearest OHLCV bar close if no trades exist
3. Estimates bid-ask spread from recent price standard deviation x 2
4. Builds depth levels with exponential liquidity decay away from the inside

### Models

```python
from pmdata.models import (
    Interval,        # StrEnum: "1m", "1h", "6h", "1d", ...
    PricePoint,      # {t: int, p: float}
    PriceBar,        # {timestamp, open, high, low, close, volume}
    OrderbookLevel,  # {price, size}
    Orderbook,       # {timestamp, market, token_id, bids, asks, is_synthetic}
    Trade,           # {timestamp, price, size, side, order_id, token_id}
    Market,          # full market metadata
)
```

## Configuration

All settings can be provided via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PMDATA_CLOB_BASE_URL` | `https://clob.polymarket.com` | CLOB API base URL |
| `PMDATA_GAMMA_BASE_URL` | `https://gamma-api.polymarket.com` | Gamma API base URL |
| `PMDATA_SUBGRAPH_URL` | *(Goldsky URL)* | GraphQL subgraph endpoint |
| `PMDATA_CACHE_DIR` | `~/.pmdata/cache` | Local cache directory |

Place them in a `.env` file in your working directory.

## Rate limits

The library enforces Polymarket's published limits automatically:

| Endpoint | Limit |
|----------|-------|
| `/prices-history` | 1 000 req / 10 s |
| `/book` | 1 500 req / 10 s |
| `/markets` | 300 req / 10 s |

Retries on HTTP 429, 500, 502, 503, 504 with exponential back-off (up to 5 attempts).

## Development

```bash
git clone https://github.com/prediction-backtesting/polymarket-data
cd polymarket-data
uv sync --extra dev
uv run pytest
uv run ruff check src/ tests/
```

## License

MIT
