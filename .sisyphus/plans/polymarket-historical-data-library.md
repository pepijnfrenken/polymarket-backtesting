# Polymarket Historical Data Library - Implementation Plan

## TL;DR

> **Quick Summary**: Build a production-grade Python library for retrieving Polymarket historical price data and synthesizing historical orderbooks using a hybrid approach (trade events + price history).
> 
> **Deliverables**:
> - Python package `polymarket-data` with pip install
> - Price history fetching (1-minute bars) from CLOB API
> - Historical orderbook synthesis from Goldsky subgraph trade events
> - OHLCV computation from raw price points
> - Caching layer (Parquet + SQLite)
> - CLI for data retrieval
> 
> **Estimated Effort**: Medium (20+ files, 1500+ lines)
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Core models → Price fetcher → Orderbook synthesis → CLI

---

## Context

### Original Request
Build a Python library to:
1. Retrieve Polymarket historical price data reliably
2. Determine if historical orderbooks are retrievable
3. If not retrievable, allow synthetic creation based on factual data

### User Requirements (Confirmed)
- **Time Range**: 3-12 months of historical data
- **Orderbook Priority**: Critical (need accurate historical orderbook for slippage)
- **Data Frequency**: 1-minute bars
- **Synthetic Approach**: Hybrid (trade events + price history)

### Research Findings
- **Price History**: Available via CLOB API `/prices-history` endpoint (returns raw price points)
- **Orderbook**: NOT directly available historically - must use synthetic approach
- **Trade Events**: Available via Goldsky subgraph `orderFilledEvent`
- **APIs**: Gamma (markets), CLOB (prices/orderbook), Subgraphs (GraphQL)

---

## Work Objectives

### Core Objective
Deliver a Python library enabling traders to:
1. Fetch historical price data (OHLCV) from Polymarket CLOB API
2. Synthesize historical orderbooks from trade events + price history
3. Cache data locally for fast subsequent access
4. Provide CLI for easy data retrieval

### Concrete Deliverables
- `src/pmdata/__init__.py` - Package root
- `src/pmdata/client.py` - Main client class
- `src/pmdata/api/clob.py` - CLOB API client (prices, orderbook)
- `src/pmdata/api/gamma.py` - Gamma API client (markets)
- `src/pmdata/api/subgraph.py` - GraphQL subgraph client (trade events)
- `src/pmdata/models.py` - Data models (PriceBar, Orderbook, Trade)
- `src/pmdata/synthesis/orderbook.py` - Orderbook synthesis engine
- `src/pmdata/synthesis/ohlcv.py` - OHLCV computation
- `src/pmdata/cache/__init__.py` - Cache management
- `src/pmdata/cache/parquet.py` - Parquet storage for price data
- `src/pmdata/cache/sqlite.py` - SQLite for metadata
- `src/pmdata/cli/__init__.py` - CLI commands
- `tests/` - Unit and integration tests
- `pyproject.toml` - Package configuration
- `README.md` - Documentation

### Definition of Done
- [ ] `pip install polymarket-data` works
- [ ] `pmdata prices --market <token_id> --start 2024-01-01 --end 2024-12-31 --interval 1m` returns OHLCV DataFrame
- [ ] `pmdata orderbook --market <token_id> --timestamp <ts>` returns synthetic orderbook
- [ ] `pmdata fetch --market <token_id> --days 90` fetches and caches 90 days of data
- [ ] Data cached in Parquet format
- [ ] All models serialize to/from dict
- [ ] Type hints throughout
- [ ] Error handling with retry logic

### Must Have
- Type hints throughout
- Error handling with retry logic (tenacity)
- Rate limit handling
- Pagination support for API calls
- Configuration via environment variables
- Synthetic orderbook generation from trade events
- OHLCV computation from raw price points

### Must NOT Have
- Hardcoded API keys (use environment variables)
- Blocking calls in async context
- Global mutable state
- Unbounded memory usage for large datasets

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: NO (fresh library)
- **Automated tests**: YES - Tests after implementation
- **Framework**: pytest + pytest-asyncio
- **Coverage Target**: 80%+

