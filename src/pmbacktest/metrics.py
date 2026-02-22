"""Performance metrics calculation for backtest results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics."""

    total_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    calmar_ratio: float
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_trade_pnl: float
    avg_winning_trade: float
    avg_losing_trade: float
    largest_winner: float
    largest_loser: float


def calculate_metrics(
    equity_history: list[tuple[int, float]],
    trades: list[Any],
    risk_free_rate: float = 0.0,
) -> PerformanceMetrics:
    """Calculate comprehensive performance metrics.

    Args:
        equity_history: List of (timestamp, equity) tuples
        trades: List of trade records
        risk_free_rate: Annual risk-free rate (default 0)

    Returns:
        PerformanceMetrics with all calculated values
    """
    import numpy as np

    # Extract returns from equity
    if len(equity_history) < 2:
        return _empty_metrics()

    equity_values = [e[1] for e in equity_history]
    returns = np.diff(equity_values) / equity_values[:-1]
    returns = returns[~np.isnan(returns)]  # Remove NaN

    if len(returns) == 0:
        return _empty_metrics()

    # Total return
    total_return = (equity_values[-1] - equity_values[0]) / equity_values[0] if equity_values[0] > 0 else 0

    # Sharpe ratio (annualized)
    if len(returns) > 1 and np.std(returns) > 0:
        sharpe = (np.mean(returns) - risk_free_rate / 252) / np.std(returns) * np.sqrt(252)
    else:
        sharpe = 0.0

    # Sortino ratio
    downside_returns = returns[returns < 0]
    if len(downside_returns) > 1 and np.std(downside_returns) > 0:
        sortino = (np.mean(returns) - risk_free_rate / 252) / np.std(downside_returns) * np.sqrt(252)
    else:
        sortino = 0.0

    # Max drawdown
    running_max = np.maximum.accumulate(equity_values)
    drawdowns = (equity_values - running_max) / running_max
    max_dd = abs(np.min(drawdowns)) if len(drawdowns) > 0 else 0

    # Calmar ratio (annual return / max drawdown)
    if max_dd > 0:
        calmar = total_return / max_dd
    else:
        calmar = 0.0

    # Trade statistics
    if trades:
        pnls = [t.pnl for t in trades if hasattr(t, 'pnl')]
        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p < 0]

        total_trades = len(pnls)
        win_rate = len(winners) / total_trades if total_trades > 0 else 0
        avg_trade = np.mean(pnls) if pnls else 0
        avg_win = np.mean(winners) if winners else 0
        avg_loss = np.mean(losers) if losers else 0
        largest_winner = max(winners) if winners else 0
        largest_loser = min(losers) if losers else 0

        gross_profit = sum(winners) if winners else 0
        gross_loss = abs(sum(losers)) if losers else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
    else:
        win_rate = 0
        avg_trade = 0
        avg_win = 0
        avg_loss = 0
        largest_winner = 0
        largest_loser = 0
        profit_factor = 0
        total_trades = 0

    return PerformanceMetrics(
        total_return=total_return,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        max_drawdown=max_dd,
        calmar_ratio=calmar,
        win_rate=win_rate,
        profit_factor=profit_factor,
        total_trades=total_trades,
        avg_trade_pnl=avg_trade,
        avg_winning_trade=avg_win,
        avg_losing_trade=avg_loss,
        largest_winner=largest_winner,
        largest_loser=largest_loser,
    )


def _empty_metrics() -> PerformanceMetrics:
    """Return empty metrics."""
    return PerformanceMetrics(
        total_return=0.0,
        sharpe_ratio=0.0,
        sortino_ratio=0.0,
        max_drawdown=0.0,
        calmar_ratio=0.0,
        win_rate=0.0,
        profit_factor=0.0,
        total_trades=0,
        avg_trade_pnl=0.0,
        avg_winning_trade=0.0,
        avg_losing_trade=0.0,
        largest_winner=0.0,
        largest_loser=0.0,
    )
