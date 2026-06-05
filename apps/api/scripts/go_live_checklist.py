#!/usr/bin/env python3
"""AstraOS — Go-Live Safety Checklist.

Run this BEFORE enabling live trading. It checks every safety system
and refuses to approve live trading unless ALL checks pass.

Usage:
  cd D:\\stocks-monitoring\\apps\\api
  python scripts/go_live_checklist.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def check_model_exists() -> tuple[bool, str]:
    from src.core.config import ML_MODEL_DIR
    model_path = ML_MODEL_DIR / "signal_model.pkl"
    if model_path.exists():
        metrics_path = ML_MODEL_DIR / "training_metrics.json"
        if metrics_path.exists():
            with open(metrics_path) as f:
                m = json.load(f)
            return True, f"Model exists — accuracy {m.get('accuracy', '?')}%, trained on {len(m.get('symbols_trained', []))} stocks"
        return True, "Model exists but no metrics file"
    return False, "No trained model found. Run: python scripts/train_and_validate.py"


def check_model_quality() -> tuple[bool, str]:
    from src.core.config import ML_MODEL_DIR
    metrics_path = ML_MODEL_DIR / "training_metrics.json"
    if not metrics_path.exists():
        return False, "No training metrics"
    with open(metrics_path) as f:
        m = json.load(f)
    cv_acc = m.get("cv_accuracy_mean", 0) or 0
    hit_rate = m.get("trade_hit_rate_best_overall_pct", 0) or 0
    if cv_acc < 50:
        return False, f"CV accuracy {cv_acc}% < 50% — model has no edge"
    if hit_rate < 55:
        return False, f"Trade hit rate {hit_rate}% < 55% — signals not reliable enough"
    return True, f"CV accuracy {cv_acc}%, hit rate {hit_rate}%"


def check_validation_report() -> tuple[bool, str]:
    report_path = Path(__file__).parent.parent / "data" / "models" / "validation_report.json"
    if not report_path.exists():
        return False, "No validation report. Run: python scripts/train_and_validate.py"
    with open(report_path) as f:
        r = json.load(f)
    if r.get("all_passed"):
        return True, f"Validation passed on {r.get('timestamp', '?')}"
    return False, "Validation report shows FAIL — model needs improvement"


def check_env_security() -> tuple[bool, str]:
    from src.core.config import get_settings
    s = get_settings()
    issues = []
    if s.jwt_secret_key == "CHANGE_ME_TO_A_RANDOM_64_CHAR_STRING":
        issues.append("JWT_SECRET_KEY is still the default")
    if len(s.jwt_secret_key) < 32:
        issues.append("JWT_SECRET_KEY too short (< 32 chars)")
    if s.app_debug and s.app_env == "production":
        issues.append("APP_DEBUG is True in production")
    if not s.broker_encryption_key:
        issues.append("BROKER_ENCRYPTION_KEY not set (broker keys stored with JWT secret fallback)")
    if issues:
        return False, "; ".join(issues)
    return True, "Security config OK"


def check_broker_config() -> tuple[bool, str]:
    from src.core.config import get_settings
    s = get_settings()
    if s.broker_provider == "paper":
        return True, "Paper broker (safe). For live: set BROKER_PROVIDER=kite|angel|upstox"
    # If live broker, check credentials
    if s.broker_provider == "angel" and not getattr(s, "angel_api_key", ""):
        return False, "Angel One broker selected but ANGEL_API_KEY not set"
    return True, f"Broker: {s.broker_provider}"


def check_kill_switch() -> tuple[bool, str]:
    try:
        from src.risk.kill_switch import KillSwitch
        return True, "Kill switch module loaded OK"
    except Exception as e:
        return False, f"Kill switch import failed: {e}"


def check_circuit_breaker() -> tuple[bool, str]:
    try:
        from src.risk.circuit_breaker import circuit_breaker
        status = circuit_breaker.get_status()
        if status["trading_allowed"]:
            return True, f"Circuit breaker OK — mode: {status['mode']}"
        return False, f"Circuit breaker blocking — mode: {status['mode']}, triggers: {status.get('triggers', [])}"
    except Exception as e:
        return False, f"Circuit breaker failed: {e}"


def check_alerts_configured() -> tuple[bool, str]:
    from src.core.config import get_settings
    s = get_settings()
    channels = []
    if s.telegram_bot_token and s.telegram_chat_id:
        channels.append("Telegram")
    if s.smtp_user and s.smtp_password:
        channels.append("Email")
    if not channels:
        return False, "No alert channels configured. Set up Telegram or Email for trade notifications"
    return True, f"Alert channels: {', '.join(channels)}"


def check_realtime_data() -> tuple[bool, str]:
    from src.core.config import get_settings
    s = get_settings()
    if getattr(s, "angel_api_key", ""):
        return True, "Angel One SmartAPI configured (real-time)"
    if getattr(s, "kite_api_key", ""):
        return True, "Zerodha Kite Connect configured (real-time)"
    if s.market_data_provider == "yfinance":
        return False, "Using yfinance (15-min delayed). For live trading: configure Angel One or Kite Connect"
    return False, "No market data provider configured"


def main():
    print("=" * 70)
    print("  AstraOS — Go-Live Safety Checklist")
    print("  Every check must PASS before enabling live trading")
    print("=" * 70)
    print()

    checks = [
        ("Trained Model", check_model_exists),
        ("Model Quality", check_model_quality),
        ("Validation Report", check_validation_report),
        ("Environment Security", check_env_security),
        ("Broker Configuration", check_broker_config),
        ("Kill Switch", check_kill_switch),
        ("Circuit Breaker", check_circuit_breaker),
        ("Alert Channels", check_alerts_configured),
        ("Real-Time Data", check_realtime_data),
    ]

    results = []
    for name, check_fn in checks:
        try:
            passed, detail = check_fn()
        except Exception as e:
            passed, detail = False, f"Check crashed: {e}"
        results.append((name, passed, detail))
        icon = "PASS" if passed else "FAIL"
        print(f"  [{icon}] {name}")
        print(f"         {detail}")
        print()

    passed_count = sum(1 for _, p, _ in results if p)
    total = len(results)
    all_passed = passed_count == total

    print("=" * 70)
    print(f"  Score: {passed_count}/{total} checks passed")
    print()

    if all_passed:
        print("  ALL CHECKS PASSED")
        print()
        print("  You may proceed to live trading. FOLLOW THIS SEQUENCE:")
        print()
        print("  Week 1-2:  1 lot only,  Rs 1,00,000 capital")
        print("  Week 3-4:  2 lots,      Rs 2,00,000 capital")
        print("  Week 5-8:  5 lots,      Rs 5,00,000 capital")
        print("  Month 3+:  Full size,   scale based on Sharpe + drawdown")
        print()
        print("  NEVER go full size on day 1. NEVER.")
        print()
        print("  To enable live trading:")
        print("    1. Set BROKER_PROVIDER=angel (or kite/upstox) in .env")
        print("    2. Set broker credentials in .env")
        print("    3. Restart the server")
        print("    4. POST /api/v1/scheduler/auto-trade/enable")
    else:
        failed = [name for name, passed, _ in results if not passed]
        print(f"  {len(failed)} CHECKS FAILED: {', '.join(failed)}")
        print()
        print("  DO NOT enable live trading until all checks pass.")
        print("  Fix the issues above and run this script again.")

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
