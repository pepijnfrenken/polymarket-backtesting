from __future__ import annotations

import os
import time
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from pmdata.models import Interval, Orderbook, OrderbookLevel, PricePoint

_CLOB_BASE = os.getenv("PMDATA_CLOB_BASE_URL", "https://clob.polymarket.com")
_PRICES_LIMIT = 1000
_BOOK_LIMIT = 1500
_WINDOW_SECS = 10.0


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {429, 500, 502, 503, 504}
    return isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError))


_MAX_WINDOW_SECS = 14 * 86400  # API enforces ~15-day max; use 14 to be safe


class ClobClient:
    def __init__(self, timeout: float = 30.0) -> None:
        self._client = httpx.Client(base_url=_CLOB_BASE, timeout=timeout)
        self._price_times: list[float] = []
        self._book_times: list[float] = []

    def _throttle(self, bucket: list[float], limit: int, window: float) -> None:
        while True:
            now = time.monotonic()
            while bucket and now - bucket[0] >= window:
                bucket.pop(0)
            if len(bucket) < limit:
                bucket.append(now)
                return
            time.sleep(max(0.001, bucket[0] + window - now))

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception(_is_retryable),
    )
    def get_prices_history(
        self,
        token_id: str,
        start_ts: int | None = None,
        end_ts: int | None = None,
        interval: Interval | None = None,
        fidelity: int = 1,
    ) -> list[PricePoint]:
        if start_ts is not None and end_ts is not None and (end_ts - start_ts) > _MAX_WINDOW_SECS:
            return self._get_prices_history_chunked(token_id, start_ts, end_ts, fidelity)
        return self._get_prices_history_single(token_id, start_ts, end_ts, interval, fidelity)

    def _get_prices_history_chunked(
        self,
        token_id: str,
        start_ts: int,
        end_ts: int,
        fidelity: int,
    ) -> list[PricePoint]:
        all_points: list[PricePoint] = []
        chunk_start = start_ts
        while chunk_start < end_ts:
            chunk_end = min(chunk_start + _MAX_WINDOW_SECS, end_ts)
            all_points.extend(
                self._get_prices_history_single(token_id, chunk_start, chunk_end, None, fidelity)
            )
            chunk_start = chunk_end
        return all_points

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception(_is_retryable),
    )
    def _get_prices_history_single(
        self,
        token_id: str,
        start_ts: int | None = None,
        end_ts: int | None = None,
        interval: Interval | None = None,
        fidelity: int = 1,
    ) -> list[PricePoint]:
        self._throttle(self._price_times, _PRICES_LIMIT, _WINDOW_SECS)
        params: dict[str, Any] = {"market": token_id, "fidelity": fidelity}
        if start_ts is not None:
            params["startTs"] = start_ts
        if end_ts is not None:
            params["endTs"] = end_ts
        if interval is not None:
            params["interval"] = interval.value
        resp = self._client.get("/prices-history", params=params)
        resp.raise_for_status()
        return [PricePoint(t=item["t"], p=item["p"]) for item in resp.json().get("history", [])]

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception(_is_retryable),
    )
    def get_orderbook(self, token_id: str) -> Orderbook:
        self._throttle(self._book_times, _BOOK_LIMIT, _WINDOW_SECS)
        resp = self._client.get("/book", params={"token_id": token_id})
        resp.raise_for_status()
        data = resp.json()
        return Orderbook(
            timestamp=int(data.get("timestamp", int(time.time()))),
            market=data.get("market", ""),
            token_id=token_id,
            bids=[
                OrderbookLevel(price=float(b["price"]), size=float(b["size"]))
                for b in data.get("bids", [])
            ],
            asks=[
                OrderbookLevel(price=float(a["price"]), size=float(a["size"]))
                for a in data.get("asks", [])
            ],
            is_synthetic=False,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ClobClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
