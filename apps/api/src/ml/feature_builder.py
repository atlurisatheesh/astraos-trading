"""AstraOS ML — Feature Builder.

Constructs a labelled feature matrix from raw OHLCV data + 60+ technical indicators.
Used to train the XGBoost signal predictor.

Features:
  - All 60+ technical indicators from quant.technical
  - Regime detector output
  - Volume profile metrics
  - Custom lag features (1d, 3d, 5d returns)

Labels:
  - BUY:  if future 5-day return > +1.5%
  - SELL: if future 5-day return < -1.5%
  - HOLD: otherwise
"""

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger()

LABEL_MAP = {"BUY": 2, "HOLD": 1, "SELL": 0}
LABEL_NAMES = {0: "SELL", 1: "HOLD", 2: "BUY"}


def build_features(
    df: pd.DataFrame,
    forward_days: int = 5,
    threshold: float = 1.5,
    include_labels: bool = True,
) -> pd.DataFrame:
    """Build feature matrix from OHLCV DataFrame.

    Args:
        df: OHLCV DataFrame (from yfinance, must have Open/High/Low/Close/Volume)
        forward_days: Days ahead to measure return for labeling
        threshold: Percentage threshold for BUY/SELL classification
        include_labels: If False, do not compute/trim labels (use for inference).

    Returns:
        If include_labels=True:
            DataFrame with indicator features + 'label' column (0=SELL, 1=HOLD, 2=BUY)
        If include_labels=False:
            DataFrame with only numeric indicator features (no label column)
    """
    from ..quant.technical import compute_all_indicators

    if df.empty or len(df) < 60:
        logger.warning("Insufficient data for feature building", rows=len(df))
        return pd.DataFrame()

    # Compute all technical indicators
    featured = compute_all_indicators(df)

    # ── Additional custom features ──

    close = featured["Close"]

    # Returns at various horizons
    featured["ret_1d"] = close.pct_change(1) * 100
    featured["ret_3d"] = close.pct_change(3) * 100
    featured["ret_5d"] = close.pct_change(5) * 100
    featured["ret_10d"] = close.pct_change(10) * 100
    featured["ret_20d"] = close.pct_change(20) * 100

    # Volatility features
    featured["vol_5d"] = close.pct_change().rolling(5).std() * np.sqrt(252) * 100
    featured["vol_20d"] = close.pct_change().rolling(20).std() * np.sqrt(252) * 100
    featured["vol_ratio"] = featured["vol_5d"] / (featured["vol_20d"] + 1e-10)

    # Volume features
    if "Volume" in featured.columns:
        featured["vol_sma_5"] = featured["Volume"].rolling(5).mean()
        featured["vol_sma_20"] = featured["Volume"].rolling(20).mean()
        featured["vol_ratio_5_20"] = featured["vol_sma_5"] / (featured["vol_sma_20"] + 1e-10)

    # Price position within Bollinger Bands
    if "BB_Upper" in featured.columns and "BB_Lower" in featured.columns:
        bb_width = featured["BB_Upper"] - featured["BB_Lower"]
        featured["bb_position"] = (close - featured["BB_Lower"]) / (bb_width + 1e-10)

    # Distance from key SMAs (%)
    for sma in ["SMA_20", "SMA_50", "SMA_200"]:
        if sma in featured.columns:
            featured[f"dist_{sma}"] = ((close - featured[sma]) / (featured[sma] + 1e-10)) * 100

    # Day of week (cyclical encoding)
    if hasattr(featured.index, 'dayofweek'):
        featured["day_sin"] = np.sin(2 * np.pi * featured.index.dayofweek / 5)
        featured["day_cos"] = np.cos(2 * np.pi * featured.index.dayofweek / 5)

    # ── Regime features (rolling windows, no look-ahead) ──────────────────
    # Rather than calling RegimeDetector once (which uses only the tail),
    # we compute rolling proxies so every row has a regime context.
    close_s = featured["Close"] if "Close" in featured.columns else None
    if close_s is not None:
        log_ret = np.log(close_s / close_s.shift(1))
        # Rolling 20-day annualised volatility as a regime proxy
        featured["regime_vol_20d"] = log_ret.rolling(20).std() * np.sqrt(252) * 100
        # Rolling 60-day trend strength (% gain from 60 bars ago)
        featured["regime_trend_60d"] = (
            (close_s - close_s.shift(60)) / (close_s.shift(60) + 1e-10) * 100
        )
        # Crisis flag: vol > 35% annualised
        featured["regime_crisis"] = (featured["regime_vol_20d"] > 35).astype(int)
        # Bull flag: trend > 3% AND vol < 20%
        featured["regime_bull"] = (
            (featured["regime_trend_60d"] > 3) & (featured["regime_vol_20d"] < 20)
        ).astype(int)
        # Bear flag: trend < -3%
        featured["regime_bear"] = (featured["regime_trend_60d"] < -3).astype(int)

    if include_labels:
        # ── Labels: future N-day return (no-trade / trade boundary) ──
        # Make the classification slightly more selective in high-volatility / crisis.
        # Effective threshold depends only on *past* regime proxies (no look-ahead).
        effective_threshold = threshold
        if "regime_crisis" in featured.columns:
            effective_threshold = np.where(featured["regime_crisis"].astype(bool), threshold * 1.5, threshold)

        future_return = close.shift(-forward_days) / close - 1
        future_return_pct = future_return * 100

        conditions = [
            future_return_pct > effective_threshold,   # BUY
            future_return_pct < -effective_threshold,  # SELL
        ]
        choices = [LABEL_MAP["BUY"], LABEL_MAP["SELL"]]
        featured["label"] = np.select(conditions, choices, default=LABEL_MAP["HOLD"])

        # Remove the last `forward_days` rows (no future data for labels)
        featured = featured.iloc[:-forward_days] if forward_days > 0 else featured

    # Select only numeric columns
    numeric_cols = featured.select_dtypes(include=[np.number]).columns.tolist()
    featured = featured[numeric_cols]

    # Drop raw OHLCV columns to prevent data leakage (keep only indicators)
    ohlcv_cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in featured.columns]
    featured = featured.drop(columns=ohlcv_cols, errors="ignore")

    # Handle NaN from indicator warmup periods (SMA_200 needs 200 days etc.)
    # Use forward-fill but do not back-fill to avoid look-ahead leakage.
    featured = featured.ffill()
    featured = featured.dropna()

    if len(featured) < 30:
        logger.warning("Too few rows after NaN handling", rows=len(featured))
        return pd.DataFrame()

    # ── Expiry cycle & day-of-week features ─────────────────────────────
    try:
        from ..quant.time_features import add_time_features_to_df
        featured = add_time_features_to_df(featured)
    except Exception as exc:
        logger.debug("Time features skipped", reason=str(exc))

    if include_labels and "label" in featured.columns:
        logger.info(
            "Features built",
            rows=len(featured),
            features=len(featured.columns) - 1,
            buy_pct=f"{(featured['label'] == 2).mean() * 100:.1f}%",
            sell_pct=f"{(featured['label'] == 0).mean() * 100:.1f}%",
            hold_pct=f"{(featured['label'] == 1).mean() * 100:.1f}%",
        )
    else:
        logger.info(
            "Features built (inference)",
            rows=len(featured),
            features=len(featured.columns),
        )

    return featured


def get_feature_columns(df: pd.DataFrame) -> list[str]:
    """Get list of feature columns (everything except 'label')."""
    return [c for c in df.columns if c != "label"]
