from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
import pytest

from pmdata.cache.impl import ParquetPriceCache, SQLiteMetadataCache

if TYPE_CHECKING:
    from pathlib import Path


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": [0, 60, 120],
            "open": [0.4, 0.5, 0.6],
            "high": [0.5, 0.6, 0.7],
            "low": [0.3, 0.4, 0.5],
            "close": [0.45, 0.55, 0.65],
            "volume": [5.0, 3.0, 4.0],
        }
    )


class TestParquetPriceCache:
    @pytest.fixture
    def cache(self, tmp_path: Path) -> ParquetPriceCache:
        return ParquetPriceCache(cache_dir=tmp_path)

    def test_has_bars_false_before_save(self, cache: ParquetPriceCache):
        assert cache.has_bars("tok_unknown") is False

    def test_save_and_has(self, cache: ParquetPriceCache):
        df = _sample_df()
        cache.save_bars("tok1", df)
        assert cache.has_bars("tok1") is True

    def test_load_returns_none_if_missing(self, cache: ParquetPriceCache):
        assert cache.load_bars("tok_missing") is None

    def test_save_then_load_roundtrip(self, cache: ParquetPriceCache):
        df = _sample_df()
        cache.save_bars("tok1", df)
        loaded = cache.load_bars("tok1")
        assert loaded is not None
        assert list(loaded.columns) == ["open", "high", "low", "close", "volume"]
        assert len(loaded) == 3

    def test_load_indexed_by_timestamp(self, cache: ParquetPriceCache):
        df = _sample_df()
        cache.save_bars("tok1", df)
        loaded = cache.load_bars("tok1")
        assert loaded is not None
        assert loaded.index.name == "timestamp"

    def test_save_indexed_df(self, cache: ParquetPriceCache):
        df = _sample_df().set_index("timestamp")
        cache.save_bars("tok2", df)
        loaded = cache.load_bars("tok2")
        assert loaded is not None
        assert len(loaded) == 3

    def test_save_empty_df_is_noop(self, cache: ParquetPriceCache):
        cache.save_bars("tok_empty", pd.DataFrame())
        assert cache.has_bars("tok_empty") is False

    def test_delete_bars(self, cache: ParquetPriceCache):
        df = _sample_df()
        cache.save_bars("tok1", df)
        cache.delete_bars("tok1")
        assert cache.has_bars("tok1") is False

    def test_delete_nonexistent_is_noop(self, cache: ParquetPriceCache):
        cache.delete_bars("not_there")

    def test_token_id_truncated_to_64(self, cache: ParquetPriceCache):
        long_id = "a" * 100
        df = _sample_df()
        cache.save_bars(long_id, df)
        assert cache.has_bars(long_id) is True


class TestSQLiteMetadataCache:
    @pytest.fixture
    def cache(self, tmp_path: Path) -> SQLiteMetadataCache:
        c = SQLiteMetadataCache(cache_dir=tmp_path)
        yield c
        c.close()

    def test_load_fetch_info_none_if_missing(self, cache: SQLiteMetadataCache):
        assert cache.load_fetch_info("unknown_tok") is None

    def test_save_and_load_fetch_info(self, cache: SQLiteMetadataCache):
        cache.save_fetch_info("tok1", 1000, 2000)
        info = cache.load_fetch_info("tok1")
        assert info == {"start_ts": 1000, "end_ts": 2000}

    def test_fetch_info_overwrite(self, cache: SQLiteMetadataCache):
        cache.save_fetch_info("tok1", 1000, 2000)
        cache.save_fetch_info("tok1", 3000, 4000)
        info = cache.load_fetch_info("tok1")
        assert info == {"start_ts": 3000, "end_ts": 4000}

    def test_load_market_none_if_missing(self, cache: SQLiteMetadataCache):
        assert cache.load_market("mkt_missing") is None

    def test_save_and_load_market(self, cache: SQLiteMetadataCache):
        data = {"id": "mkt_1", "question": "Will it?", "active": True}
        cache.save_market("mkt_1", data)
        loaded = cache.load_market("mkt_1")
        assert loaded == data

    def test_market_overwrite(self, cache: SQLiteMetadataCache):
        cache.save_market("mkt_1", {"question": "old"})
        cache.save_market("mkt_1", {"question": "new"})
        loaded = cache.load_market("mkt_1")
        assert loaded == {"question": "new"}

    def test_context_manager(self, tmp_path: Path):
        with SQLiteMetadataCache(cache_dir=tmp_path) as c:
            c.save_fetch_info("tok_cm", 0, 100)
            info = c.load_fetch_info("tok_cm")
        assert info == {"start_ts": 0, "end_ts": 100}
