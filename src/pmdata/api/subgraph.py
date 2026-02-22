from __future__ import annotations

import os
import time

from gql import Client, gql
from gql.transport.httpx import HTTPXTransport

from pmdata.models import Trade

_SUBGRAPH_URL = os.getenv(
    "PMDATA_SUBGRAPH_URL",
    "https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw"
    "/subgraphs/orderbook-subgraph/0.0.1/gn",
)
_PAGE_SIZE = 1000

_FILLS_QUERY = gql("""
    query GetFills(
        $assetId: String!,
        $startTs: BigInt!,
        $endTs: BigInt!,
        $lastId: ID!
    ) {
        orderFilledEvents(
            first: 1000,
            where: {
                makerAssetId: $assetId,
                timestamp_gte: $startTs,
                timestamp_lte: $endTs,
                id_gt: $lastId
            },
            orderBy: timestamp,
            orderDirection: asc
        ) {
            id
            timestamp
            makerAssetId
            takerAssetId
            makerAmountFilled
            takerAmountFilled
        }
    }
""")


def _parse_trade(event: dict, token_id: str) -> Trade | None:
    try:
        maker_asset = str(event["makerAssetId"])
        maker_amount = int(event["makerAmountFilled"])
        taker_amount = int(event["takerAmountFilled"])
        if maker_amount <= 0 or taker_amount <= 0:
            return None
        if maker_asset == token_id:
            price = taker_amount / maker_amount
            size = maker_amount / 1e6
            side = "SELL"
        else:
            price = maker_amount / taker_amount
            size = taker_amount / 1e6
            side = "BUY"
        if not (0.0 < price < 1.0):
            return None
        return Trade(
            timestamp=int(event["timestamp"]),
            price=price,
            size=size,
            side=side,
            order_id=event["id"],
            token_id=token_id,
        )
    except (KeyError, ValueError, ZeroDivisionError):
        return None


class SubgraphClient:
    def __init__(self, timeout: float = 60.0) -> None:
        transport = HTTPXTransport(url=_SUBGRAPH_URL, timeout=timeout)
        self._client = Client(transport=transport, fetch_schema_from_transport=False)

    def get_order_filled_events(
        self,
        token_id: str,
        start_ts: int,
        end_ts: int,
    ) -> list[Trade]:
        all_trades: list[Trade] = []
        last_id = ""
        with self._client as session:
            while True:
                result = session.execute(
                    _FILLS_QUERY,
                    variable_values={
                        "assetId": token_id,
                        "startTs": str(start_ts),
                        "endTs": str(end_ts),
                        "lastId": last_id,
                    },
                )
                events = result.get("orderFilledEvents", [])
                for event in events:
                    trade = _parse_trade(event, token_id)
                    if trade is not None:
                        all_trades.append(trade)
                if len(events) < _PAGE_SIZE:
                    break
                last_id = events[-1]["id"]
                time.sleep(0.1)
        return all_trades
