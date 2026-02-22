from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest
from click.testing import CliRunner

from pmdata.cli import main
from pmdata.models import Market, Orderbook, OrderbookLevel, PricePoint


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _mock_market() -> Market:
    return Market(
        id="mkt_1",
        question="Will it happen?",
        condition_id="cond_abc",
        clob_token_ids=["tok_yes", "tok_no"],
        outcomes=["Yes", "No"],
        active=True,
        closed=False,
        resolved=False,
    )


def _mock_ohlcv_df() -> pd.DataFrame:
    return pd.DataFrame(
        {"open": [0.5], "high": [0.6], "low": [0.4], "close": [0.55], "volume": [5.0]},
        index=pd.Index([1000], name="timestamp"),
    )


def _mock_orderbook() -> Orderbook:
    return Orderbook(
        timestamp=1000,
        market="",
        token_id="tok_yes",
        bids=[OrderbookLevel(price=0.48, size=100.0)],
        asks=[OrderbookLevel(price=0.52, size=80.0)],
        is_synthetic=True,
    )


class TestMarketsCommand:
    def test_table_format(self, runner: CliRunner):
        with patch("pmdata.cli.PolymarketData") as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get_markets.return_value = [_mock_market()]
            result = runner.invoke(main, ["markets", "--format", "table"])
        assert result.exit_code == 0
        assert "mkt_1" in result.output

    def test_json_format(self, runner: CliRunner):
        with patch("pmdata.cli.PolymarketData") as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get_markets.return_value = [_mock_market()]
            result = runner.invoke(main, ["markets", "--format", "json"])
        assert result.exit_code == 0
        assert '"id": "mkt_1"' in result.output

    def test_limit_passed_to_client(self, runner: CliRunner):
        with patch("pmdata.cli.PolymarketData") as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get_markets.return_value = []
            result = runner.invoke(main, ["markets", "--limit", "5"])
        assert result.exit_code == 0
        instance.get_markets.assert_called_once()
        call_kwargs = instance.get_markets.call_args
        assert call_kwargs.kwargs.get("limit") == 5 or call_kwargs.args[2] == 5


class TestOhlcvCommand:
    def test_csv_output_to_stdout(self, runner: CliRunner):
        with patch("pmdata.cli.PolymarketData") as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get_ohlcv.return_value = _mock_ohlcv_df()
            result = runner.invoke(
                main,
                ["ohlcv", "--market", "tok1", "--start", "2024-01-01", "--end", "2024-01-02"],
            )
        assert result.exit_code == 0
        assert "open" in result.output

    def test_json_format(self, runner: CliRunner):
        with patch("pmdata.cli.PolymarketData") as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get_ohlcv.return_value = _mock_ohlcv_df()
            result = runner.invoke(
                main,
                [
                    "ohlcv",
                    "--market",
                    "tok1",
                    "--start",
                    "2024-01-01",
                    "--end",
                    "2024-01-02",
                    "--format",
                    "json",
                ],
            )
        assert result.exit_code == 0
        assert "open" in result.output

    def test_no_cache_flag(self, runner: CliRunner):
        with patch("pmdata.cli.PolymarketData") as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get_ohlcv.return_value = _mock_ohlcv_df()
            runner.invoke(
                main,
                [
                    "ohlcv",
                    "--market",
                    "tok1",
                    "--start",
                    "2024-01-01",
                    "--end",
                    "2024-01-02",
                    "--no-cache",
                ],
            )
        call_kwargs = instance.get_ohlcv.call_args
        assert call_kwargs.kwargs.get("use_cache") is False


class TestPricesCommand:
    def test_json_output(self, runner: CliRunner):
        with patch("pmdata.cli.PolymarketData") as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get_raw_prices.return_value = [PricePoint(t=1000, p=0.5)]
            result = runner.invoke(
                main,
                ["prices", "--market", "tok1", "--start", "2024-01-01", "--end", "2024-01-02"],
            )
        assert result.exit_code == 0
        assert "0.5" in result.output

    def test_csv_format(self, runner: CliRunner):
        with patch("pmdata.cli.PolymarketData") as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get_raw_prices.return_value = [PricePoint(t=1000, p=0.5)]
            result = runner.invoke(
                main,
                [
                    "prices",
                    "--market",
                    "tok1",
                    "--start",
                    "2024-01-01",
                    "--end",
                    "2024-01-02",
                    "--format",
                    "csv",
                ],
            )
        assert result.exit_code == 0
        assert "t,p" in result.output or "1000" in result.output


class TestOrderbookCommand:
    def test_json_output(self, runner: CliRunner):
        with patch("pmdata.cli.PolymarketData") as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get_synthetic_orderbook.return_value = _mock_orderbook()
            result = runner.invoke(
                main,
                ["orderbook", "--market", "tok_yes", "--timestamp", "2024-01-01"],
            )
        assert result.exit_code == 0
        assert "0.48" in result.output

    def test_table_format(self, runner: CliRunner):
        with patch("pmdata.cli.PolymarketData") as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get_synthetic_orderbook.return_value = _mock_orderbook()
            result = runner.invoke(
                main,
                [
                    "orderbook",
                    "--market",
                    "tok_yes",
                    "--timestamp",
                    "2024-01-01",
                    "--format",
                    "table",
                ],
            )
        assert result.exit_code == 0
        assert "Orderbook" in result.output


class TestFetchCommand:
    def test_fetch_reports_bar_count(self, runner: CliRunner):
        with patch("pmdata.cli.PolymarketData") as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.fetch_and_cache.return_value = _mock_ohlcv_df()
            result = runner.invoke(
                main,
                ["fetch", "--market", "tok1", "--days", "7"],
            )
        assert result.exit_code == 0
        assert "1 bars" in result.output


class TestParseDateHelper:
    def test_unix_timestamp(self, runner: CliRunner):
        with patch("pmdata.cli.PolymarketData") as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get_raw_prices.return_value = []
            result = runner.invoke(
                main,
                ["prices", "--market", "tok1", "--start", "1700000000", "--end", "1700086400"],
            )
        assert result.exit_code == 0
        call = instance.get_raw_prices.call_args
        assert call.kwargs.get("start") == 1700000000 or 1700000000 in call.args

    def test_date_string(self, runner: CliRunner):
        with patch("pmdata.cli.PolymarketData") as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get_raw_prices.return_value = []
            result = runner.invoke(
                main,
                ["prices", "--market", "tok1", "--start", "2024-06-01", "--end", "2024-06-02"],
            )
        assert result.exit_code == 0
