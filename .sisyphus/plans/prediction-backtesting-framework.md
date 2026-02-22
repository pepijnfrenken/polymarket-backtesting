# Prediction Market Backtesting Framework - Production Implementation Plan

## TL;DR

> **Quick Summary**: Build a production-grade Python CLI backtesting framework for prediction markets (Polymarket + Kalshi) with modular strategy system, comprehensive metrics, and extensible architecture.
> 
> **Deliverables**:
> - Full Python package with Click CLI (`bt` command)
> - Platform adapters for Polymarket and Kalshi
> - 5 trading strategies (Weather, CopyTrade, CrossArb, Momentum, MeanReversion)
> - Backtest engine with full metrics (Sharpe, Sortino, Calmar, MaxDD, Win%, PF)
> - Deep analysis tools (param sweeps, Monte Carlo, attribution)
> - Docker-ready configuration
> 
> **Estimated Effort**: XL (50+ files, 3000+ lines)
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Core models → Adapters → Strategies → Engine → CLI

---

## Context

### Original Request
Build production-grade Python CLI backtesting framework for prediction markets with:
- Data fetchers (Polymarket py-clob-client + Goldsky subgraph, Kalshi API)
- Pluggable strategies (Weather, CopyTrade, CrossArb, Momentum)
- Backtest engine with replay and full metrics
- CLI commands (fetch, backtest, optimize, compare, analyze)
- Extensibility (PlatformAdapter ABC, MCP integration)

### Market Research (from MCP scan)
- **Polymarket active**: High-volume markets on Fed rates, sports (NBA, Tennis), crypto (Bitcoin), politics
- **Polymarket resolved**: Historical 2020 election markets (Trump win: $10.8M volume)
- **Kalshi settled**: Today's sports markets (Tennis, Soccer, NBA)

### Backtest Candidates Identified
1. Fed interest rate markets (high liquidity, binary resolution)
2. Sports markets (NBA games daily, high volume)
3. Election markets (historical high-volume, clear resolution)
4. Crypto price markets (binary, daily)

---

## Work Objectives

### Core Objective
Deliver a production-ready backtesting framework enabling traders to:
1. Fetch historical market data from Polymarket/Kalshi
2. Test strategies with realistic fee/slippage modeling
3. Optimize parameters via grid search
4. Compare strategies across identical data
5. Generate reports with equity curves, metrics tables

### Concrete Deliverables
- `src/bt/cli/main.py` - Click CLI entry point
- `src/bt/core/models.py` - Data models (Market, Trade, Position, Signal)
- `src/bt/core/cache.py` - Parquet/SQLite caching layer
- `src/bt/platforms/base.py` - PlatformAdapter ABC
- `src/bt/platforms/polymarket.py` - Polymarket adapter
- `src/bt/platforms/kalshi.py` - Kalshi adapter
- `src/bt/strategies/base.py` - BaseStrategy ABC
- `src/bt/strategies/*.py` - 5 strategy implementations
- `src/bt/engine/backtest.py` - Backtest engine
- `src/bt/engine/metrics.py` - Performance metrics
- `src/bt/engine/analysis.py` - Deep analysis (sweeps, Monte Carlo)
- `tests/` - Unit and integration tests
- `examples/` - Example configs and scripts
- `Dockerfile`, `docker-compose.yml` - Container setup
- `README.md` - Documentation with examples

### Definition of Done
- [ ] `bt fetch --platform poly --market-id <id>` downloads and caches data
- [ ] `bt backtest --strategy weather --config config.yaml` runs single backtest
- [ ] `bt optimize --strategy crossarb --params edge_threshold=0.01-0.1` runs grid search
- [ ] `bt compare --strategies weather,copy,arb` shows comparison table
- [ ] `bt analyze --run-id 123` shows deep analysis
- [ ] All strategies inherit from BaseStrategy
- [ ] All platforms implement PlatformAdapter
- [ ] Fees (2% PM, 1% Kalshi) and slippage modeled
- [ ] Output: stats DF, equity curve PNG, trades CSV/JSON, HTML report

### Must Have
- Type hints throughout
- Error handling with retry logic
- Rate limit handling
- Pagination support for API calls
- Configuration via YAML
- **Universal market support**: Any binary/categorical market from Polymarket/Kalshi
- **Extensible signals**: Strategy receives raw market data, can implement ANY logic
- **Generic backtest engine**: Works with any market that has price history + resolution
- **Orderbook support**: Fetch and replay orderbook data for realistic execution
- **Liquidity matching**: Match order size against available depth, calculate slippage
- **Tiered pricing**: Fill partial orders at progressively worse prices

