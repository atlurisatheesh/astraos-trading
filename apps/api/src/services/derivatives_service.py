"""AstraOS Services — F&O Options Chain & Derivatives Data.

Fetches options chain data to calculate resistance/support via Open Interest:
- Options Chain: call/put strikes, LTP, IV, OI from NSE + yfinance
- PCR (Put-Call Ratio): market sentiment indicator
- Max Pain: strike price where option writers lose least
- IV Surface: implied volatility across strikes and expiries
- Greeks: delta, gamma, theta, vega for each contract

Data sources (all free):
- NSE public option chain API (primary, real-time during market hours)
- yfinance options chain (fallback, delayed)
- Broker APIs (Angel One, Upstox) when connected

Integrates with existing quant/options_pricer.py for Black-Scholes calculations.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import structlog

from ..quant.options_pricer import black_scholes, calculate_max_pain, calculate_pcr

logger = structlog.get_logger()


@dataclass
class OptionContract:
    """A single option contract in the chain."""
    strike: float
    option_type: str  # "CE" or "PE"
    ltp: float = 0.0
    open_interest: int = 0
    change_in_oi: int = 0
    volume: int = 0
    iv: float = 0.0
    bid_price: float = 0.0
    ask_price: float = 0.0
    # Greeks (computed)
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None

    def to_dict(self) -> dict:
        d = {
            "strike": self.strike,
            "option_type": self.option_type,
            "ltp": self.ltp,
            "open_interest": self.open_interest,
            "change_in_oi": self.change_in_oi,
            "volume": self.volume,
            "iv": round(self.iv, 2) if self.iv else 0,
            "bid_price": self.bid_price,
            "ask_price": self.ask_price,
        }
        if self.delta is not None:
            d["greeks"] = {
                "delta": round(self.delta, 4),
                "gamma": round(self.gamma, 6) if self.gamma else 0,
                "theta": round(self.theta, 4) if self.theta else 0,
                "vega": round(self.vega, 4) if self.vega else 0,
            }
        return d


@dataclass
class OptionsChainData:
    """Complete options chain for a symbol and expiry."""
    symbol: str
    underlying_price: float
    expiry: str
    available_expiries: list[str] = field(default_factory=list)
    calls: list[OptionContract] = field(default_factory=list)
    puts: list[OptionContract] = field(default_factory=list)
    pcr_oi: float = 0.0
    pcr_volume: float = 0.0
    max_pain: float = 0.0
    total_call_oi: int = 0
    total_put_oi: int = 0
    total_call_volume: int = 0
    total_put_volume: int = 0
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "underlying_price": self.underlying_price,
            "expiry": self.expiry,
            "available_expiries": self.available_expiries,
            "calls": [c.to_dict() for c in self.calls],
            "puts": [p.to_dict() for p in self.puts],
            "analytics": {
                "pcr_oi": self.pcr_oi,
                "pcr_volume": self.pcr_volume,
                "max_pain": self.max_pain,
                "total_call_oi": self.total_call_oi,
                "total_put_oi": self.total_put_oi,
                "total_call_volume": self.total_call_volume,
                "total_put_volume": self.total_put_volume,
                "sentiment": self._sentiment(),
            },
            "timestamp": self.timestamp,
        }

    def _sentiment(self) -> str:
        """Derive market sentiment from PCR."""
        if self.pcr_oi > 1.2:
            return "bullish"  # More puts = writers expect rise
        elif self.pcr_oi < 0.8:
            return "bearish"  # More calls = writers expect fall
        return "neutral"


@dataclass
class IVSurfacePoint:
    """A single point on the IV surface."""
    strike: float
    expiry: str
    iv: float
    option_type: str
    moneyness: float  # strike / spot

    def to_dict(self) -> dict:
        return {
            "strike": self.strike,
            "expiry": self.expiry,
            "iv": round(self.iv, 2),
            "option_type": self.option_type,
            "moneyness": round(self.moneyness, 4),
        }


# ── Derivatives Service ─────────────────────────────────────


class DerivativesService:
    """Fetch and analyze F&O derivatives data.

    Primary: NSE public option chain API (real-time)
    Fallback: yfinance (delayed, global coverage)
    """

    async def get_options_chain(
        self,
        symbol: str,
        expiry: str | None = None,
        compute_greeks: bool = True,
    ) -> OptionsChainData:
        """Get full options chain with analytics.

        Tries NSE first, falls back to yfinance.
        """
        # Try NSE public API first
        chain = await self._fetch_nse_chain(symbol, expiry)

        # Fallback: Angel One optionGreek (works on cloud hosts where NSE blocks)
        if not chain or (not chain.calls and not chain.puts):
            chain = await self._fetch_angel_chain(symbol, expiry)

        # Fallback to yfinance
        if not chain or (not chain.calls and not chain.puts):
            chain = await self._fetch_yfinance_chain(symbol, expiry)

        if chain and compute_greeks:
            self._compute_greeks_for_chain(chain)

        return chain or OptionsChainData(
            symbol=symbol, underlying_price=0, expiry=expiry or "",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def get_pcr(self, symbol: str) -> dict:
        """Get Put-Call Ratio analysis for a symbol."""
        chain = await self.get_options_chain(symbol, compute_greeks=False)
        return {
            "symbol": symbol,
            "pcr_oi": chain.pcr_oi,
            "pcr_volume": chain.pcr_volume,
            "total_call_oi": chain.total_call_oi,
            "total_put_oi": chain.total_put_oi,
            "sentiment": chain._sentiment(),
            "interpretation": self._interpret_pcr(chain.pcr_oi),
        }

    async def get_max_pain(self, symbol: str, expiry: str | None = None) -> dict:
        """Calculate max pain strike for a symbol."""
        chain = await self.get_options_chain(symbol, expiry=expiry, compute_greeks=False)
        return {
            "symbol": symbol,
            "expiry": chain.expiry,
            "max_pain": chain.max_pain,
            "underlying_price": chain.underlying_price,
            "distance_pct": round(
                ((chain.max_pain - chain.underlying_price) / chain.underlying_price * 100)
                if chain.underlying_price > 0 else 0, 2
            ),
        }

    async def get_iv_surface(self, symbol: str) -> list[IVSurfacePoint]:
        """Get IV surface data across strikes and expiries."""
        chain = await self.get_options_chain(symbol, compute_greeks=False)
        points: list[IVSurfacePoint] = []

        spot = chain.underlying_price
        if spot <= 0:
            return points

        for contract in chain.calls + chain.puts:
            if contract.iv > 0:
                points.append(IVSurfacePoint(
                    strike=contract.strike,
                    expiry=chain.expiry,
                    iv=contract.iv,
                    option_type=contract.option_type,
                    moneyness=contract.strike / spot,
                ))

        points.sort(key=lambda p: (p.expiry, p.strike))
        return points

    async def get_oi_analysis(self, symbol: str) -> dict:
        """Get Open Interest analysis for support/resistance levels."""
        chain = await self.get_options_chain(symbol, compute_greeks=False)

        # Find max OI strikes (support/resistance)
        max_call_oi_strike = 0.0
        max_call_oi = 0
        max_put_oi_strike = 0.0
        max_put_oi = 0

        for c in chain.calls:
            if c.open_interest > max_call_oi:
                max_call_oi = c.open_interest
                max_call_oi_strike = c.strike

        for p in chain.puts:
            if p.open_interest > max_put_oi:
                max_put_oi = p.open_interest
                max_put_oi_strike = p.strike

        # Top 5 strikes by OI
        top_call_strikes = sorted(chain.calls, key=lambda c: c.open_interest, reverse=True)[:5]
        top_put_strikes = sorted(chain.puts, key=lambda p: p.open_interest, reverse=True)[:5]

        return {
            "symbol": symbol,
            "underlying_price": chain.underlying_price,
            "resistance": {
                "strike": max_call_oi_strike,
                "call_oi": max_call_oi,
                "interpretation": f"Strong resistance at {max_call_oi_strike} (max call OI)",
            },
            "support": {
                "strike": max_put_oi_strike,
                "put_oi": max_put_oi,
                "interpretation": f"Strong support at {max_put_oi_strike} (max put OI)",
            },
            "top_call_oi_strikes": [
                {"strike": c.strike, "oi": c.open_interest} for c in top_call_strikes
            ],
            "top_put_oi_strikes": [
                {"strike": p.strike, "oi": p.open_interest} for p in top_put_strikes
            ],
            "max_pain": chain.max_pain,
            "pcr_oi": chain.pcr_oi,
        }

    # ── NSE Chain Fetcher ───────────────────────────────────

    async def _fetch_nse_chain(self, symbol: str, expiry: str | None) -> OptionsChainData | None:
        """Fetch options chain from NSE public API."""
        try:
            from ..services.nse_bse_feed import get_nse_adapter

            nse = get_nse_adapter()
            data = await nse.get_option_chain(symbol)
            if not data or not data.get("chain"):
                return None

            underlying = float(data.get("underlying_value", 0))
            expiries = data.get("expiry_dates", [])
            selected_expiry = expiry or (expiries[0] if expiries else "")

            calls: list[OptionContract] = []
            puts: list[OptionContract] = []

            for record in data.get("chain", []):
                strike = float(record.get("strikePrice", 0))

                # Filter by expiry if specified
                ce_data = record.get("CE", {})
                pe_data = record.get("PE", {})

                if expiry and ce_data.get("expiryDate") != expiry and pe_data.get("expiryDate") != expiry:
                    continue

                if ce_data:
                    calls.append(OptionContract(
                        strike=strike,
                        option_type="CE",
                        ltp=float(ce_data.get("lastPrice", 0)),
                        open_interest=int(ce_data.get("openInterest", 0)),
                        change_in_oi=int(ce_data.get("changeinOpenInterest", 0)),
                        volume=int(ce_data.get("totalTradedVolume", 0)),
                        iv=float(ce_data.get("impliedVolatility", 0)),
                        bid_price=float(ce_data.get("bidprice", 0)),
                        ask_price=float(ce_data.get("askPrice", 0)),
                    ))

                if pe_data:
                    puts.append(OptionContract(
                        strike=strike,
                        option_type="PE",
                        ltp=float(pe_data.get("lastPrice", 0)),
                        open_interest=int(pe_data.get("openInterest", 0)),
                        change_in_oi=int(pe_data.get("changeinOpenInterest", 0)),
                        volume=int(pe_data.get("totalTradedVolume", 0)),
                        iv=float(pe_data.get("impliedVolatility", 0)),
                        bid_price=float(pe_data.get("bidprice", 0)),
                        ask_price=float(pe_data.get("askPrice", 0)),
                    ))

            # Compute analytics
            total_call_oi = sum(c.open_interest for c in calls)
            total_put_oi = sum(p.open_interest for p in puts)
            total_call_vol = sum(c.volume for c in calls)
            total_put_vol = sum(p.volume for p in puts)

            pcr_oi = calculate_pcr(total_put_oi, total_call_oi)
            pcr_vol = round(total_put_vol / max(total_call_vol, 1), 2)

            # Max pain
            strikes = sorted(set(c.strike for c in calls) | set(p.strike for p in puts))
            call_oi_map = {c.strike: c.open_interest for c in calls}
            put_oi_map = {p.strike: p.open_interest for p in puts}
            call_oi_list = [call_oi_map.get(s, 0) for s in strikes]
            put_oi_list = [put_oi_map.get(s, 0) for s in strikes]

            max_pain = calculate_max_pain(strikes, call_oi_list, put_oi_list) if strikes else 0

            return OptionsChainData(
                symbol=symbol,
                underlying_price=underlying,
                expiry=selected_expiry,
                available_expiries=expiries,
                calls=sorted(calls, key=lambda c: c.strike),
                puts=sorted(puts, key=lambda p: p.strike),
                pcr_oi=pcr_oi,
                pcr_volume=pcr_vol,
                max_pain=max_pain,
                total_call_oi=total_call_oi,
                total_put_oi=total_put_oi,
                total_call_volume=total_call_vol,
                total_put_volume=total_put_vol,
                timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            )

        except Exception as e:
            logger.warning("NSE option chain failed, falling back", symbol=symbol, error=str(e))
            return None

    # ── Angel One Chain Fetcher (optionGreek API) ───────────

    @staticmethod
    def _next_expiries(count: int = 4) -> list[str]:
        """Upcoming weekly (Thursday) expiries in Angel format DDMMMYYYY."""
        from datetime import date, timedelta

        today = date.today()
        days_to_thu = (3 - today.weekday()) % 7  # Thursday = 3
        first = today + timedelta(days=days_to_thu)
        return [
            (first + timedelta(weeks=w)).strftime("%d%b%Y").upper()
            for w in range(count)
        ]

    async def _fetch_angel_chain(self, symbol: str, expiry: str | None) -> OptionsChainData | None:
        """Build a chain from Angel One's optionGreek endpoint.

        Used when NSE blocks the server IP (Render). Provides strikes, IV,
        greeks and traded volume — optionGreek has no LTP/OI, so those stay 0
        and the UI shows what's available.
        """
        try:
            from ..routers.broker import get_active_sessions

            angel = next(
                (b for k, b in get_active_sessions().items()
                 if k.endswith(":angel") and getattr(b, "is_logged_in", False)),
                None,
            )
            if not angel:
                return None

            expiries = [expiry.upper()] if expiry else self._next_expiries()
            greeks: list[dict] = []
            used_expiry = ""
            for exp in expiries:
                greeks = await angel.get_option_greeks(symbol.upper(), exp)
                if greeks:
                    used_expiry = exp
                    break
            if not greeks:
                return None

            # Spot price from broker LTP (index symbols need NSE token; best-effort)
            underlying = 0.0
            try:
                underlying = await angel.get_ltp("NSE", symbol.upper())
            except Exception:
                pass

            calls: list[OptionContract] = []
            puts: list[OptionContract] = []
            for g in greeks:
                contract = OptionContract(
                    strike=float(g.get("strikePrice", 0)),
                    option_type=g.get("optionType", "CE"),
                    volume=int(float(g.get("tradeVolume", 0) or 0)),
                    iv=float(g.get("impliedVolatility", 0) or 0),
                    delta=float(g.get("delta", 0) or 0),
                    gamma=float(g.get("gamma", 0) or 0),
                    theta=float(g.get("theta", 0) or 0),
                    vega=float(g.get("vega", 0) or 0),
                )
                (calls if contract.option_type == "CE" else puts).append(contract)

            if not calls and not puts:
                return None

            total_call_vol = sum(c.volume for c in calls)
            total_put_vol = sum(p.volume for p in puts)

            logger.info("Options chain served from Angel One", symbol=symbol,
                        expiry=used_expiry, strikes=len(calls) + len(puts))

            return OptionsChainData(
                symbol=symbol,
                underlying_price=float(underlying or 0),
                expiry=used_expiry,
                available_expiries=self._next_expiries(),
                calls=sorted(calls, key=lambda c: c.strike),
                puts=sorted(puts, key=lambda p: p.strike),
                pcr_volume=round(total_put_vol / max(total_call_vol, 1), 2),
                total_call_volume=total_call_vol,
                total_put_volume=total_put_vol,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as e:
            logger.warning("Angel option chain failed", symbol=symbol, error=str(e))
            return None

    # ── yfinance Chain Fetcher ──────────────────────────────

    async def _fetch_yfinance_chain(self, symbol: str, expiry: str | None) -> OptionsChainData | None:
        """Fetch options chain from yfinance (fallback)."""
        import yfinance as yf

        yf_symbol = f"{symbol}.NS" if not symbol.endswith(".NS") and not symbol.startswith("^") else symbol
        try:
            ticker = yf.Ticker(yf_symbol)
            expirations = ticker.options
            if not expirations:
                return None

            selected = expiry or expirations[0]
            chain = ticker.option_chain(selected)

            spot_info = ticker.info
            spot = float(spot_info.get("currentPrice", spot_info.get("regularMarketPrice", 0)))

            calls: list[OptionContract] = []
            puts: list[OptionContract] = []

            if not chain.calls.empty:
                for _, row in chain.calls.iterrows():
                    calls.append(OptionContract(
                        strike=float(row.get("strike", 0)),
                        option_type="CE",
                        ltp=float(row.get("lastPrice", 0)),
                        open_interest=int(row.get("openInterest", 0)),
                        volume=int(row.get("volume", 0)) if pd.notna(row.get("volume")) else 0,
                        iv=float(row.get("impliedVolatility", 0)) * 100,  # yf returns decimal
                        bid_price=float(row.get("bid", 0)),
                        ask_price=float(row.get("ask", 0)),
                    ))

            if not chain.puts.empty:
                for _, row in chain.puts.iterrows():
                    puts.append(OptionContract(
                        strike=float(row.get("strike", 0)),
                        option_type="PE",
                        ltp=float(row.get("lastPrice", 0)),
                        open_interest=int(row.get("openInterest", 0)),
                        volume=int(row.get("volume", 0)) if pd.notna(row.get("volume")) else 0,
                        iv=float(row.get("impliedVolatility", 0)) * 100,
                        bid_price=float(row.get("bid", 0)),
                        ask_price=float(row.get("ask", 0)),
                    ))

            total_call_oi = sum(c.open_interest for c in calls)
            total_put_oi = sum(p.open_interest for p in puts)
            total_call_vol = sum(c.volume for c in calls)
            total_put_vol = sum(p.volume for p in puts)

            pcr_oi = calculate_pcr(total_put_oi, total_call_oi)
            pcr_vol = round(total_put_vol / max(total_call_vol, 1), 2)

            strikes = sorted(set(c.strike for c in calls) | set(p.strike for p in puts))
            call_oi_map = {c.strike: c.open_interest for c in calls}
            put_oi_map = {p.strike: p.open_interest for p in puts}
            call_oi_list = [call_oi_map.get(s, 0) for s in strikes]
            put_oi_list = [put_oi_map.get(s, 0) for s in strikes]
            max_pain = calculate_max_pain(strikes, call_oi_list, put_oi_list) if strikes else 0

            return OptionsChainData(
                symbol=symbol,
                underlying_price=spot,
                expiry=selected,
                available_expiries=list(expirations),
                calls=sorted(calls, key=lambda c: c.strike),
                puts=sorted(puts, key=lambda p: p.strike),
                pcr_oi=pcr_oi,
                pcr_volume=pcr_vol,
                max_pain=max_pain,
                total_call_oi=total_call_oi,
                total_put_oi=total_put_oi,
                total_call_volume=total_call_vol,
                total_put_volume=total_put_vol,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        except Exception as e:
            logger.error("yfinance option chain failed", symbol=symbol, error=str(e))
            return None

    # ── Greeks Computation ──────────────────────────────────

    def _compute_greeks_for_chain(self, chain: OptionsChainData) -> None:
        """Compute Greeks for all contracts in the chain using Black-Scholes."""
        spot = chain.underlying_price
        if spot <= 0:
            return

        # Estimate time to expiry from expiry string
        tte = self._estimate_tte(chain.expiry)
        if tte <= 0:
            return

        for contract in chain.calls + chain.puts:
            if contract.iv > 0 and contract.strike > 0:
                try:
                    greeks = black_scholes(
                        spot=spot,
                        strike=contract.strike,
                        time_to_expiry=tte,
                        risk_free_rate=0.065,  # RBI repo rate
                        volatility=contract.iv / 100,  # Convert from percentage
                        option_type=contract.option_type,
                    )
                    contract.delta = greeks.delta
                    contract.gamma = greeks.gamma
                    contract.theta = greeks.theta
                    contract.vega = greeks.vega
                except Exception:
                    pass

    @staticmethod
    def _estimate_tte(expiry_str: str) -> float:
        """Estimate time to expiry in years from expiry date string."""
        try:
            # Try common formats
            for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y", "%Y%m%d", "%b %d, %Y"):
                try:
                    exp_date = datetime.strptime(expiry_str, fmt).replace(tzinfo=timezone.utc)
                    now = datetime.now(timezone.utc)
                    days = (exp_date - now).days
                    return max(days, 1) / 365
                except ValueError:
                    continue
            # Default: assume 7 days
            return 7 / 365
        except Exception:
            return 7 / 365

    @staticmethod
    def _interpret_pcr(pcr: float) -> str:
        """Interpret PCR value."""
        if pcr > 1.5:
            return "Extremely bullish — excessive put writing suggests strong support below"
        elif pcr > 1.2:
            return "Bullish — put writers confident, market likely to hold or rise"
        elif pcr > 0.8:
            return "Neutral — balanced call/put writing, no clear directional bias"
        elif pcr > 0.5:
            return "Bearish — call writers dominating, resistance above"
        else:
            return "Extremely bearish — excessive call writing signals overhead resistance"


# ── Factory ─────────────────────────────────────────────────


_service: DerivativesService | None = None


def get_derivatives_service() -> DerivativesService:
    """Get singleton derivatives service."""
    global _service
    if _service is None:
        _service = DerivativesService()
    return _service
