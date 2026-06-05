"""AstraOS Quant — Time-of-Day and Expiry Cycle Features.

Encodes the two biggest free edges in Bank Nifty that retail traders ignore:
  1. Intraday time windows (opening range, lunch dump, square-off)
  2. Weekly expiry cycle positioning (T-4 to T-0 theta characteristics)
"""

import math
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

IST = ZoneInfo("Asia/Kolkata")


# ── Time-of-Day Windows ────────────────────────────────────────────────────

class IntradayWindow:
    """Classifies the current time into a Bank Nifty intraday regime."""

    WINDOWS = [
        ("pre_open",        9,  0,  9, 15, 0.1),  # Auction period — do not trade
        ("opening_chaos",   9, 15,  9, 30, 0.3),  # Wild moves, avoid new entries
        ("first_trend",     9, 30, 10, 30, 1.0),  # Best breakout window
        ("mid_morning",    10, 30, 11, 30, 0.8),  # Trend continuation
        ("lunch_range",    11, 30, 13,  0, 0.5),  # Consolidation — range plays
        ("lunch_dump",     13,  0, 13, 30, 0.6),  # Often fades, reversal watch
        ("afternoon_trend",13, 30, 14, 30, 0.9),  # Second trend leg
        ("expiry_vol",     14, 30, 15, 15, 0.7),  # Expiry-week gamma spike
        ("squareoff",      15, 15, 15, 30, 0.2),  # Rush to exit — avoid new
    ]

    @classmethod
    def classify(cls, now: datetime | None = None) -> dict:
        """Return the current window name, trade suitability score, and features."""
        if now is None:
            now = datetime.now(IST)

        current_minutes = now.hour * 60 + now.minute
        result = {
            "window_name": "closed",
            "trade_suitability": 0.0,
            "minutes_into_session": 0,
            "minutes_to_close": 0,
            "session_progress": 0.0,
        }

        session_start = 9 * 60 + 15
        session_end = 15 * 60 + 30
        session_len = session_end - session_start

        if current_minutes < session_start or current_minutes > session_end:
            return result

        result["minutes_into_session"] = current_minutes - session_start
        result["minutes_to_close"] = session_end - current_minutes
        result["session_progress"] = (current_minutes - session_start) / session_len

        for name, h1, m1, h2, m2, score in cls.WINDOWS:
            start = h1 * 60 + m1
            end = h2 * 60 + m2
            if start <= current_minutes < end:
                result["window_name"] = name
                result["trade_suitability"] = score
                break

        return result

    @classmethod
    def get_numeric_features(cls, now: datetime | None = None) -> dict[str, float]:
        """Return numeric features suitable for ML models."""
        if now is None:
            now = datetime.now(IST)

        info = cls.classify(now)
        minutes_into = info["minutes_into_session"]
        session_len = (15 * 60 + 30) - (9 * 60 + 15)

        progress = minutes_into / session_len if session_len > 0 else 0
        return {
            "tod_sin": math.sin(2 * math.pi * progress),
            "tod_cos": math.cos(2 * math.pi * progress),
            "tod_suitability": info["trade_suitability"],
            "tod_minutes_to_close": float(info["minutes_to_close"]),
            "tod_session_progress": progress,
        }


# ── Expiry Cycle Features ──────────────────────────────────────────────────

def _next_thursday(d: date) -> date:
    """Return the next Thursday on or after date d."""
    days_ahead = 3 - d.weekday()  # Thursday = 3
    if days_ahead < 0:
        days_ahead += 7
    return d + timedelta(days=days_ahead)


def _previous_thursday(d: date) -> date:
    """Return the most recent Thursday on or before date d."""
    days_back = d.weekday() - 3
    if days_back < 0:
        days_back += 7
    return d - timedelta(days=days_back)


