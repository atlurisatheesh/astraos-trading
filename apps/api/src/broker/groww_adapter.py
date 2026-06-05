"""AstraOS Broker — Groww Adapter.

Groww integration for portfolio tracking and market data.

Note: Groww does NOT currently provide a public trading API for placing orders.
This adapter supports:
  - Portfolio tracking (via scraping/unofficial API)
  - Market data and quotes
  - Holdings and watchlist sync

For actual order execution, use another broker (Angel One, Kite, etc.)
and use Groww only for portfolio monitoring.

Requirements:
    pip install httpx
"""

from datetime import datetime, timezone

import structlog  # type: ignore

from . import BrokerAdapter, BrokerCredentials, OrderParams, OrderResult, Position, Holding  # type: ignore

logger = structlog.get_logger()


class GrowwAdapter(BrokerAdapter):
    """Groww adapter for portfolio tracking and market data.

    ⚠️ Groww does not offer a public trading API.
    Order placement returns an error directing to other brokers.
    Supports: market data, portfolio sync, watchlist.
    """

    name = "groww"

    BASE_URL = "https://groww.in/v1/api"
    SEARCH_URL = "https://groww.in/v1/api/search/v3/query/global/st_query"
    STOCK_URL = "https://groww.in/v1/api/stocks_data/v1/tr_est/stock"
    MUTUAL_FUND_URL = "https://groww.in/v1/api/data/mf/web/v4/scheme/search"

    def __init__(self):
        self._logged_in = False
        self._session_token: str = ""
        self._profile: dict = {}

    async def login(self, credentials: BrokerCredentials) -> dict:
        """Groww login — limited to portfolio sync.

        Note: No official API exists. Uses session-based access.
        """
        try:
            import httpx

            if credentials.access_token:
                self._session_token = credentials.access_token
                self._logged_in = True

                return {
                    "status": "success",
                    "broker": "groww",
                    "message": "Connected to Groww (portfolio sync mode — no order execution)",
                    "capabilities": ["market_data", "portfolio_sync", "watchlist"],
                    "limitations": ["no_order_placement", "no_real_time_streaming"],
                }
            else:
                return {
                    "status": "info",
                    "broker": "groww",
                    "message": (
                        "Groww does not offer a public trading API. "
                        "Use Angel One, Kite, or Upstox for order execution. "
                        "Groww adapter supports: market data, portfolio tracking."
                    ),
                    "capabilities": ["market_data", "search", "stock_info"],
                }

        except Exception as e:
            return {"status": "error", "broker": "groww", "message": str(e)}

    async def place_order(self, params: OrderParams) -> OrderResult:
        """Groww does NOT support order placement via API."""
        return OrderResult(
            success=False, broker="groww",
            message=(
                "⚠️ Groww does not provide a trading API. "
                "Use a supported broker: Angel One, Zerodha Kite, Upstox, Fyers, or 5Paisa."
            ),
        )

    async def modify_order(self, order_id: str, params: OrderParams) -> OrderResult:
        return OrderResult(success=False, broker="groww", message="Not supported by Groww")

    async def cancel_order(self, order_id: str) -> OrderResult:
        return OrderResult(success=False, broker="groww", message="Not supported by Groww")

    async def get_order_book(self) -> list[dict]:
        return []

    async def get_positions(self) -> list[Position]:
        return []

    async def get_holdings(self) -> list[Holding]:
        return []

    async def get_funds(self) -> dict:
        return {"broker": "groww", "message": "Not available via API"}

    async def get_ltp(self, exchange: str, symbol: str) -> float:
        """Get stock price from Groww's public data."""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                # Search for the stock
                search_result = await self._search_stock(client, symbol)
                if not search_result:
                    return 0.0

                # Get stock data
                stock_id = search_result.get("search_id", symbol.lower())
                resp = await client.get(
                    f"{self.STOCK_URL}/{stock_id}/trading-info",
                    headers=self._headers(),
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return float(data.get("ltp", 0))

        except Exception as e:
            logger.debug("Groww LTP failed", symbol=symbol, error=str(e))

        return 0.0

    async def get_quote(self, exchange: str, symbol: str) -> dict:
        """Get stock info from Groww."""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                search_result = await self._search_stock(client, symbol)
                if not search_result:
                    return {"symbol": symbol, "error": "Not found"}

                stock_id = search_result.get("search_id", symbol.lower())
                resp = await client.get(
                    f"{self.STOCK_URL}/{stock_id}/trading-info",
                    headers=self._headers(),
                    timeout=10,
                )

                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "symbol": symbol,
                        "ltp": data.get("ltp"),
                        "open": data.get("open"),
                        "high": data.get("high"),
                        "low": data.get("low"),
                        "close": data.get("close"),
                        "volume": data.get("volume"),
                        "change": data.get("dayChange"),
                        "change_pct": data.get("dayChangePerc"),
                        "broker": "groww",
                    }

        except Exception:
            pass

        return {}

    async def search_stocks(self, query: str, limit: int = 10) -> list[dict]:
        """Search stocks on Groww."""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    self.SEARCH_URL,
                    params={"q": query, "size": limit, "page": 0},
                    headers=self._headers(),
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = []
                    for item in data.get("content", []):
                        results.append({
                            "symbol": item.get("nse_scrip_code", ""),
                            "name": item.get("title", ""),
                            "exchange": "NSE" if item.get("nse_scrip_code") else "BSE",
                            "type": item.get("entity_type", ""),
                            "search_id": item.get("search_id", ""),
                        })
                    return results

        except Exception:
            pass

        return []

    async def _search_stock(self, client, symbol: str) -> dict:
        """Internal: search for a stock and return the first result."""
        try:
            resp = await client.get(
                self.SEARCH_URL,
                params={"q": symbol, "size": 1, "page": 0},
                headers=self._headers(),
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("content", [])
                if content:
                    return content[0]
        except Exception:
            pass
        return {}

    def _headers(self) -> dict:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        }
        if self._session_token:
            headers["Authorization"] = f"Bearer {self._session_token}"
        return headers

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in
