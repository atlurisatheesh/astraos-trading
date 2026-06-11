"""AstraOS Schemas — Pydantic validation models for API requests/responses."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Auth ──────────────────────────────────────────────

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=12, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=255)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Instruments ───────────────────────────────────────

class InstrumentResponse(BaseModel):
    id: int
    symbol: str
    exchange: str
    instrument_type: str
    name: str | None
    lot_size: int
    sector: str | None
    industry: str | None
    is_active: bool

    model_config = {"from_attributes": True}


# ── Watchlists ────────────────────────────────────────

class WatchlistCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    # Stock symbols (e.g. ["RELIANCE", "TCS"]); field name kept for model compat
    instrument_ids: list[str] = []


class WatchlistResponse(BaseModel):
    id: int
    name: str
    instrument_ids: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Signals ───────────────────────────────────────────

class SignalResponse(BaseModel):
    id: uuid.UUID
    instrument_id: int
    signal_type: str
    confidence: Decimal
    entry_price: Decimal | None
    target_price: Decimal | None
    stop_loss: Decimal | None
    time_horizon: str | None
    reasoning: dict
    regime: str | None
    risk_reward: Decimal | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Orders ────────────────────────────────────────────

class OrderCreate(BaseModel):
    instrument_id: int
    order_type: str = Field(..., pattern="^(MARKET|LIMIT|SL|SL_M|GTT)$")
    side: str = Field(..., pattern="^(BUY|SELL)$")
    product: str = Field(..., pattern="^(CNC|MIS|NRML)$")
    quantity: int = Field(..., gt=0)
    price: Decimal | None = None
    trigger_price: Decimal | None = None
    strategy_id: uuid.UUID | None = None


class OrderResponse(BaseModel):
    id: uuid.UUID
    instrument_id: int
    broker: str
    order_type: str
    side: str
    product: str
    quantity: int
    price: Decimal | None
    status: str
    filled_quantity: int
    average_price: Decimal | None
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Positions ─────────────────────────────────────────

class PositionResponse(BaseModel):
    id: uuid.UUID
    instrument_id: int
    side: str
    quantity: int
    average_cost: Decimal
    current_price: Decimal | None
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    stop_loss: Decimal | None
    target: Decimal | None
    is_open: bool
    opened_at: datetime

    model_config = {"from_attributes": True}


# ── Strategies ────────────────────────────────────────

class StrategyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    strategy_type: str
    asset_class: str = Field(..., pattern="^(equity|futures|options|index)$")
    timeframe: str = Field(..., pattern="^(intraday|swing|positional|long_term)$")
    parameters: dict = {}
    risk_limits: dict = {}


class StrategyResponse(BaseModel):
    id: uuid.UUID
    name: str
    strategy_type: str
    asset_class: str
    timeframe: str
    parameters: dict
    risk_limits: dict
    algo_id: str | None
    is_approved: bool
    is_active: bool
    wfe_score: Decimal | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Risk ──────────────────────────────────────────────

class RiskLimitsSchema(BaseModel):
    max_daily_loss_pct: float = 2.0
    max_weekly_drawdown_pct: float = 5.0
    max_strategy_drawdown_pct: float = 10.0
    max_portfolio_drawdown_pct: float = 15.0
    max_single_position_pct: float = 5.0
    max_sector_exposure_pct: float = 25.0
    max_correlation_cluster_pct: float = 30.0
    max_fo_exposure_pct: float = 40.0
    max_leverage: float = 2.0
    min_cash_reserve_pct: float = 20.0
    max_orders_per_second: int = 8
    slippage_threshold_pct: float = 0.5
    vix_circuit_breaker: float = 25.0
    news_freeze_minutes: int = 30
    stale_data_threshold_seconds: int = 30


class RiskCheckResult(BaseModel):
    passed: bool
    checks: dict[str, bool]
    rejection_reason: str | None = None


# ── General ───────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
