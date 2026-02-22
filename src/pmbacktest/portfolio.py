"""Portfolio manager for tracking positions and P&L."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pmbacktest.types import (
    Fill,
    Outcome,
    OrderSide,
    Position,
    Trade,
)


@dataclass
class PortfolioState:
    """Current state of the portfolio."""

    cash: float
    positions: dict[str, Position]
    equity: float
    unrealized_pnl: float
    realized_pnl: float


class PortfolioManager:
    """Manages positions, cash, and P&L tracking.

    Attributes:
        initial_cash: Starting capital
        cash: Current available cash
        positions: Dict of position_key -> Position
    """

    def __init__(self, initial_cash: float = 10000.0):
        """Initialize portfolio with starting capital.

        Args:
            initial_cash: Starting cash amount
        """
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: dict[str, Position] = {}
        self._trades: list[Trade] = []
        self._equity_history: list[tuple[int, float]] = []

    def _make_key(self, market_id: str, outcome: Outcome) -> str:
        """Create position key from market and outcome."""
        return f"{market_id}:{outcome.value}"

    @property
    def trades(self) -> list[Trade]:
        """Get all completed trades."""
        return self._trades

    @property
    def equity_history(self) -> list[tuple[int, float]]:
        """Get equity curve as (timestamp, equity) pairs."""
        return self._equity_history

    @property
    def total_unrealized_pnl(self) -> float:
        """Sum of all unrealized P&L."""
        return sum(p.unrealized_pnl for p in self.positions.values())

    @property
    def total_realized_pnl(self) -> float:
        """Sum of all realized P&L."""
        return sum(p.realized_pnl for p in self.positions.values())

    @property
    def total_equity(self) -> float:
        """Total portfolio value including cash and positions."""
        return self.cash + sum(
            p.quantity * p.entry_price  # Use cost basis for unrealized
            for p in self.positions.values()
        ) + self.total_unrealized_pnl

    def get_position(self, market_id: str, outcome: Outcome) -> Position | None:
        """Get position for a market outcome."""
        key = self._make_key(market_id, outcome)
        return self.positions.get(key)

    def has_position(self, market_id: str, outcome: Outcome) -> bool:
        """Check if position exists."""
        key = self._make_key(market_id, outcome)
        return key in self.positions and self.positions[key].quantity > 0

    def execute_buy(
        self,
        market_id: str,
        outcome: Outcome,
        dollar_amount: float,
        fill_price: float,
        timestamp: int | None = None,
    ) -> Fill | None:
        """Execute a buy order.

        Args:
            market_id: Market identifier
            outcome: Which outcome to buy
            dollar_amount: Dollar amount to spend
            fill_price: Price at which order filled
            timestamp: Order timestamp

        Returns:
            Fill object if successful, None if insufficient funds
        """
        if dollar_amount <= 0:
            return None

        token_amount = dollar_amount / fill_price
        cost = token_amount * fill_price

        if cost > self.cash:
            # Scale down to available cash
            dollar_amount = self.cash
            token_amount = dollar_amount / fill_price
            cost = dollar_amount

        if token_amount <= 0:
            return None

        self.cash -= cost

        key = self._make_key(market_id, outcome)
        if key in self.positions:
            pos = self.positions[key]
            # Average down/up
            total_qty = pos.quantity + token_amount
            new_entry_price = (
                (pos.quantity * pos.entry_price + token_amount * fill_price)
                / total_qty
            )
            pos.quantity = total_qty
            pos.entry_price = new_entry_price
        else:
            self.positions[key] = Position(
                market_id=market_id,
                outcome=outcome,
                quantity=token_amount,
                entry_price=fill_price,
                entry_time=datetime.fromtimestamp(timestamp) if timestamp else datetime.now(),
            )

        from pmbacktest.types import Order, OrderType

        order = Order(
            signal=None,  # Will be set by caller
            status="filled",
        )
        fill = Fill(
            order=order,
            market_id=market_id,
            outcome=outcome,
            side=OrderSide.BUY,
            quantity=token_amount,
            price=fill_price,
            timestamp=datetime.fromtimestamp(timestamp) if timestamp else datetime.now(),
        )

        return fill

    def execute_sell(
        self,
        market_id: str,
        outcome: Outcome,
        dollar_amount: float,
        fill_price: float,
        timestamp: int | None = None,
    ) -> Fill | None:
        """Execute a sell order (close or reduce position).

        Args:
            market_id: Market identifier
            outcome: Which outcome to sell
            dollar_amount: Dollar amount to sell (or 'all' for full position)
            fill_price: Price at which order filled
            timestamp: Order timestamp

        Returns:
            Fill object if successful, None if no position
        """
        key = self._make_key(market_id, outcome)
        if key not in self.positions:
            return None

        pos = self.positions[key]
        if pos.quantity <= 0:
            return None

        # Calculate how many tokens to sell
        if dollar_amount == -1:  # Sell all
            token_amount = pos.quantity
        else:
            token_amount = min(dollar_amount / fill_price, pos.quantity)

        proceeds = token_amount * fill_price

        # Calculate P&L for this trade
        cost_basis = token_amount * pos.entry_price
        trade_pnl = proceeds - cost_basis
        pos.realized_pnl += trade_pnl

        # Update or remove position
        pos.quantity -= token_amount
        self.cash += proceeds

        # Record trade
        trade = Trade(
            market_id=market_id,
            outcome=outcome,
            side=OrderSide.SELL,
            quantity=token_amount,
            price=fill_price,
            pnl=trade_pnl,
            entry_time=pos.entry_time,
            exit_time=datetime.fromtimestamp(timestamp) if timestamp else datetime.now(),
        )
        self._trades.append(trade)

        # Remove position if fully closed
        if pos.quantity <= 0:
            del self.positions[key]

        from pmbacktest.types import Order

        order = Order(
            signal=None,
            status="filled",
        )
        fill = Fill(
            order=order,
            market_id=market_id,
            outcome=outcome,
            side=OrderSide.SELL,
            quantity=token_amount,
            price=fill_price,
            timestamp=datetime.fromtimestamp(timestamp) if timestamp else datetime.now(),
        )

        return fill

    def mark_to_market(self, prices: dict[str, dict[Outcome, float]]) -> None:
        """Update unrealized P&L based on current prices.

        Args:
            prices: Dict of market_id -> {outcome: price}
        """
        for key, pos in list(self.positions.items()):
            market_prices = prices.get(pos.market_id, {})
            current_price = market_prices.get(pos.outcome)
            if current_price is not None:
                pos.update_unrealized_pnl(current_price)

    def record_equity(self, timestamp: int) -> None:
        """Record equity for equity curve.

        Args:
            timestamp: Current timestamp
        """
        self._equity_history.append((timestamp, self.total_equity))

    def close_position(
        self,
        market_id: str,
        outcome: Outcome,
        close_price: float,
        timestamp: int | None = None,
    ) -> Fill | None:
        """Close a position at specified price.

        Args:
            market_id: Market identifier
            outcome: Which outcome
            close_price: Price to close at
            timestamp: Close timestamp

        Returns:
            Fill object if position was closed, None if no position
        """
        return self.execute_sell(market_id, outcome, -1, close_price, timestamp)

    def get_state(self) -> PortfolioState:
        """Get current portfolio state."""
        return PortfolioState(
            cash=self.cash,
            positions=self.positions.copy(),
            equity=self.total_equity,
            unrealized_pnl=self.total_unrealized_pnl,
            realized_pnl=self.total_realized_pnl,
        )