NSE_HOLIDAYS_2025_2026 = {
    date(2025, 1, 26), date(2025, 2, 26), date(2025, 3, 14),
    date(2025, 3, 31), date(2025, 4, 10), date(2025, 4, 14),
    date(2025, 4, 18), date(2025, 5, 1), date(2025, 8, 15),
    date(2025, 8, 27), date(2025, 10, 2), date(2025, 10, 21),
    date(2025, 10, 22), date(2025, 11, 5), date(2025, 11, 26),
    date(2025, 12, 25),
    date(2026, 1, 26), date(2026, 3, 10), date(2026, 3, 17),
    date(2026, 3, 25), date(2026, 4, 2), date(2026, 4, 3),
    date(2026, 4, 14), date(2026, 5, 1), date(2026, 7, 17),
    date(2026, 8, 15), date(2026, 10, 2), date(2026, 10, 20),
    date(2026, 11, 9), date(2026, 11, 24), date(2026, 12, 25),
}


class ExpiryCycle:
    """Bank Nifty weekly expiry cycle features."""

    @classmethod
    def get_features(cls, today: date | None = None) -> dict:
        """Return expiry-cycle features for a given date."""
        if today is None:
            today = datetime.now(IST).date()

        expiry = _next_thursday(today)

        # If expiry day is a holiday, shift to Wednesday
        if expiry in NSE_HOLIDAYS_2025_2026:
            expiry = expiry - timedelta(days=1)

        days_to_expiry = (expiry - today).days

        # Trading days to expiry (exclude weekends and holidays)
        trading_dte = 0
        d = today
        while d < expiry:
            d += timedelta(days=1)
            if d.weekday() < 5 and d not in NSE_HOLIDAYS_2025_2026:
                trading_dte += 1

        is_expiry_day = today == expiry
        is_expiry_week = days_to_expiry <= 4

        # Theta decay acceleration (non-linear — accelerates near expiry)
        theta_factor = 1.0 / max(trading_dte, 0.5)

        # Premium writing suitability (best at T-2, T-3)
        if trading_dte == 0:
            writing_score = 0.2  # Expiry day: gamma risk too high
        elif trading_dte == 1:
            writing_score = 0.6  # T-1: fast decay but risky
        elif trading_dte in (2, 3):
            writing_score = 1.0  # Sweet spot for premium selling
        elif trading_dte == 4:
            writing_score = 0.8  # Monday of expiry week
        else:
            writing_score = 0.5  # Far from expiry

        # Directional play suitability
        if is_expiry_day:
            directional_score = 0.7  # Fast moves but tight SL needed
        elif trading_dte <= 2:
            directional_score = 0.8
        else:
            directional_score = 0.9

        return {
            "expiry_date": expiry.isoformat(),
            "days_to_expiry": days_to_expiry,
            "trading_dte": trading_dte,
            "is_expiry_day": is_expiry_day,
            "is_expiry_week": is_expiry_week,
            "theta_factor": round(theta_factor, 4),
            "writing_score": writing_score,
            "directional_score": directional_score,
        }

    @classmethod
    def get_numeric_features(cls, today: date | None = None) -> dict[str, float]:
        """Return numeric features for ML models."""
        f = cls.get_features(today)
        dte = f["trading_dte"]
        return {
            "expiry_dte": float(dte),
            "expiry_theta_factor": f["theta_factor"],
            "expiry_writing_score": f["writing_score"],
            "expiry_directional_score": f["directional_score"],
            "expiry_is_day": 1.0 if f["is_expiry_day"] else 0.0,
            "expiry_dte_sin": math.sin(2 * math.pi * min(dte, 5) / 5),
            "expiry_dte_cos": math.cos(2 * math.pi * min(dte, 5) / 5),
        }


def add_time_features_to_df(df: pd.DataFrame) -> pd.DataFrame:
    """Add time-of-day and expiry features to a DataFrame with datetime index."""
    if df.empty:
        return df

    df = df.copy()

    if hasattr(df.index, "date"):
        dates = df.index.date
    else:
        dates = [datetime.now(IST).date()] * len(df)

    expiry_cols = {k: [] for k in ExpiryCycle.get_numeric_features().keys()}
    for d in dates:
        feats = ExpiryCycle.get_numeric_features(d)
        for k, v in feats.items():
            expiry_cols[k].append(v)

    for k, vals in expiry_cols.items():
        df[k] = vals

    if hasattr(df.index, 'dayofweek'):
        df["dow_sin"] = np.sin(2 * np.pi * df.index.dayofweek / 5)
        df["dow_cos"] = np.cos(2 * np.pi * df.index.dayofweek / 5)

    return df
