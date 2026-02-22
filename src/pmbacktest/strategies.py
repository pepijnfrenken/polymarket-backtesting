"""Strategy base classes for the Polymarket backtesting library.

This module provides the base classes for implementing trading strategies:
- Strategy: Abstract base class with lifecycle methods
- SignalStrategy: Simple signal-based strategy interface
- EventStrategy: Full event-driven strategy interface with orderbook/trade data
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pmbacktest.types import (
    Fill,
    Outcome,
    Signal,
    Trade,
)

# Orderbook is imported from polymarket-data when needed
Orderbook = None


@dataclass
class Bar:
    """A single bar of price data.

    Attributes:
        timestamp: When the bar represents
        open: Opening price
        high: High price
        low: Low price
        close: Closing price
        volume: Trading volume
    """

    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class MarketState:
    """Current state of markets for strategy decision-making.

    Attributes:
        timestamp: Current timestamp
        prices: Dict of market_id -> {outcome: price}
        bars: Dict of market_id -> Bar for current period
        positions: Dict of market_id -> Position
        cash: Available cash
        portfolio_value: Total portfolio value
    """

    timestamp: int
    prices: dict[str, dict[Outcome, float]] = field(default_factory=dict)
    bars: dict[str, Bar] = field(default_factory=dict)
    positions: dict[str, Any] = field(default_factory=dict)
    cash: float = 0.0
    portfolio_value: float = 0.0

    def get_price(self, market_id: str, outcome: Outcome) -> float | None:
        """Get price for a market outcome."""
        return self.prices.get(market_id, {}).get(outcome)

    def get_bar(self, market_id: str) -> Bar | None:
        """Get current bar for a market."""
        return self.bars.get(market_id)


class Strategy(ABC):
    """Abstract base class for all trading strategies.

    Attributes:
        name: Strategy identifier
        params: Strategy parameters dictionary
        state: Mutable state dictionary for strategy data
    """

    def __init__(self, name: str | None = None, params: dict | None = None):
        """Initialize the strategy.

        Args:
            name: Strategy name (defaults to class name)
            params: Strategy parameters
        """
        self.name = name or self.__class__.__name__
        self.params = params or {}
        self.state: dict = {}
        self._initialized = False

    def on_init(self) -> None:
        """Called once at the beginning of the backtest.

        Use this to initialize indicators, load historical data, etc.
        """
        pass

    @abstractmethod
    def on_bar(self, state: MarketState) -> list[Signal] | None:
        """Called on each bar of data.

        Args:
            state: Current market state

        Returns:
            List of signals to execute, or None for no action
        """
        pass

    def on_fill(self, fill: Fill) -> None:
        """Called when an order is filled.

        Args:
            fill: Fill event details
        """
        pass

    def on_end(self) -> None:
        """Called at the end of the backtest.

        Use this for final calculations, cleanup, etc.
        """
        pass

    def get_param(self, key: str, default: Any = None) -> Any:
        """Get a strategy parameter.

        Args:
            key: Parameter name
            default: Default value if not found

        Returns:
            Parameter value
        """
        return self.params.get(key, default)


class SignalStrategy(Strategy):
    """Signal-based strategy interface.

    This is a simpler interface where strategies generate signals
    based on bar data. Ideal for indicator-based strategies.

    Example:
        class MyStrategy(SignalStrategy):
            def generate_signals(self, state: MarketState) -> list[Signal]:
                # Your signal logic here
                return signals
    """

    def on_bar(self, state: MarketState) -> list[Signal] | None:
        """Generate signals based on current bar data.

        This method calls generate_signals() which should be overridden
        by subclasses.
        """
        return self.generate_signals(state)

    @abstractmethod
    def generate_signals(self, state: MarketState) -> list[Signal] | None:
        """Generate trading signals based on market state.

        Args:
            state: Current market state

        Returns:
            List of signals to execute, or None for no action
        """
        pass


class EventStrategy(Strategy):
    """Event-driven strategy interface.

    This is a more advanced interface with access to orderbook
    and trade data. Ideal for market-making, arbitrage, or
    strategies that need granular market data.

    Attributes:
        pending_orders: List of pending limit orders
    """

    def __init__(self, name: str | None = None, params: dict | None = None):
        """Initialize the event strategy."""
        super().__init__(name, params)
        self.pending_orders: list = []

    def on_bar(self, state: MarketState) -> list[Signal] | None:
        """Default bar handler for event strategies.

        Event strategies typically don't use on_bar directly.
        Override on_price_update, on_orderbook, or on_trade instead.
        """
        return None

    def on_price_update(
        self,
        market_id: str,
        outcome: Outcome,
        price: float,
        timestamp: int,
    ) -> None:
        """Called when price updates.

        Args:
            market_id: Market identifier
            outcome: Which outcome
            price: New price
            timestamp: Update timestamp
        """
        pass

    def on_orderbook(
        self,
        market_id: str,
        orderbook: Orderbook,
        timestamp: int,
    ) -> None:
        """Called when orderbook updates.

        Args:
            market_id: Market identifier
            orderbook: Current orderbook state
            timestamp: Update timestamp
        """
        pass

    def on_trade(
        self,
        market_id: str,
        trade: Trade,
        timestamp: int,
    ) -> None:
        """Called when trades occur.

        Args:
            market_id: Market identifier
            trade: Trade details
            timestamp: Trade timestamp
        """
        pass

    def place_limit_order(
        self,
        market_id: str,
        outcome: Outcome,
        side: str,
        size: float,
        limit_price: float,
    ) -> Signal:
        """Place a limit order.

        Args:
            market_id: Market identifier
            outcome: Which outcome
            side: "buy" or "sell"
            size: Dollar amount
            limit_price: Limit price

        Returns:
            Signal for the limit order
        """
        from pmbacktest.types import OrderSide, OrderType

        return Signal(
            market_id=market_id,
            outcome=outcome,
            action=OrderSide(side),
            size=size,
            order_type=OrderType.LIMIT,
            limit_price=limit_price,
        )
