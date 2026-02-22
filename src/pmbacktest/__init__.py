"""Polymarket Backtesting Library

A comprehensive Python library for backtesting trading strategies on Polymarket
prediction markets. Supports both signal-based and event-driven strategy interfaces.
"""

from pmbacktest.types import (
    OrderSide,
    OrderType,
    Outcome,
    Signal,
    Order,
    Position,
    Fill,
    Trade,
)

from pmbacktest.strategies import (
    Strategy,
    SignalStrategy,
    EventStrategy,
    Bar,
    MarketState,
)

from pmbacktest.portfolio import PortfolioManager, PortfolioState
from pmbacktest.execution import ExecutionHandler, ExecutionConfig
from pmbacktest.data import MarketDataFeed, MarketDataPoint, MockDataFeed
from pmbacktest.risk import RiskManager, RiskConfig, PositionSizingMethod
from pmbacktest.config import Config, BacktestConfig, EngineConfig, DEFAULT_CONFIG
from pmbacktest.engine import BacktestEngine, BacktestResult

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # Core types
    "Signal",
    "Order",
    "Position",
    "Fill",
    "Trade",
    "OrderType",
    "OrderSide",
    "Outcome",
    # Strategies
    "Strategy",
    "SignalStrategy",
    "EventStrategy",
    "Bar",
    "MarketState",
    # Portfolio
    "PortfolioManager",
    "PortfolioState",
    # Execution
    "ExecutionHandler",
    "ExecutionConfig",
    # Data
    "MarketDataFeed",
    "MarketDataPoint",
    "MockDataFeed",
    # Risk
    "RiskManager",
    "RiskConfig",
    "PositionSizingMethod",
    # Config
    "Config",
    "BacktestConfig",
    "EngineConfig",
    "DEFAULT_CONFIG",
    # Engine
    "BacktestEngine",
    "BacktestResult",
]
