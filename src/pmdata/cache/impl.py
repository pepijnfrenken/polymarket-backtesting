from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

import pyarrow as pa
import pyarrow.parquet as pq

if TYPE_CHECKING:
    import pandas as pd

_DEFAULT_CACHE_DIR = Path(os.getenv("PMDATA_CACHE_DIR", "~/.pmdata/cache")).expanduser()
_BARS_SCHEMA = pa.schema(
    [
        pa.field("timestamp", pa.int64()),
        pa.field("open", pa.float64()),
        pa.field("high", pa.float64()),
        pa.field("low", pa.float64()),
        pa.field("close", pa.float64()),
        pa.field("volume", pa.float64()),
    ]
)


class ParquetPriceCache:
    def __init__(self, cache_dir: Path | None = None) -> None:
        self._root = (cache_dir or _DEFAULT_CACHE_DIR) / "prices"
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, token_id: str) -> Path:
        safe = token_id.replace("/", "_")[:64]
        return self._root / f"{safe}.parquet"

    def save_bars(self, token_id: str, df: pd.DataFrame) -> None:
        if df.empty:
            return
        if "timestamp" not in df.columns and df.index.name == "timestamp":
            df = df.reset_index()
        table = pa.Table.from_pandas(df, schema=_BARS_SCHEMA)
        pq.write_table(table, self._path(token_id), compression="snappy")

    def load_bars(self, token_id: str) -> pd.DataFrame | None:
        path = self._path(token_id)
        if not path.exists():
            return None
        df = pq.read_table(path).to_pandas()
        return df.set_index("timestamp") if "timestamp" in df.columns else df

    def has_bars(self, token_id: str) -> bool:
        return self._path(token_id).exists()

    def delete_bars(self, token_id: str) -> None:
        path = self._path(token_id)
        if path.exists():
            path.unlink()


class SQLiteMetadataCache:
    def __init__(self, cache_dir: Path | None = None) -> None:
        db_path = (cache_dir or _DEFAULT_CACHE_DIR) / "metadata.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS fetch_info (
                token_id TEXT PRIMARY KEY,
                start_ts INTEGER NOT NULL,
                end_ts INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS markets (
                market_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            );
            """
        )
        self._conn.commit()

    def save_fetch_info(self, token_id: str, start_ts: int, end_ts: int) -> None:
        import time

        sql = (
            "INSERT OR REPLACE INTO fetch_info"
            " (token_id, start_ts, end_ts, updated_at) VALUES (?,?,?,?)"
        )
        self._conn.execute(sql, (token_id, start_ts, end_ts, int(time.time())))
        self._conn.commit()

    def load_fetch_info(self, token_id: str) -> dict[str, int] | None:
        row = self._conn.execute(
            "SELECT start_ts, end_ts FROM fetch_info WHERE token_id=?", (token_id,)
        ).fetchone()
        if row is None:
            return None
        return {"start_ts": row[0], "end_ts": row[1]}

    def save_market(self, market_id: str, data: dict) -> None:
        import time

        self._conn.execute(
            "INSERT OR REPLACE INTO markets (market_id, data, updated_at) VALUES (?,?,?)",
            (market_id, json.dumps(data), int(time.time())),
        )
        self._conn.commit()

    def load_market(self, market_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT data FROM markets WHERE market_id=?", (market_id,)
        ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> SQLiteMetadataCache:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
