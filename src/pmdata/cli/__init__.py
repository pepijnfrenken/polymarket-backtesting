from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import click
import pandas as pd

from pmdata._version import __version__
from pmdata.client import PolymarketData
from pmdata.synthesis.orderbook import SynthesisConfig


@click.group()
@click.version_option(version=__version__, prog_name="pmdata")
def main() -> None:
    pass


@main.command()
@click.option("--active/--no-active", default=None, help="Filter by active status")
@click.option("--closed/--no-closed", default=None, help="Filter by closed status")
@click.option("--limit", default=20, show_default=True, help="Max markets to return")
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default="table")
def markets(active: bool | None, closed: bool | None, limit: int, fmt: str) -> None:
    with PolymarketData() as client:
        results = client.get_markets(active=active, closed=closed, limit=limit)
    if fmt == "json":
        click.echo(json.dumps([m.model_dump() for m in results], indent=2))
    else:
        for m in results:
            tokens = ", ".join(m.clob_token_ids[:1])
            click.echo(f"{m.id:<12} {m.question[:60]:<60} [{tokens[:20]}]")


@main.command()
@click.option("--market", "token_id", required=True, help="Token ID (from clobTokenIds)")
@click.option("--start", required=True, help="Start date (YYYY-MM-DD or unix ts)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD or unix ts)")
@click.option("--interval", default="1m", show_default=True, help="Bar interval (1m/5m/1h/6h/1d)")
@click.option("--output", "-o", default="-", help="Output file path (- for stdout)")
@click.option("--format", "fmt", type=click.Choice(["csv", "json", "parquet"]), default="csv")
@click.option("--no-cache", is_flag=True, help="Skip local cache")
def ohlcv(
    token_id: str,
    start: str,
    end: str,
    interval: str,
    output: str,
    fmt: str,
    no_cache: bool,
) -> None:
    start_ts = _parse_date(start)
    end_ts = _parse_date(end)
    with PolymarketData() as client:
        df = client.get_ohlcv(
            token_id=token_id,
            start=start_ts,
            end=end_ts,
            interval=interval,
            use_cache=not no_cache,
        )
    _write_df(df, output, fmt)


@main.command()
@click.option("--market", "token_id", required=True, help="Token ID")
@click.option("--start", required=True, help="Start date")
@click.option("--end", required=True, help="End date")
@click.option("--output", "-o", default="-", help="Output file path")
@click.option("--format", "fmt", type=click.Choice(["csv", "json"]), default="json")
def prices(token_id: str, start: str, end: str, output: str, fmt: str) -> None:
    start_ts = _parse_date(start)
    end_ts = _parse_date(end)
    with PolymarketData() as client:
        pts = client.get_raw_prices(token_id=token_id, start=start_ts, end=end_ts)
    data = [p.model_dump() for p in pts]
    if fmt == "json":
        text = json.dumps(data, indent=2)
    else:
        df = pd.DataFrame(data)
        text = df.to_csv(index=False)
    _write_text(text, output)


@main.command()
@click.option("--market", "token_id", required=True, help="Token ID")
@click.option("--timestamp", required=True, help="Target timestamp (YYYY-MM-DD or unix ts)")
@click.option("--lookback-days", default=7, show_default=True, help="Days of history to use")
@click.option("--depth-levels", default=10, show_default=True, help="Orderbook depth levels")
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default="json")
def orderbook(
    token_id: str,
    timestamp: str,
    lookback_days: int,
    depth_levels: int,
    fmt: str,
) -> None:
    ts = _parse_date(timestamp)
    config = SynthesisConfig(depth_levels=depth_levels)
    with PolymarketData() as client:
        ob = client.get_synthetic_orderbook(
            token_id=token_id,
            timestamp=ts,
            lookback_days=lookback_days,
            config=config,
        )
    if fmt == "json":
        click.echo(json.dumps(ob.model_dump(), indent=2))
    else:
        click.echo(f"Orderbook for {token_id} @ {ob.timestamp} (synthetic={ob.is_synthetic})")
        header = f"{'BID':>10}  {'SIZE':>9}  {'ASK':>10}  {'SIZE':>9}"
        click.echo(header)
        for bid, ask in zip(ob.bids, ob.asks, strict=False):
            row = f"{bid.price:>10.4f}  {bid.size:>9.2f}  {ask.price:>10.4f}  {ask.size:>9.2f}"
            click.echo(row)


@main.command()
@click.option("--market", "token_id", required=True, help="Token ID to fetch and cache")
@click.option("--days", default=90, show_default=True, help="Days of history to fetch")
@click.option("--interval", default="1m", show_default=True, help="Bar interval")
@click.option("--cache-dir", default=None, help="Cache directory path")
def fetch(token_id: str, days: int, interval: str, cache_dir: str | None) -> None:
    cache_path = Path(cache_dir) if cache_dir else None
    with PolymarketData(cache_dir=cache_path) as client:
        df = client.fetch_and_cache(token_id=token_id, days=days, interval=interval)
    click.echo(f"Fetched {len(df)} bars ({interval}) for {token_id}")
    if not df.empty:
        click.echo(f"Range: {df.index.min()} -> {df.index.max()}")


def _parse_date(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        dt = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
        return int(dt.timestamp())


def _write_df(df: pd.DataFrame, output: str, fmt: str) -> None:
    if fmt == "parquet":
        path = output if output != "-" else "output.parquet"
        df.to_parquet(path)
        click.echo(f"Written to {path}", err=True)
        return
    if fmt == "json":
        text = df.reset_index().to_json(orient="records", indent=2)
    else:
        text = df.reset_index().to_csv(index=False)
    _write_text(text or "", output)


def _write_text(text: str, output: str) -> None:
    if output == "-":
        click.echo(text)
    else:
        Path(output).write_text(text)
        click.echo(f"Written to {output}", err=True)