### QA Policy
Every task includes agent-executed QA scenarios:
- **API fetch**: Verify response parsing, error handling
- **OHLCV**: Compare computed OHLCV against manual calculation
- **Orderbook synthesis**: Verify bid/ask levels generated correctly
- **CLI**: Run each command, verify help text and output

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation - 6 tasks):
├── T1: Project scaffolding + pyproject.toml
├── T2: Core data models (PriceBar, Orderbook, Trade, Market)
├── T3: CLOB API client (prices-history, orderbook endpoints)
├── T4: Gamma API client (markets, events)
├── T5: GraphQL subgraph client (orderFilledEvents)
└── T6: Cache base classes (Parquet + SQLite)

Wave 2 (Core Logic - 5 tasks):
├── T7: OHLCV computation from price points
├── T8: Orderbook synthesis engine (hybrid approach)
├── T9: Main client class (unified interface)
├── T10: Rate limiting + retry logic
└── T11: Cache implementation (Parquet + SQLite)

Wave 3 (CLI & Polish - 4 tasks):
├── T12: CLI commands (prices, orderbook, fetch, markets)
├── T13: Tests (unit + integration)
├── T14: README + examples
└── T15: Final verification
```

### Dependency Matrix
- **T1**: — — T2-T6
- **T2**: T1 — T3-T6
- **T3**: T2 — T7-T11
- **T4**: T2 — T7-T11
- **T5**: T2 — T8 (synthesis needs trade events)
- **T6**: T1 — T11 (cache implementation)
- **T7**: T3 — T9
- **T8**: T3, T5 — T9 (synthesis needs both APIs)
- **T9**: T7, T8, T11 — T12
- **T10**: T3 — T12
- **T11**: T6, T9 — T12
- **T12**: T9-T11 — T13
- **T13**: T12 — T14
- **T14**: T13 — T15

---

## TODOs

### Wave 1: Foundation

- [ ] 1. **Project scaffolding + pyproject.toml**

  **What to do**:
  - Create directory structure: `src/pmdata/{api,cache,synthesis,cli}`
  - Create `pyproject.toml` with dependencies:
    - `requests` - HTTP client
    - `httpx` - Async HTTP (optional)
    - `gql` - GraphQL client
    - `pandas` - Data manipulation
    - `pyarrow` - Parquet support
    - `tenacity` - Retry logic
    - `click` - CLI
    - `pydantic` - Data validation
    - `python-dotenv` - Environment config
  - Create `__init__.py` files
  - Create `.env.example`

  **References**:
  - Python packaging: `https://packaging.python.org/en/latest/tutorials/packaging-projects/`
  - py-clob-client patterns: `https://github.com/Polymarket/py-clob-client`

  **Acceptance Criteria**:
  - [ ] `pip install -e .` installs package
  - [ ] `python -m pmdata --help` works

- [ ] 2. **Core data models**

  **What to do**:
  - Define dataclasses using Pydantic:
    - `PricePoint`: timestamp, price
    - `PriceBar`: timestamp, open, high, low, close, volume
    - `OrderbookLevel`: price, size
    - `Orderbook`: timestamp, bids, asks, market, token_id
    - `Trade`: timestamp, price, size, side, order_id
    - `Market`: id, question, clob_token_ids, outcomes, resolved_date
  - Add validation with Pydantic
  - Add serialization (dict, json)

  **References**:
  - Pydantic docs: `https://docs.pydantic.dev/`

  **Acceptance Criteria**:
  - [ ] All models serialize to/from JSON
  - [ ] Validation catches invalid data

- [ ] 3. **CLOB API client**

  **What to do**:
  - Implement `ClobClient` class
  - Implement `get_prices_history()`:
    - Endpoint: `GET /prices-history`
    - Params: market, startTs, endTs, interval, fidelity
    - Returns: List[PricePoint]
  - Implement `get_orderbook()`:
    - Endpoint: `GET /book`
    - Params: token_id
    - Returns: Orderbook
  - Add rate limit handling (1,000 req/10s for prices)
  - Add retry logic with exponential backoff

  **References**:
  - CLOB API docs: `https://docs.polymarket.com/api-reference/markets/get-prices-history`

  **Acceptance Criteria**:
  - [ ] `client.get_prices_history("0xtoken", start, end)` returns price points
  - [ ] `client.get_orderbook("0xtoken")` returns Orderbook