### Must NOT Have
- Hardcoded API keys (use environment variables)
- Blocking calls in async context
- Global mutable state
- Unbounded memory usage for large datasets

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: NO (fresh project)
- **Automated tests**: YES - Tests after implementation
- **Framework**: pytest + pytest-asyncio
- **Coverage Target**: 80%+

### QA Policy
Every task includes agent-executed QA scenarios:
- **Data fetch**: Verify Parquet files created, schema correct
- **Strategy**: Run backtest on known data, verify trades logged
- **Engine**: Compare output metrics against manual calculation
- **CLI**: Run each command, verify help text and output

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation - 7 tasks):
├── T1: Project scaffolding + pyproject.toml
├── T2: Core data models (Market, Trade, Position, Signal)
├── T3: Cache layer (Parquet + SQLite)
├── T4: PlatformAdapter ABC + type definitions
├── T5: Configuration loading (YAML)
├── T6: Logging + error handling utilities
└── T7: BaseStrategy ABC

Wave 2 (Platforms & Strategies - 8 tasks):
├── T8: Polymarket adapter (py-clob-client)
├── T9: Kalshi adapter (official API)
├── T10: Weather strategy (NOAA/ECMWF vs price)
├── T11: CopyTrade strategy (top wallets consensus)
├── T12: CrossArb strategy (YES/NO pairs)
├── T13: Momentum strategy (volume spikes)
├── T14: MeanReversion strategy (reversion to 50%)
└── T15: Strategy registry + config loading

Wave 3 (Engine & CLI - 7 tasks):
├── T16: Backtest engine (replay, timestamp alignment)
├── T17: Performance metrics (all stats)
├── T18: Equity curve + visualization
├── T19: Trade export (CSV/JSON)
├── T20: Deep analysis (param sweeps, Monte Carlo)
├── T21: HTML report generation
└── T22: CLI commands (fetch, backtest, optimize, compare, analyze)

Wave 4 (Finalization - 4 tasks):
├── T23: Tests (unit + integration)
├── T24: Docker setup
├── T25: README + examples
└── T26: Final verification
```

### Dependency Matrix
- **T1-T7**: — — All (foundation)
- **T8**: T4 — T10-T15 (depends on adapter base)
- **T9**: T4 — T10-T15 (depends on adapter base)
- **T10-T14**: T7, T8, T9 — T15 (strategies need engine + adapters)
- **T15**: T7, T8, T9 — T16-T22
- **T16-T21**: T15 — T22 (engine needs strategies)
- **T22**: T16-T21 — T23
- **T23-T25**: T22 — T26
- **T26**: T23-T25 —

---

## TODOs

### Wave 1: Foundation

- [ ] 1. **Project scaffolding + pyproject.toml**

  **What to do**:
  - Create directory structure: `src/bt/{core,platforms,strategies,engine,cli}`
  - Create `pyproject.toml` with all dependencies
  - Create `__init__.py` files for packages
  - Create `.env.example` for API keys

  **References**:
  - Python packaging best practices: `https://packaging.python.org/en/latest/tutorials/packaging-projects/`

  **Acceptance Criteria**:
  - [ ] `python -m bt --help` works
  - [ ] All dependencies install via `poetry install`

- [ ] 2. **Core data models**

  **What to do**:
  - Define dataclasses: Market, Trade, Position, Signal, BacktestResult
  - Define enums: Platform, Side, OrderType
  - Add validation with Pydantic-style checks

  **References**:
  - Use Python 3.12 dataclasses with field validation

  **Acceptance Criteria**:
  - [ ] All models serialize to/from dict
  - [ ] Type hints complete

- [ ] 3. **Cache layer (Parquet + SQLite)**

  **What to do**:
  - Implement `DataCache` class with Parquet for OHLCV data
  - Implement SQLite for metadata and trade logs
  - Add `get_markets()`, `save_prices()`, `get_trades()` methods
  - Handle schema migrations

  **References**:
  - PyArrow docs for Parquet: `https://arrow.apache.org/docs/python/parquet.html`

  **Acceptance Criteria**:
  - [ ] `cache.save_prices()` creates valid Parquet file
  - [ ] `cache.get_prices()` returns DataFrame with correct columns

- [ ] 4. **PlatformAdapter ABC**

  **What to do**:
  - Define `PlatformAdapter` abstract base class
  - Define abstract methods: `get_markets()`, `get_prices()`, `get_trades()`, `get_positions()`
  - Define `MarketTicker` and `PriceData` types

  **References**:
  - Python ABC documentation

  **Acceptance Criteria**:
  - [ ] PolymarketAdapter and KalshiAdapter inherit correctly

