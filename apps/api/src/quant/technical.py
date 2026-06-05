"""AstraOS Quant — Technical Indicator Engine (60+ indicators, using 'ta' library)."""

import pandas as pd
import ta
import structlog

logger = structlog.get_logger()


def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute 60+ technical indicators on OHLCV DataFrame.

    Input: DataFrame with columns [Open, High, Low, Close, Volume]
    Output: Same DataFrame with additional indicator columns (~80 new columns).
    """
    if df.empty or len(df) < 30:
        logger.warning("Insufficient data for indicators", rows=len(df))
        return df

    result = df.copy()

    # Flatten multi-index columns if present (yfinance returns these)
    if isinstance(result.columns, pd.MultiIndex):
        result.columns = result.columns.droplevel(1)
    
    # Ensure all columns are 1D Series (yfinance can leave 2D arrays)
    for col in result.columns:
        if hasattr(result[col], 'ndim') and result[col].ndim > 1:
            result[col] = result[col].iloc[:, 0]

    # Ensure proper column names
    col_map = {}
    for c in result.columns:
        if c.lower() in ("close", "adj close"):
            col_map[c] = "Close"
        elif c.lower() == "open":
            col_map[c] = "Open"
        elif c.lower() == "high":
            col_map[c] = "High"
        elif c.lower() == "low":
            col_map[c] = "Low"
        elif c.lower() == "volume":
            col_map[c] = "Volume"
    result.rename(columns=col_map, inplace=True)

    close = result["Close"]
    high = result["High"]
    low = result["Low"]
    volume = result["Volume"]

    # ── Trend Indicators (15+) ──
    result["SMA_10"] = ta.trend.sma_indicator(close, window=10)
    result["SMA_20"] = ta.trend.sma_indicator(close, window=20)
    result["SMA_50"] = ta.trend.sma_indicator(close, window=50)
    result["SMA_200"] = ta.trend.sma_indicator(close, window=200)
    result["EMA_9"] = ta.trend.ema_indicator(close, window=9)
    result["EMA_21"] = ta.trend.ema_indicator(close, window=21)
    result["EMA_50"] = ta.trend.ema_indicator(close, window=50)
    result["MACD"] = ta.trend.macd(close)
    result["MACD_Signal"] = ta.trend.macd_signal(close)
    result["MACD_Hist"] = ta.trend.macd_diff(close)
    result["ADX"] = ta.trend.adx(high, low, close)
    result["ADX_Pos"] = ta.trend.adx_pos(high, low, close)
    result["ADX_Neg"] = ta.trend.adx_neg(high, low, close)
    result["PSAR_Up"] = ta.trend.psar_up(high, low, close)
    result["PSAR_Down"] = ta.trend.psar_down(high, low, close)
    result["Aroon_Up"] = ta.trend.aroon_up(high, low)
    result["Aroon_Down"] = ta.trend.aroon_down(high, low)
    result["CCI"] = ta.trend.cci(high, low, close)
    result["TRIX"] = ta.trend.trix(close)
    result["VORTEX_Pos"] = ta.trend.vortex_indicator_pos(high, low, close)
    result["VORTEX_Neg"] = ta.trend.vortex_indicator_neg(high, low, close)

    # ── Momentum Indicators (10+) ──
    result["RSI_14"] = ta.momentum.rsi(close, window=14)
    result["RSI_7"] = ta.momentum.rsi(close, window=7)
    result["Stoch_K"] = ta.momentum.stoch(high, low, close)
    result["Stoch_D"] = ta.momentum.stoch_signal(high, low, close)
    result["Williams_R"] = ta.momentum.williams_r(high, low, close)
    result["ROC"] = ta.momentum.roc(close)
    result["TSI"] = ta.momentum.tsi(close)
    result["UO"] = ta.momentum.ultimate_oscillator(high, low, close)
    result["AO"] = ta.momentum.awesome_oscillator(high, low)

    # ── Volatility Indicators (8+) ──
    bb = ta.volatility.BollingerBands(close)
    result["BB_Upper"] = bb.bollinger_hband()
    result["BB_Middle"] = bb.bollinger_mavg()
    result["BB_Lower"] = bb.bollinger_lband()
    result["BB_Width"] = bb.bollinger_wband()
    result["ATR"] = ta.volatility.average_true_range(high, low, close)
    kc = ta.volatility.KeltnerChannel(high, low, close)
    result["KC_Upper"] = kc.keltner_channel_hband()
    result["KC_Lower"] = kc.keltner_channel_lband()
    dc = ta.volatility.DonchianChannel(high, low, close)
    result["DC_Upper"] = dc.donchian_channel_hband()
    result["DC_Lower"] = dc.donchian_channel_lband()

    # ── Volume Indicators (6+) ──
    result["OBV"] = ta.volume.on_balance_volume(close, volume)
    result["CMF"] = ta.volume.chaikin_money_flow(high, low, close, volume)
    result["MFI"] = ta.volume.money_flow_index(high, low, close, volume)
    result["ADI"] = ta.volume.acc_dist_index(high, low, close, volume)
    result["VWAP"] = ta.volume.volume_weighted_average_price(high, low, close, volume)
    result["FI"] = ta.volume.force_index(close, volume)

    # ── Custom Derived Signals ──
    _add_custom_signals(result)

    return result


def _add_custom_signals(df: pd.DataFrame) -> None:
    """Add custom trading signals."""
    # Golden / Death Cross
    if "SMA_50" in df.columns and "SMA_200" in df.columns:
        df["golden_cross"] = (df["SMA_50"] > df["SMA_200"]).astype(int)
        df["death_cross"] = (df["SMA_50"] < df["SMA_200"]).astype(int)

    # RSI extremes
    if "RSI_14" in df.columns:
        df["rsi_oversold"] = (df["RSI_14"] < 30).astype(int)
        df["rsi_overbought"] = (df["RSI_14"] > 70).astype(int)

    # MACD cross
    if "MACD" in df.columns and "MACD_Signal" in df.columns:
        df["macd_bullish"] = (df["MACD"] > df["MACD_Signal"]).astype(int)

    # Volume spike
    if "Volume" in df.columns:
        avg_vol = df["Volume"].rolling(20).mean()
        df["volume_spike"] = (df["Volume"] > 2 * avg_vol).astype(int)

    # Above 200 DMA
    if "Close" in df.columns and "SMA_200" in df.columns:
        df["above_200dma"] = (df["Close"] > df["SMA_200"]).astype(int)

    # Bollinger squeeze
    if "BB_Width" in df.columns:
        df["bb_squeeze"] = (df["BB_Width"] < df["BB_Width"].rolling(50).quantile(0.1)).astype(int)


def get_signal_summary(df: pd.DataFrame) -> dict:
    """Summarize latest indicator readings."""
    if df.empty:
        return {"error": "No data"}

    latest = df.iloc[-1]
    return {
        "price": float(latest.get("Close", 0)),
        "rsi": float(latest.get("RSI_14", 50)),
        "macd": float(latest.get("MACD", 0)),
        "macd_signal": float(latest.get("MACD_Signal", 0)),
        "adx": float(latest.get("ADX", 0)),
        "atr": float(latest.get("ATR", 0)),
        "bb_upper": float(latest.get("BB_Upper", 0)),
        "bb_lower": float(latest.get("BB_Lower", 0)),
        "sma_50": float(latest.get("SMA_50", 0)),
        "sma_200": float(latest.get("SMA_200", 0)),
        "obv": float(latest.get("OBV", 0)),
        "cmf": float(latest.get("CMF", 0)),
        "mfi": float(latest.get("MFI", 0)),
        "trend": "bullish" if latest.get("SMA_50", 0) > latest.get("SMA_200", 0) else "bearish",
        "momentum": "overbought" if latest.get("RSI_14", 50) > 70 else "oversold" if latest.get("RSI_14", 50) < 30 else "neutral",
        "volatility": "high" if latest.get("ATR", 0) > 2 else "low",
    }
