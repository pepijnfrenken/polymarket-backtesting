from __future__ import annotations

import os
import time
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from pmdata.models import Market

_GAMMA_BASE = os.getenv("PMDATA_GAMMA_BASE_URL", "https://gamma-api.polymarket.com")
_MARKETS_LIMIT = 300
_WINDOW_SECS = 10.0


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {429, 500, 502, 503, 504}
    return isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError))


class GammaClient:
    def __init__(self, timeout: float = 30.0) -> None:
        self._client = httpx.Client(base_url=_GAMMA_BASE, timeout=timeout)
        self._request_times: list[float] = []

    def _throttle(self) -> None:
        while True:
            now = time.monotonic()
            while self._request_times and now - self._request_times[0] >= _WINDOW_SECS:
                self._request_times.pop(0)
            if len(self._request_times) < _MARKETS_LIMIT:
                self._request_times.append(now)
                return
            time.sleep(max(0.001, self._request_times[0] + _WINDOW_SECS - now))

    def _build_market(self, raw: dict[str, Any]) -> Market:
        return Market(
            id=str(raw.get("id", "")),
            question=raw.get("question", ""),
            condition_id=raw.get("conditionId", ""),
            clob_token_ids=raw.get("clobTokenIds", "[]"),
            outcomes=raw.get("outcomes", "[]"),
            active=bool(raw.get("active", False)),
            closed=bool(raw.get("closed", False)),
            resolved=bool(raw.get("resolved", False)),
            resolved_outcome=raw.get("resolvedOutcome"),
            end_date_iso=raw.get("endDate"),
            created_at=raw.get("createdAt"),
            start_date=raw.get("startDate"),
        )

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception(_is_retryable),
    )
    def get_markets(
        self,
        active: bool | None = None,
        closed: bool | None = None,
        limit: int = 100,
        offset: int = 0,
        order: str | None = None,
        ascending: bool | None = None,
        start_date_min: str | None = None,
        start_date_max: str | None = None,
    ) -> list[Market]:
        self._throttle()
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if active is not None:
            params["active"] = str(active).lower()
        if closed is not None:
            params["closed"] = str(closed).lower()
        if order is not None:
            params["order"] = order
        if ascending is not None:
            params["ascending"] = str(ascending).lower()
        if start_date_min is not None:
            params["start_date_min"] = start_date_min
        if start_date_max is not None:
            params["start_date_max"] = start_date_max
        resp = self._client.get("/markets", params=params)
        resp.raise_for_status()
        return [self._build_market(m) for m in resp.json()]

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception(_is_retryable),
    )
    def get_market(self, market_id: str) -> Market:
        self._throttle()
        resp = self._client.get(f"/markets/{market_id}")
        resp.raise_for_status()
        return self._build_market(resp.json())

    def iter_all_markets(
        self,
        active: bool | None = None,
        closed: bool | None = None,
        page_size: int = 100,
        order: str | None = None,
        ascending: bool | None = None,
        start_date_min: str | None = None,
        start_date_max: str | None = None,
    ) -> list[Market]:
        all_markets: list[Market] = []
        offset = 0
        while True:
            page = self.get_markets(
                active=active,
                closed=closed,
                limit=page_size,
                offset=offset,
                order=order,
                ascending=ascending,
                start_date_min=start_date_min,
                start_date_max=start_date_max,
            )
            all_markets.extend(page)
            if len(page) < page_size:
                break
            offset += page_size
        return all_markets

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> GammaClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
