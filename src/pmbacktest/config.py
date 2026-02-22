"""Configuration dataclasses for backtest engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from pmbacktest.execution import ExecutionConfig
from pmbacktest.risk import RiskConfig
from pmbacktest.types import FeeCalculator


@dataclass
class BacktestConfig:
    """Main configuration for backtest.

    Attributes:
        initial_capital: Starting capital
        commission: Commission rate (deprecated, use fee_calculator)
        slippage_pct: Slippage percentage
        fee_calculator: Custom fee calculator function
    """

    initial_capital: float = 10000.0
    commission: float = 0.0  # Deprecated, use fee_calculator
    slippage_pct: float = 0.0
    fee_calculator: Callable[[float, float, bool], float] = field(default=None)

    def __post_init__(self) -> None:
        """Set up defaults after initialization."""
        if self.fee_calculator is None:
            # Use no fee by default
            from pmbacktest.execution import no_fee_calculator
            self.fee_calculator = no_fee_calculator

    def to_execution_config(self) -> ExecutionConfig:
        """Convert to execution config."""
        return ExecutionConfig(
            slippage_pct=self.slippage_pct,
            fee_calculator=self.fee_calculator,
        )


@dataclass
class EngineConfig:
    """Configuration for backtest engine.

    Attributes:
        data_interval: Time interval for data ("1m", "5m", "15m", "1h", "6h", "1d")
        warmup_bars: Number of bars to warm up indicators
        start_date: Start date for backtest
        end_date: End date for backtest
        verbose: Print progress
    """

    data_interval: str = "1h"
    warmup_bars: int = 0
    start_date: int | None = None
    end_date: int | None = None
    verbose: bool = True


@dataclass
class Config:
    """Combined configuration for backtest.

    This is the main configuration class that combines all
    configuration options into a single object.

    Attributes:
        backtest: Backtest configuration
        engine: Engine configuration
        risk: Risk configuration
    """

    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    engine: EngineConfig = field(default_factory=EngineConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)

    @classmethod
    def from_dict(cls, data: dict) -> Config:
        """Create config from dictionary.

        Args:
            data: Configuration dictionary

        Returns:
            Config instance
        """
        backtest_data = data.get("backtest", {})
        engine_data = data.get("engine", {})
        risk_data = data.get("risk", {})

        return cls(
            backtest=BacktestConfig(**backtest_data),
            engine=EngineConfig(**engine_data),
            risk=RiskConfig(**risk_data),
        )

    def to_dict(self) -> dict:
        """Convert config to dictionary.

        Returns:
            Configuration dictionary
        """
        return {
            "backtest": {
                "initial_capital": self.backtest.initial_capital,
                "commission": self.backtest.commission,
                "slippage_pct": self.backtest.slippage_pct,
            },
            "engine": {
                "data_interval": self.engine.data_interval,
                "warmup_bars": self.engine.warmup_bars,
                "start_date": self.engine.start_date,
                "end_date": self.engine.end_date,
                "verbose": self.engine.verbose,
            },
            "risk": {
                "position_sizing": self.risk.position_sizing.value,
                "fixed_amount": self.risk.fixed_amount,
                "fixed_percent": self.risk.fixed_percent,
                "max_position_pct": self.risk.max_position_pct,
                "max_daily_loss_pct": self.risk.max_daily_loss_pct,
                "stop_loss_pct": self.risk.stop_loss_pct,
                "enable_stop_loss": self.risk.enable_stop_loss,
                "max_kelly": self.risk.max_kelly,
            },
        }


# Default configuration
DEFAULT_CONFIG = Config()


def get_default_config() -> Config:
    """Get default configuration.

    Returns:
        Default Config instance
    """
    return DEFAULT_CONFIG