- [ ] 4. **Gamma API client**

  **What to do**:
  - Implement `GammaClient` class
  - Implement `get_markets()`:
    - Endpoint: `GET /markets`
    - Params: active, closed, limit, cursor, etc.
    - Returns: List[Market]
  - Implement `get_market()`:
    - Endpoint: `GET /markets/{id}`
  - Implement `get_events()`:
    - Endpoint: `GET /events`
  - Parse `clobTokenIds` from market response

  **References**:
  - Gamma API: `https://gamma-api.polymarket.com`

  **Acceptance Criteria**:
  - [ ] `client.get_markets(active=True)` returns markets with token IDs

- [ ] 5. **GraphQL subgraph client**

  **What to do**:
  - Implement `SubgraphClient` class using `gql` library
  - Implement `get_order_filled_events()`:
    - Endpoint: Goldsky Orders subgraph
    - Query: orderFilledEvents
    - Filters: token_id, timestamp_gte, timestamp_lte, first, skip
    - Returns: List[Trade]
  - Implement `get_market_data()`:
    - Query: marketData
  - Add pagination support for large result sets

  **References**:
  - Orders subgraph: `https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw/subgraphs/orderbook-subgraph/0.0.1/gn`

  **Acceptance Criteria**:
  - [ ] `client.get_order_filled_events("0xtoken", start, end)` returns trades

- [ ] 6. **Cache base classes**

  **What to do**:
  - Define `Cache` abstract base class
  - Define `PriceCache` interface
  - Define `OrderbookCache` interface
  - Define schema for cached data

  **References**:
  - PyArrow Parquet: `https://arrow.apache.org/docs/python/parquet.html`

  **Acceptance Criteria**:
  - [ ] Cache interfaces defined
  - [ ] Schema documented

### Wave 2: Core Logic

- [ ] 7. **OHLCV computation**

  **What to do**:
  - Implement `compute_ohlcv()` function
  - Input: List[PricePoint], interval (1m, 5m, 1h, 1d)
  - Output: List[PriceBar]
  - Algorithm:
    1. Group price points by time bucket
    2. open = first price in bucket
    3. high = max price in bucket
    4. low = min price in bucket
    5. close = last price in bucket
    6. volume = count of trades (approximate from price changes)
  - Handle edge cases: single point, gaps, partial buckets

  **Acceptance Criteria**:
  - [ ] 1-minute interval produces correct OHLCV
  - [ ] 1-hour interval produces correct OHLCV

- [ ] 8. **Orderbook synthesis engine**

  **What to do**:
  - Implement `OrderbookSynthesizer` class
  - Strategy: Hybrid approach
    1. Get trade events from subgraph for time window
    2. Build price distribution from trade prices
    3. Estimate bid/ask spread from recent trades
    4. Generate synthetic depth levels around each trade price
    5. Apply liquidity decay model (older = less depth)
  - Implement methods:
    - `synthesize_orderbook(token_id, timestamp)` - Single snapshot
    - `synthesize_orderbook_series(token_id, start, end, freq)` - Time series
  - Add configuration:
    - `spread_multiplier`: Multiplier for spread estimation
    - `depth_levels`: Number of price levels to generate
    - `liquidity_decay`: Decay factor for older data

  **Acceptance Criteria**:
  - [ ] Synthesized orderbook has bids < asks
  - [ ] Spread matches recent trade activity
  - [ ] Price levels are realistic (within 5% of mid)

- [ ] 9. **Main client class**

  **What to do**:
  - Implement `PolymarketData` client class
  - Compose: ClobClient, GammaClient, SubgraphClient, Cache
  - Implement unified interface:
    - `get_markets()` → List[Market]
    - `get_prices(token_id, start, end, interval)` → DataFrame
    - `get_ohlcv(token_id, start, end, interval)` → DataFrame
    - `get_orderbook(token_id, timestamp)` → Orderbook
    - `synthesize_orderbook(token_id, timestamp)` → Orderbook
    - `fetch_and_cache(token_id, days)` → None
  - Add convenience methods:
    - `list_markets()` - Quick market listing
    - `get_market_by_question()` - Search by question

  **Acceptance Criteria**:
  - [ ] Single client can fetch prices, OHLCV, orderbooks
  - [ ] Unified error handling

