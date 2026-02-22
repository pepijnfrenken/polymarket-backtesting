"""Backtest engine for running strategies against historical data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pmbacktest.config import Config
from pmbacktest.data import MarketDataFeed, MarketDataPoint
from pmbacktest.execution import ExecutionHandler
from pmbacktest.portfolio import PortfolioManager
from pmbacktest.risk import RiskManager
from pmbacktest.strategies import MarketState, Strategy
from pmbacktest.types import OrderSide, Outcome, Signal


@dataclass
class BacktestResult:
    """Results from a backtest run."""

    initial_capital: float
    final_capital: float
    total_return: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    equity_history: list[tuple[int, float]]
    trades: list[Any]  # Trade records
    config: Config

    @property
    def win_rate(self) -> float:
        """Win rate as percentage."""
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades


class BacktestEngine:
    """Event-driven backtest engine.

    The engine iterates through historical data, updates market state,
    generates signals from strategies, executes orders, and tracks portfolio.

    Attributes:
        config: Backtest configuration
        portfolio: Portfolio manager
        execution: Execution handler
        risk: Risk manager
    """

    def __init__(self, config: Config | None = None):
        """Initialize backtest engine.

        Args:
            config: Backtest configuration
        """
        self.config = config or Config()
        self.portfolio = PortfolioManager(
            initial_cash=self.config.backtest.initial_capital
        )
        self.execution = ExecutionHandler(
            config=self.config.backtest.to_execution_config()
        )
        self.risk = RiskManager(config=self.config.risk)
        self.strategies: list[Strategy] = []
        self._data: MarketDataFeed | None = None
        self._result: BacktestResult | None = None

    def add_strategy(self, strategy: Strategy) -> None:
        """Add a strategy to the engine.

        Args:
            strategy: Strategy to add
        """
        self.strategies.append(strategy)

    def run(self, data: MarketDataFeed) -> BacktestResult:
        """Run backtest on historical data.

        Args:
            data: Market data feed

        Returns:
            BacktestResult with performance metrics
        """
        self._data = data
        self._result = None

        # Initialize strategies
        for strategy in self.strategies:
            strategy.on_init()

        # Initialize daily tracking
        current_day = None
        self.risk.start_new_day(self.portfolio.total_equity)

        # Main event loop
        for data_point in data:
            timestamp = data_point.timestamp
            prices = data_point.prices
            bars = data_point.bars

            # Track day changes
            day = timestamp // 86400
            if current_day is not None and day != current_day:
                self.risk.start_new_day(self.portfolio.total_equity)
            current_day = day

            # Mark to market
            self.portfolio.mark_to_market(prices)

            # Build market state
            state = MarketState(
                timestamp=timestamp,
                prices=prices,
                bars=bars,
                positions=self.portfolio.positions,
                cash=self.portfolio.cash,
                portfolio_value=self.portfolio.total_equity,
            )

            # Generate signals from strategies
            for strategy in self.strategies:
                signals = strategy.on_bar(state)
                if signals:
                    for signal in signals:
                        self._execute_signal(signal, prices, timestamp, strategy)

            # Record equity
            self.portfolio.record_equity(timestamp)

        # Finalize
        for strategy in self.strategies:
            strategy.on_end()

        # Mark to market at final prices
        if data._data:
            final_prices = data._data[-1].prices
            self.portfolio.mark_to_market(final_prices)

        return self._build_result()

    def _execute_signal(
        self,
        signal: Signal,
        prices: dict[str, dict[Outcome, float]],
        timestamp: int,
        strategy: Strategy,
    ) -> None:
        """Execute a trading signal.

        Args:
            signal: Signal to execute
            prices: Current prices
            timestamp: Current timestamp
            strategy: Strategy that generated signal
        """
        # Get current price
        market_prices = prices.get(signal.market_id, {})
        current_price = market_prices.get(signal.outcome)

        if current_price is None:
            return

        # Get position for stop loss
        position = self.portfolio.get_position(signal.market_id, signal.outcome)
        entry_price = position.entry_price if position else None

        # Execute with stop loss check
        if entry_price and self.risk.apply_stop_loss(
            signal, entry_price, current_price
        ):
            # Stop loss triggered - close position
            fill = self.portfolio.execute_sell(
                signal.market_id,
                signal.outcome,
                -1,  # Sell all
                current_price,
                timestamp,
            )
            if fill:
                strategy.on_fill(fill)
            return

        # Apply risk management
        if not self.risk.check_signal(signal, self.portfolio.total_equity):
            return

        # Execute order
        if signal.action == OrderSide.BUY:
            fill = self.execution.execute(signal, current_price, timestamp)
            if fill:
                # Apply commission to cash
                self.portfolio.cash -= fill.commission
                # Execute buy in portfolio
                buy_fill = self.portfolio.execute_buy(
                    signal.market_id,
                    signal.outcome,
                    signal.size,
                    fill.price,
                    timestamp,
                )
                if buy_fill:
                    strategy.on_fill(buy_fill)
        else:
            fill = self.execution.execute(signal, current_price, timestamp)
            if fill:
                sell_fill = self.portfolio.execute_sell(
                    signal.market_id,
                    signal.outcome,
                    signal.size,
                    fill.price,
                    timestamp,
                )
                if sell_fill:
                    strategy.on_fill(sell_fill)

    def _build_result(self) -> BacktestResult:
        """Build final result from backtest."""
        trades = self.portfolio.trades
        winning = sum(1 for t in trades if t.pnl > 0)
        losing = sum(1 for t in trades if t.pnl < 0)

        initial = self.config.backtest.initial_capital
        final = self.portfolio.total_equity

        return BacktestResult(
            initial_capital=initial,
            final_capital=final,
            total_return=(final - initial) / initial if initial > 0 else 0,
            total_trades=len(trades),
            winning_trades=winning,
            losing_trades=losing,
            equity_history=self.portfolio.equity_history,
            trades=trades,
            config=self.config,
        )

    @property
    def result(self) -> BacktestResult | None:
        """Get backtest result."""
        return self._result
