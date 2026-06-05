"""AstraOS Routers — Knowledge & Strategy API."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ..core.dependencies import get_current_user
from ..knowledge.investment_frameworks import (
    GrahamScreen, FisherScreen, ShenanigansDetector, damodaran_dcf, ExpectedReturnDecomposition
)
from ..knowledge.banknifty_strategies import (
    classify_regime, recommend_strategy, generate_bank_nifty_setup, MarketRegime
)
from ..knowledge.creator_lessons import CreatorLesson, get_creator_lesson_store

router = APIRouter(prefix="/api/v1/knowledge", tags=["Knowledge & Strategy"])


class CreatorLessonInput(BaseModel):
    creator: str = Field(..., min_length=2, max_length=100)
    title: str = Field(..., min_length=2, max_length=200)
    transcript: str = Field(..., min_length=20, max_length=10000)
    concepts: list[str] = []
    language: str = ""
    source_url: str = ""
    source_type: str = "instagram"
    source_note: str = "User-provided caption/transcript"


class CreatorLessonImport(BaseModel):
    filename: str = Field("creator_lessons", min_length=2, max_length=100)
    lessons: list[CreatorLessonInput] = Field(..., min_length=1)


@router.get("/creator-lessons")
async def list_creator_lessons(user=Depends(get_current_user)):
    """List locally loaded user-provided creator lessons."""
    lessons = get_creator_lesson_store().load(force=True)
    return {"count": len(lessons), "lessons": [lesson.to_dict() for lesson in lessons]}


@router.get("/creator-lessons/search")
async def search_creator_lessons(
    query: str = Query(..., min_length=3),
    k: int = Query(5, ge=1, le=20),
    user=Depends(get_current_user),
):
    """Search creator lessons by topic, title, or transcript text."""
    results = get_creator_lesson_store().search(query, k=k)
    return {"query": query, "count": len(results), "results": results}


@router.post("/creator-lessons/import")
async def import_creator_lessons(data: CreatorLessonImport, user=Depends(get_current_user)):
    """Import user-provided captions/transcripts into the local lesson store."""
    lessons = [CreatorLesson.from_dict(item.model_dump()) for item in data.lessons]
    path = get_creator_lesson_store().add_lessons(lessons, data.filename)
    return {"status": "imported", "count": len(lessons), "path": str(path)}


# ── Graham Value Screen ──

class GrahamInput(BaseModel):
    pe_ratio: float = 12
    pb_ratio: float = 1.2
    current_ratio: float = 2.5
    debt_to_equity: float = 0.3
    earnings_growth_10y: float = 8
    dividend_years: int = 7
    market_cap_cr: float = 5000


@router.post("/graham-screen")
async def graham_screen(data: GrahamInput, user=Depends(get_current_user)):
    """Run Graham-Dodd value screen (Security Analysis, 7th Ed).
    Scores stock against 8 defensive investor criteria."""
    screen = GrahamScreen(**data.model_dump())
    return screen.score()


# ── Fisher Quality Screen ──

class FisherInput(BaseModel):
    revenue_growth_3y: float = 18
    profit_margin: float = 15
    roe: float = 20
    rd_to_revenue: float = 5
    management_integrity: int = 8
    competitive_moat: int = 7
    market_potential: int = 8


@router.post("/fisher-screen")
async def fisher_screen(data: FisherInput, user=Depends(get_current_user)):
    """Run Fisher business quality screen (Common Stocks & Uncommon Profits).
    Evaluates 7 qualitative business factors."""
    screen = FisherScreen(**data.model_dump())
    return screen.score()


# ── Financial Shenanigans Detector ──

class ShenanigansInput(BaseModel):
    revenue_growth: float = 30
    cfo_growth: float = 10
    dso_change: float = 20
    capex_to_revenue_change: float = 5
    other_income_pct: float = 20
    related_party_pct: float = 8
    auditor_changed: bool = True
    accounting_policy_changed: bool = True
    inventory_growth_vs_revenue: float = 25


@router.post("/shenanigans-detect")
async def shenanigans_detect(data: ShenanigansInput, user=Depends(get_current_user)):
    """Detect accounting red flags (Financial Shenanigans, 4th Ed).
    Scans for 8 manipulation signals from Schilit's framework."""
    detector = ShenanigansDetector(**data.model_dump())
    return detector.detect()


# ── Damodaran DCF ──

class DCFInput(BaseModel):
    fcf: float = 5000         # ₹ Cr
    growth_rate: float = 0.12
    terminal_growth: float = 0.04
    wacc: float = 0.10
    projection_years: int = 10
    shares_outstanding: float = 100  # Cr


@router.post("/dcf-valuation")
async def dcf_valuation(data: DCFInput, user=Depends(get_current_user)):
    """Run Damodaran DCF valuation (Investment Valuation, 4th Ed).
    Returns intrinsic value with 25% and 40% margin-of-safety prices."""
    return damodaran_dcf(**data.model_dump())


# ── Expected Returns ──

class FactorInput(BaseModel):
    market_beta: float = 1.0
    value_loading: float = 0.3
    momentum_loading: float = 0.2
    size_loading: float = -0.1
    quality_loading: float = 0.4
    low_vol_loading: float = 0.1


@router.post("/expected-returns")
async def expected_returns(data: FactorInput, user=Depends(get_current_user)):
    """Calculate expected returns from factor exposures (Ilmanen framework)."""
    decomp = ExpectedReturnDecomposition(**data.model_dump())
    return decomp.expected_return()


# ── Bank Nifty Strategy ──

@router.get("/banknifty/regime")
async def banknifty_regime(
    vix: float = Query(16.5),
    adx: float = Query(28),
    atr_pct: float = Query(1.8),
    days_to_expiry: int = Query(3),
    trend: str = Query("up"),
    user=Depends(get_current_user),
):
    """Classify Bank Nifty market regime (Dalton + Sinclair).
    Returns regime type for strategy selection."""
    regime = classify_regime(vix, adx, atr_pct, days_to_expiry, trend)
    return {"regime": regime.value, "inputs": {"vix": vix, "adx": adx, "atr_pct": atr_pct, "dte": days_to_expiry}}


@router.get("/banknifty/strategy")
async def banknifty_strategy(
    spot: float = Query(52000),
    vix: float = Query(16.5),
    dte: int = Query(3),
    risk: str = Query("moderate"),
    user=Depends(get_current_user),
):
    """Recommend options strategies for Bank Nifty (Natenberg + McMillan).
    Returns top 3 strategies with legs, Greeks, and confidence."""
    regime = classify_regime(vix, 28, 1.8, dte, "neutral")
    strategies = recommend_strategy(regime, vix, spot, dte, risk_tolerance=risk)
    return {
        "regime": regime.value,
        "spot": spot,
        "strategies": [s.to_dict() for s in strategies],
    }


@router.get("/banknifty/setup")
async def banknifty_setup(
    spot: float = Query(52000),
    vix: float = Query(16.5),
    atr: float = Query(450),
    adx: float = Query(28),
    dte: int = Query(3),
    capital: float = Query(500000),
    user=Depends(get_current_user),
):
    """Generate Bank Nifty trade setup (trend/breakout/range).
    Returns entry, SL, targets, lots, options strategy, and pre-trade checklist."""
    regime = classify_regime(vix, adx, atr / spot * 100, dte, "up" if adx > 25 else "neutral")
    setup = generate_bank_nifty_setup(regime, spot, vix, atr, capital=capital)
    if not setup:
        return {"message": "No setup for current regime", "regime": regime.value}
    return setup.to_dict()