- [ ] 10. **Rate limiting + retry logic**

  **What to do**:
  - Implement `RateLimiter` class
  - Track requests per time window
  - Implement backoff strategies:
    - Exponential backoff on 429 errors
    - Per-endpoint rate limit tracking
  - Add tenacity decorators:
    - `@retry` for transient failures
    - `@retry_with_backoff` for rate limits

  **Acceptance Criteria**:
  - [ ] Respects CLOB rate limits (1,000/10s prices, 1,500/10s book)
  - [ ] Retries on transient failures

- [ ] 11. **Cache implementation**

  **What to do**:
  - Implement `ParquetPriceCache`:
    - Store OHLCV in Parquet files
    - Partition by market/token_id and date
    - Read/write methods
  - Implement `SQLiteMetadataCache`:
    - Store market metadata
    - Store fetch timestamps
    - Store synthesis parameters
  - Implement `CacheManager`:
    - Coordinate between caches
    - Check cache before API calls
    - Invalidate stale data

  **Acceptance Criteria**:
  - [ ] Prices cached and retrieved correctly
  - [ ] Stale data detected and refreshed

### Wave 3: CLI & Polish

- [ ] 12. **CLI commands**

  **What to do**:
  - Implement `pmdata` CLI using Click
  - Commands:
    - `pmdata markets` - List available markets
    - `pmdata prices` - Fetch raw price history
    - `pmdata ohlcv` - Fetch OHLCV bars
    - `pmdata orderbook` - Get/synthesize orderbook
    - `pmdata fetch` - Fetch and cache data
  - Options:
    - `--market`, `--start`, `--end`, `--interval`
    - `--output` (file path or stdout)
    - `--format` (json, csv, parquet)
  - Add help text and examples

  **Acceptance Criteria**:
  - [ ] `pmdata --help` shows all commands
  - [ ] Each command works end-to-end

- [ ] 13. **Tests**

  **What to do**:
  - Unit tests for models
  - Unit tests for OHLCV computation
  - Unit tests for orderbook synthesis
  - Integration tests for API clients (mocked responses)
  - Test fixtures for common scenarios

  **Acceptance Criteria**:
  - [ ] `pytest` passes
  - [ ] 80%+ coverage

- [ ] 14. **README + examples**

  **What to do**:
  - Write comprehensive README
  - Include:
    - Installation instructions
    - Quick start guide
    - API reference
    - CLI usage examples
    - Configuration guide
  - Add example scripts in `examples/`

  **Acceptance Criteria**:
  - [ ] README explains all features

- [ ] 15. **Final verification**

  **What to do**:
  - Run full fetch on real market
  - Verify OHLCV computation accuracy
  - Verify orderbook synthesis quality
  - Test CLI end-to-end

  **Acceptance Criteria**:
  - [ ] All features work with real data

---

## Final Verification Wave

- [ ] F1. **Plan Compliance Audit** — Verify all deliverables present
- [ ] F2. **Code Quality Review** — Type checking (mypy), linting (ruff)
- [ ] F3. **Real Manual QA** — Run actual data fetch with real Polymarket API
- [ ] F4. **Scope Fidelity Check** — Verify no creep

---

## Commit Strategy

- **1**: `feat(core): Add data models and API clients` (T1-T5)
- **2**: `feat(synthesis): Add OHLCV and orderbook synthesis` (T7-T8)
- **3**: `feat(client): Add unified client and caching` (T9-T11)
- **4**: `feat(cli): Add CLI commands` (T12)
- **5**: `test: Add unit and integration tests` (T13)
- **6**: `docs: Add README and examples` (T14)

---

## Success Criteria

### Verification Commands
```bash
pip install -e .
python -m pmdata --help
pmdata markets --limit 10
pmdata ohlcv --market 0xtoken --start 2024-01-01 --end 2024-03-01 --interval 1m
pmdata orderbook --market 0xtoken --timestamp 1704067200
pmdata fetch --market 0xtoken --days 90
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] OHLCV computation correct
- [ ] Orderbook synthesis generates realistic data
- [ ] Rate limiting respects API limits
- [ ] Caching works correctly
- [ ] CLI functional