- [ ] 5. **Configuration loading**

  **What to do**:
  - Implement `Config` class to load YAML
  - Support strategy params, platform credentials, backtest settings
  - Add environment variable interpolation

  **References**:
  - PyYAML docs: `https://pyyaml.org/wiki/PyYAMLDocumentation`

  **Acceptance Criteria**:
  - [ ] Load example config without error

- [ ] 6. **Logging + error handling**

  **What to do**:
  - Configure structured logging
  - Implement retry decorator with exponential backoff
  - Add rate limit handler

  **References**:
  - Tenacity library: `https://tenacity.readthedocs.io/`

  **Acceptance Criteria**:
  - [ ] `@retry` decorator works on API calls

- [ ] 7. **BaseStrategy ABC**

  **What to do**:
  - Define `BaseStrategy` abstract class
  - Define `generate_signals()` abstract method
  - Define lifecycle methods: `on_start()`, `on_trade()`, `on_end()`
  - Define risk management methods

  **Acceptance Criteria**:
  - [ ] All strategy implementations inherit correctly

### Wave 2: Platforms & Strategies

- [ ] 8. **Polymarket adapter**

  **What to do**:
  - Implement `PolymarketAdapter` using py-clob-client
  - Implement price history fetching with pagination
  - Implement trade history fetching
  - Map to unified data models
  - Add Goldsky subgraph support for advanced queries

  **References**:
  - py-clob-client: `https://github.com/polymarket/py-clob-client`
  - Goldsky subgraph: `https://docs.goldsky.com/`

  **Acceptance Criteria**:
  - [ ] `adapter.get_markets()` returns list of Market objects

- [ ] 9. **Kalshi adapter**

  **What to do**:
  - Implement `KalshiAdapter` using kalshi-python
  - Implement `/markets`, `/prices_history`, `/trades` endpoints
  - Map to unified data models
  - Handle rate limits

  **References**:
  - Kalshi API docs

  **Acceptance Criteria**:
  - [ ] `adapter.get_markets()` returns list of Market objects

- [ ] 10. **Weather strategy**

  **What to do**:
  - Implement `WeatherStrategy` subclassing BaseStrategy
  - Fetch NOAA/ECMWF forecast data
  - Compare forecast probability vs market price
  - Generate buy signals when forecast > price + edge_threshold

  **Acceptance Criteria**:
  - [ ] Backtest runs on Polymarket weather markets

- [ ] 11. **CopyTrade strategy**

  **What to do**:
  - Implement `CopyTradeStrategy`
  - Track top wallets via Goldsky subgraph
  - Enter positions when 80% consensus among top traders
  - Include position sizing based on conviction

  **Acceptance Criteria**:
  - [ ] Successfully identifies top wallets

- [ ] 12. **CrossArb strategy**

  **What to do**:
  - Implement `CrossArbStrategy`
  - Scan paired events (election markets)
  - Buy YES + NO when sum < 0.98 post-fees
  - Account for Polymarket 2% fee

  **Acceptance Criteria**:
  - [ ] Detects arb opportunities in election markets

- [ ] 13. **Momentum strategy**

  **What to do**:
  - Implement `MomentumStrategy`
  - Detect volume spikes (>3x average)
  - Trail winners with stop-loss
  - Position size via Kelly criterion

  **Acceptance Criteria**:
  - [ ] Trades on volume spike detection

- [ ] 14. **MeanReversion strategy**

  **What to do**:
  - Implement `MeanReversionStrategy`
  - Identify oversold/overbought (z-score > 2)
  - Mean-revert to 50%
  - Include time decay factor

  **Acceptance Criteria**:
  - [ ] Trades against extreme prices

- [ ] 15. **Strategy registry**

  **What to do**:
  - Implement `StrategyRegistry` class
  - Load strategies from config
  - Validate strategy parameters

  **Acceptance Criteria**:
  - [ ] `registry.get("weather")` returns WeatherStrategy class

### Wave 3: Engine & CLI

- [ ] 16. **Backtest engine**

  **What to do**:
  - Implement `BacktestEngine` class
  - Timestamp-aligned replay of price data
  - Handle market resolutions
  - Apply position sizing and Kelly criterion
  - Calculate PnL with fees and slippage
  - **Orderbook-aware execution**: Match orders against depth, calculate realistic fills
  - **Tiered pricing**: Fill partial orders at progressively worse prices
  - **Liquidity tracking**: Model impact on price for large orders

  **Acceptance Criteria**:
  - [ ] `engine.run()` returns BacktestResult

