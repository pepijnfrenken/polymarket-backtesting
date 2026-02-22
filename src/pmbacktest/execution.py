"""Execution handler for order simulation with slippage and fees."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pmbacktest.types import (
    FeeCalculator,
    Fill,
    Order,
    OrderSide,
    OrderType,
    Outcome,
    Signal,
)


# Default Polymarket-style fee: 0% commission but P*(1-P) taker fee structure
def default_fee_calculator(price: float, quantity: float, is_maker: bool) -> float:
    """Default fee calculator - Polymarket's P*(1-P) taker fee structure.

    This approximates Polymarket's fee model where fees are highest
    at 50% probability and lowest at the extremes.

    Args:
        price: Fill price
        quantity: Token quantity
        is_maker: Whether this is a maker order

    Returns:
        Fee amount in dollars
    """
    if is_maker:
        return 0.0  # Maker fees are 0
    # Taker fee: approximately 0.02 * price * (1 - price) * value
    # This gives ~0.5% at 50%, near 0% at extremes
    fee_rate = 0.02 * price * (1 - price)
    return fee_rate * price * quantity


def flat_fee_calculator(price: float, quantity: float, is_maker: bool) -> float:
    """Simple flat percentage fee.

    Args:
        price: Fill price
        quantity: Token quantity
        is_maker: Whether this is a maker order

    Returns:
        Fee amount (0.1% of value)
    """
    return 0.001 * price * quantity


def no_fee_calculator(price: float, quantity: float, is_maker: bool) -> float:
    """No fees."""
    return 0.0


@dataclass
class ExecutionConfig:
    """Configuration for execution simulation."""

    slippage_pct: float = 0.0  # Percentage slippage (0.001 = 0.1%)
    fee_calculator: Callable[[float, float, bool], float] = default_fee_calculator
    default_slippage: float = 0.0


class ExecutionHandler:
    """Handles order execution with slippage and fee modeling.

    Attributes:
        config: Execution configuration
    """

    def __init__(self, config: ExecutionConfig | None = None):
        """Initialize execution handler.

        Args:
            config: Execution configuration
        """
        self.config = config or ExecutionConfig()

    def execute(
        self,
        signal: Signal,
        current_price: float,
        timestamp: int | None = None,
    ) -> Fill | None:
        """Execute a trading signal.

        Args:
            signal: Signal to execute
            current_price: Current market price
            timestamp: Execution timestamp

        Returns:
            Fill object if executed, None if order not filled (limit order)
        """
        # Apply slippage to determine fill price
        fill_price = self._apply_slippage(
            current_price,
            signal.action,
        )

        # Check if limit order condition is met
        if signal.order_type == OrderType.LIMIT:
            if signal.limit_price is not None:
                if signal.action == OrderSide.BUY and fill_price > signal.limit_price:
                    return None  # Price too high
                if signal.action == OrderSide.SELL and fill_price < signal.limit_price:
                    return None  # Price too low

        # Check stop order
        if signal.order_type == OrderType.STOP:
            if signal.stop_price is not None:
                if signal.action == OrderSide.BUY and current_price < signal.stop_price:
                    return None  # Stop not triggered
                if signal.action == OrderSide.SELL and current_price > signal.stop_price:
                    return None  # Stop not triggered

        # Calculate token amount
        dollar_amount = signal.size
        token_amount = dollar_amount / fill_price if fill_price > 0 else 0

        if token_amount <= 0:
            return None

        # Calculate fee
        fee = self.config.fee_calculator(fill_price, token_amount, is_maker=False)

        # Create order and fill
        order = Order(
            signal=signal,
            status="filled",
        )

        from datetime import datetime

        fill = Fill(
            order=order,
            market_id=signal.market_id,
            outcome=signal.outcome,
            side=signal.action,
            quantity=token_amount,
            price=fill_price,
            commission=fee,
            timestamp=datetime.fromtimestamp(timestamp) if timestamp else datetime.now(),
        )

        return fill

    def _apply_slippage(
        self,
        price: float,
        side: OrderSide,
    ) -> float:
        """Apply slippage to price based on order side.

        Args:
            price: Base price
            side: Order side (buy or sell)

        Returns:
            Price after slippage
        """
        slippage = self.config.slippage_pct

        if side == OrderSide.BUY:
            # Buy orders execute at higher price
            return price * (1 + slippage)
        else:
            # Sell orders execute at lower price
            return price * (1 - slippage)

    def check_stop_loss(
        self,
        signal: Signal,
        entry_price: float,
        current_price: float,
    ) -> bool:
        """Check if stop loss is triggered.

        Args:
            signal: Signal with stop price
            entry_price: Position entry price
            current_price: Current market price

        Returns:
            True if stop loss is triggered
        """
        if signal.stop_price is None:
            return False

        if signal.action == OrderSide.BUY:
            # Stop loss on sell means price fell below stop
            return current_price <= signal.stop_price
        else:
            # Stop loss on buy means price rose above stop
            return current_price >= signal.stop_price

    def execute_with_stop(
        self,
        signal: Signal,
        current_price: float,
        entry_price: float,
        timestamp: int | None = None,
    ) -> Fill | None:
        """Execute signal with stop loss check.

        Args:
            signal: Signal to execute
            current_price: Current market price
            entry_price: Position entry price
            timestamp: Execution timestamp

        Returns:
            Fill object if executed, None if stopped out or not filled
        """
        # Check stop loss first
        if self.check_stop_loss(signal, entry_price, current_price):
            # Trigger stop - execute at current price
            return self.execute(signal, current_price, timestamp)

        # Normal execution
        return self.execute(signal, current_price, timestamp)
