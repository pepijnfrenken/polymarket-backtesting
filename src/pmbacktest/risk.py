"""Risk management for position sizing and limits."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pmbacktest.types import Signal


class PositionSizingMethod(StrEnum):
    """Position sizing strategies."""

    FIXED_AMOUNT = "fixed_amount"
    FIXED_PERCENT = "fixed_percent"
    KELLY = "kelly"
    FRACTIONAL_KELLY = "fractional_kelly"


@dataclass
class RiskConfig:
    """Configuration for risk management."""

    position_sizing: PositionSizingMethod = PositionSizingMethod.FIXED_PERCENT
    fixed_amount: float = 100.0  # Dollar amount per trade
    fixed_percent: float = 0.1  # 10% of portfolio per trade
    max_position_pct: float = 0.25  # Max 25% in single position
    max_daily_loss_pct: float = 0.1  # Max 10% daily loss before kill switch
    stop_loss_pct: float = 0.05  # 5% stop loss
    enable_stop_loss: bool = True
    max_kelly: float = 0.25  # Max Kelly fraction (for safety)


class RiskManager:
    """Manages risk including position sizing and limits.

    Attributes:
        config: Risk configuration
    """

    def __init__(self, config: RiskConfig | None = None):
        """Initialize risk manager.

        Args:
            config: Risk configuration
        """
        self.config = config or RiskConfig()
        self._daily_pnl = 0.0
        self._day_start_equity = 0.0

    def calculate_position_size(
        self,
        signal: Signal,
        portfolio_value: float,
        win_rate: float = 0.5,
        avg_win: float = 1.0,
        avg_loss: float = 1.0,
    ) -> float:
        """Calculate position size based on method.

        Args:
            signal: Trading signal
            portfolio_value: Current portfolio value
            win_rate: Historical win rate (for Kelly)
            avg_win: Average win amount (for Kelly)
            avg_loss: Average loss amount (for Kelly)

        Returns:
            Adjusted dollar amount to trade
        """
        method = self.config.position_sizing

        if method == PositionSizingMethod.FIXED_AMOUNT:
            return self.config.fixed_amount

        elif method == PositionSizingMethod.FIXED_PERCENT:
            return portfolio_value * self.config.fixed_percent

        elif method == PositionSizingMethod.KELLY:
            kelly = self._calculate_kelly(win_rate, avg_win, avg_loss)
            return portfolio_value * kelly

        elif method == PositionSizingMethod.FRACTIONAL_KELLY:
            kelly = self._calculate_kelly(win_rate, avg_win, avg_loss)
            fractional = kelly * self.config.max_kelly
            return portfolio_value * fractional

        return self.config.fixed_amount  # Default

    def _calculate_kelly(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
    ) -> float:
        """Calculate Kelly Criterion fraction.

        Formula: f* = (bp - q) / b
        where:
            b = odds received (avg_win / avg_loss)
            p = probability of win (win_rate)
            q = probability of loss (1 - p)

        Args:
            win_rate: Probability of winning
            avg_win: Average win amount
            avg_loss: Average loss amount

        Returns:
            Kelly fraction (0-1)
        """
        if avg_loss == 0:
            return 0.0

        b = avg_win / avg_loss  # Odds
        p = win_rate
        q = 1 - p

        kelly = (b * p - q) / b

        # Kelly can be negative (no edge) or > 1 (infinite edge)
        # Clamp to valid range
        return max(0.0, min(1.0, kelly))

    def check_signal(
        self,
        signal: Signal,
        portfolio_value: float,
    ) -> bool:
        """Check if signal passes risk checks.

        Args:
            signal: Signal to check
            portfolio_value: Current portfolio value

        Returns:
            True if signal is allowed
        """
        # Check max position size
        max_position = portfolio_value * self.config.max_position_pct
        if signal.size > max_position:
            signal.size = max_position

        # Check minimum viable size
        if signal.size < 1.0:  # Less than $1
            return False

        # Check daily loss kill switch
        if portfolio_value > 0:
            daily_loss = (self._day_start_equity - portfolio_value) / self._day_start_equity
            if daily_loss > self.config.max_daily_loss_pct:
                return False  # Kill switch triggered

        return True

    def apply_stop_loss(
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
            True if should exit position
        """
        if not self.config.enable_stop_loss:
            return False

        if signal.action.value == "buy":
            # For long positions, stop loss is below entry
            loss_pct = (entry_price - current_price) / entry_price
            return loss_pct >= self.config.stop_loss_pct
        else:
            # For short positions, stop loss is above entry
            loss_pct = (current_price - entry_price) / entry_price
            return loss_pct >= self.config.stop_loss_pct

    def start_new_day(self, equity: float) -> None:
        """Reset daily tracking for new day.

        Args:
            equity: Current equity at start of day
        """
        self._day_start_equity = equity
        self._daily_pnl = 0.0

    def record_trade(self, pnl: float) -> None:
        """Record trade P&L for daily tracking.

        Args:
            pnl: Trade profit/loss
        """
        self._daily_pnl += pnl