- [ ] 17. **Performance metrics**

  **What to do**:
  - Implement full metrics table:
    - Sharpe ratio, Sortino ratio, Calmar ratio
    - Max drawdown, Win rate, Profit factor
    - Trades per month, Expectancy
  - Calculate drawdown curve

  **Acceptance Criteria**:
  - [ ] All metrics calculated correctly

- [ ] 18. **Equity curve visualization**

  **What to do**:
  - Generate equity curve using Plotly
  - Include benchmark (buy-and-hold)
  - Export as PNG

  **Acceptance Criteria**:
  - [ ] PNG file generated with correct data

- [ ] 19. **Trade export**

  **What to do**:
  - Export trades to CSV with all fields
  - Export to JSON for programmatic use
  - Include execution details

  **Acceptance Criteria**:
  - [ ] CSV/JSON files valid and complete

- [ ] 20. **Deep analysis**

  **What to do**:
  - Implement parameter sweeps (grid search)
  - Implement Monte Carlo simulation (slippage/vol shocks)
  - Implement attribution (signal vs market)
  - Generate heatmaps

  **Acceptance Criteria**:
  - [ ] Sweep completes with optimal params
  - [ ] Monte Carlo shows confidence intervals

- [ ] 21. **HTML report generation**

  **What to do**:
  - Generate self-contained HTML report
  - Include metrics, equity curve, trades table
  - Interactive charts

  **Acceptance Criteria**:
  - [ ] HTML opens in browser with all content

- [ ] 22. **CLI commands**

  **What to do**:
  - Implement `bt fetch` - Download/enrich data
  - Implement `bt backtest` - Run single strategy
  - Implement `bt optimize` - Grid search
  - Implement `bt compare` - Multi-strat comparison
  - Implement `bt analyze` - Deep dive

  **Acceptance Criteria**:
  - [ ] All commands work with `--help`
  - [ ] Output formats correct

### Wave 4: Finalization

- [ ] 23. **Tests**

  **What to do**:
  - Unit tests for models, strategies
  - Integration tests for adapters
  - Mock API responses for reproducibility

  **Acceptance Criteria**:
  - [ ] `pytest` passes with 80%+ coverage

- [ ] 24. **Docker setup**

  **What to do**:
  - Create `Dockerfile` with Python 3.12
  - Create `docker-compose.yml`
  - Include volume mounts for data

  **Acceptance Criteria**:
  - [ ] Container builds and runs

- [ ] 25. **README + examples**

  **What to do**:
  - Write comprehensive README
  - Add example configs in `examples/`
  - Document API usage

  **Acceptance Criteria**:
  - [ ] README explains all features

- [ ] 26. **Final verification**

  **What to do**:
  - Run full backtest on real data
  - Verify output files
  - Test on 50 resolved Polymarket weather markets

  **Acceptance Criteria**:
  - [ ] Sharpe > 1.5 target achievable
  - [ ] All outputs generated correctly

---

## Final Verification Wave

- [ ] F1. **Plan Compliance Audit** — Verify all deliverables present
- [ ] F2. **Code Quality Review** — Type checking, linting
- [ ] F3. **Real Manual QA** — Run actual backtest with real data
- [ ] F4. **Scope Fidelity Check** — Verify no creep

---

## Commit Strategy

- **1**: `feat(core): Add data models and cache layer` (7 files)
- **2**: `feat(platforms): Add Polymarket and Kalshi adapters` (2 files)
- **3**: `feat(strategies): Add 5 trading strategies` (6 files)
- **4**: `feat(engine): Add backtest engine and metrics` (4 files)
- **5**: `feat(cli): Add CLI commands` (1 file)
- **6**: `test: Add unit and integration tests` (N files)
- **7**: `chore: Add Docker and documentation` (4 files)

---

## Success Criteria

### Verification Commands
```bash
poetry install
python -m bt --help
python -m bt fetch --platform poly --market-id 654414
python -m bt backtest --strategy weather --config config.yaml
python -m bt optimize --strategy crossarb --params edge_threshold=0.01-0.1
python -m bt compare --strategies weather,copy,arb --period last_year
python -m bt analyze --run-id 123
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] Fees (2% PM, 1% Kalshi) modeled
- [ ] Slippage model included
- [ ] Position limits enforced
- [ ] Output: stats DF, equity curve PNG, trades CSV/JSON, HTML report
