from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, field_validator


class Interval(StrEnum):
    MAX = "max"
    ALL = "all"
    ONE_MINUTE = "1m"
    ONE_HOUR = "1h"
    SIX_HOURS = "6h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"


class PricePoint(BaseModel):
    t: int
    p: float


class PriceBar(BaseModel):
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class OrderbookLevel(BaseModel):
    price: float
    size: float


class Orderbook(BaseModel):
    timestamp: int
    market: str
    token_id: str
    bids: list[OrderbookLevel]
    asks: list[OrderbookLevel]
    is_synthetic: bool = False


class Trade(BaseModel):
    timestamp: int
    price: float
    size: float
    side: str
    order_id: str
    token_id: str


class Market(BaseModel):
    id: str
    question: str
    condition_id: str
    clob_token_ids: list[str]
    outcomes: list[str]
    active: bool
    closed: bool
    resolved: bool
    resolved_outcome: str | None = None
    end_date_iso: str | None = None

    @field_validator("clob_token_ids", "outcomes", mode="before")
    @classmethod
    def _parse_json_list(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return json.loads(v)
        return v
