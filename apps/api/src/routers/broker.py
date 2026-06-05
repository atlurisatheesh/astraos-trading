"""AstraOS Router — Multi-Broker API (Angel One, Kite, Upstox, Fyers, 5Paisa, Groww).

Unified API for all broker operations. Select broker via query parameter.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from ..core.dependencies import get_current_user
from ..broker import get_broker, list_brokers, BrokerCredentials, OrderParams
from ..models.user import User

router = APIRouter(prefix="/api/v1/broker", tags=["Broker (Multi-Broker)"])

# ── Active broker sessions (in-memory per user session) ──
_active_sessions: dict[str, object] = {}


def _session_key(user_id, broker_name: str) -> str:
    return f"{user_id}:{broker_name.lower()}"


def _get_user_broker_or_401(user_id, broker_name: str):
    broker = _active_sessions.get(_session_key(user_id, broker_name))
    if not broker:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Not logged in to {broker_name}",
        )
    return broker


class LoginRequest(BaseModel):
    """Universal login request for any broker."""
    broker: str = "paper"       # paper, angel, kite, upstox, fyers, 5paisa, groww
    api_key: str = ""
    api_secret: str = ""
    client_id: str = ""
    password: str = ""
    totp_secret: str = ""
    access_token: str = ""
    request_token: str = ""
    # Broker-specific extras
    redirect_uri: str = "https://localhost"
    app_name: str = ""
    app_source: str = ""
    email: str = ""
    pin: str = ""
    dob: str = ""


class OrderRequest(BaseModel):
    """Universal order request for any broker."""
    broker: str = "paper"
    symbol: str
    exchange: str = "NSE"
    side: str = "BUY"
    order_type: str = "MARKET"
    product: str = "DELIVERY"
    quantity: int = 1
    price: float = 0
    trigger_price: float = 0
    variety: str = "NORMAL"
    validity: str = "DAY"
    tag: str = "quantus"
    symbol_token: str = ""
    instrument_token: str = ""


# ═══════════════════════════════════════════════════════════════
# Broker Management
# ═══════════════════════════════════════════════════════════════

@router.get("/list")
async def available_brokers():
    """List all available broker adapters."""
    return {
        "brokers": list_brokers(),
        "supported": [
            {"name": "angel", "display": "Angel One", "trading": True, "sdk": "smartapi-python"},
            {"name": "kite", "display": "Zerodha Kite", "trading": True, "sdk": "kiteconnect"},
            {"name": "upstox", "display": "Upstox", "trading": True, "sdk": "upstox-python-sdk"},
            {"name": "fyers", "display": "Fyers", "trading": True, "sdk": "fyers-apiv3"},
            {"name": "5paisa", "display": "5Paisa", "trading": True, "sdk": "py5paisa"},
            {"name": "groww", "display": "Groww", "trading": False, "sdk": "httpx (REST)"},
            {"name": "paper", "display": "Paper Trading", "trading": True, "sdk": "built-in"},
        ],
    }


@router.get("/active")
async def active_sessions(current_user: User = Depends(get_current_user)):
    """List active broker sessions."""
    prefix = f"{current_user.id}:"
    return {
        "sessions": [
            {"broker": key.removeprefix(prefix), "logged_in": broker.is_logged_in}
            for key, broker in _active_sessions.items()
            if key.startswith(prefix)
        ]
    }


# ═══════════════════════════════════════════════════════════════
# Authentication
# ═══════════════════════════════════════════════════════════════

@router.post("/login")
async def broker_login(req: LoginRequest, current_user: User = Depends(get_current_user)):
    """Login to any broker. Returns auth status + profile."""
    broker = get_broker(req.broker)

    credentials = BrokerCredentials(
        api_key=req.api_key,
        api_secret=req.api_secret,
        client_id=req.client_id,
        password=req.password,
        totp_secret=req.totp_secret,
        access_token=req.access_token,
        request_token=req.request_token,
        extras={
            "redirect_uri": req.redirect_uri,
            "app_name": req.app_name,
            "app_source": req.app_source,
            "email": req.email,
            "pin": req.pin,
            "dob": req.dob,
        },
    )

    result = await broker.login(credentials)

    # Store session if login succeeded
    if result.get("status") == "success":
        _active_sessions[_session_key(current_user.id, req.broker)] = broker

    return result


@router.post("/logout/{broker_name}")
async def broker_logout(
    broker_name: str,
    current_user: User = Depends(get_current_user),
):
    """Logout from a broker session."""
    key = _session_key(current_user.id, broker_name)
    if key in _active_sessions:
        del _active_sessions[key]
        return {"status": "logged_out", "broker": broker_name}
    return {"status": "not_found", "broker": broker_name}


# ═══════════════════════════════════════════════════════════════
# Orders
# ═══════════════════════════════════════════════════════════════

@router.post("/order")
async def place_order(req: OrderRequest, current_user: User = Depends(get_current_user)):
    """Place an order on any broker."""
    broker = _active_sessions.get(_session_key(current_user.id, req.broker))
    if not broker:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Not logged in to {req.broker}. Login first via POST /api/v1/broker/login",
        )

    params = OrderParams(
        symbol=req.symbol,
        exchange=req.exchange,
        side=req.side,
        order_type=req.order_type,
        product=req.product,
        quantity=req.quantity,
        price=req.price,
        trigger_price=req.trigger_price,
        variety=req.variety,
        validity=req.validity,
        tag=req.tag,
        symbol_token=req.symbol_token,
        instrument_token=req.instrument_token,
    )

    result = await broker.place_order(params)
    return result.to_dict()


@router.delete("/order/{broker_name}/{order_id}")
async def cancel_order(
    broker_name: str,
    order_id: str,
    current_user: User = Depends(get_current_user),
):
    """Cancel an order on any broker."""
    broker = _active_sessions.get(_session_key(current_user.id, broker_name))
    if not broker:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Not logged in to {broker_name}")

    result = await broker.cancel_order(order_id)
    return result.to_dict()


@router.get("/orders/{broker_name}")
async def get_orders(
    broker_name: str,
    current_user: User = Depends(get_current_user),
):
    """Get order book for a broker."""
    broker = _get_user_broker_or_401(current_user.id, broker_name)

    return {"orders": await broker.get_order_book(), "broker": broker_name}


# ═══════════════════════════════════════════════════════════════
# Portfolio
# ═══════════════════════════════════════════════════════════════

@router.get("/positions/{broker_name}")
async def get_positions(
    broker_name: str,
    current_user: User = Depends(get_current_user),
):
    """Get positions for a broker."""
    broker = _get_user_broker_or_401(current_user.id, broker_name)

    positions = await broker.get_positions()
    return {
        "positions": [vars(p) for p in positions],
        "count": len(positions),
        "broker": broker_name,
    }


@router.get("/holdings/{broker_name}")
async def get_holdings(
    broker_name: str,
    current_user: User = Depends(get_current_user),
):
    """Get holdings for a broker."""
    broker = _get_user_broker_or_401(current_user.id, broker_name)

    holdings = await broker.get_holdings()
    return {
        "holdings": [vars(h) for h in holdings],
        "count": len(holdings),
        "broker": broker_name,
    }


@router.get("/funds/{broker_name}")
async def get_funds(
    broker_name: str,
    current_user: User = Depends(get_current_user),
):
    """Get available funds for a broker."""
    broker = _get_user_broker_or_401(current_user.id, broker_name)

    return await broker.get_funds()


# ═══════════════════════════════════════════════════════════════
# Market Data
# ═══════════════════════════════════════════════════════════════

@router.get("/ltp/{broker_name}/{exchange}/{symbol}")
async def get_ltp(
    broker_name: str,
    exchange: str,
    symbol: str,
    current_user: User = Depends(get_current_user),
):
    """Get Last Traded Price from a specific broker."""
    broker = _get_user_broker_or_401(current_user.id, broker_name)

    ltp = await broker.get_ltp(exchange, symbol)
    return {"symbol": symbol, "exchange": exchange, "ltp": ltp, "broker": broker_name}


@router.get("/quote/{broker_name}/{exchange}/{symbol}")
async def get_quote(
    broker_name: str,
    exchange: str,
    symbol: str,
    current_user: User = Depends(get_current_user),
):
    """Get full market quote from a specific broker."""
    broker = _get_user_broker_or_401(current_user.id, broker_name)

    return await broker.get_quote(exchange, symbol)


# ═══════════════════════════════════════════════════════════════
# Aggregated Portfolio (across all connected brokers)
# ═══════════════════════════════════════════════════════════════

@router.get("/portfolio/all")
async def aggregated_portfolio(current_user: User = Depends(get_current_user)):
    """Get combined portfolio across all connected brokers."""
    all_positions = []
    all_holdings = []
    all_funds = {}
    prefix = f"{current_user.id}:"

    for key, broker in _active_sessions.items():
        if not key.startswith(prefix):
            continue
        name = key.removeprefix(prefix)
        try:
            positions = await broker.get_positions()
            all_positions.extend([vars(p) for p in positions])
        except Exception:
            pass

        try:
            holdings = await broker.get_holdings()
            all_holdings.extend([vars(h) for h in holdings])
        except Exception:
            pass

        try:
            funds = await broker.get_funds()
            all_funds[name] = funds
        except Exception:
            pass

    total_pnl = sum(p.get("pnl", 0) for p in all_positions)
    total_holdings_value = sum(h.get("ltp", 0) * h.get("quantity", 0) for h in all_holdings)

    return {
        "positions": all_positions,
        "holdings": all_holdings,
        "funds": all_funds,
        "summary": {
            "total_positions": len(all_positions),
            "total_holdings": len(all_holdings),
            "total_pnl": round(total_pnl, 2),
            "total_holdings_value": round(total_holdings_value, 2),
            "connected_brokers": [
                key.removeprefix(prefix)
                for key in _active_sessions
                if key.startswith(prefix)
            ],
        },
    }
