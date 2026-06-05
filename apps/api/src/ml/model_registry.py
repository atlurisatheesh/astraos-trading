# type: ignore
"""AstraOS ML — Model Registry.

Version-controlled model storage with accuracy tracking,
automatic promotion, and rollback support.

Each trained model is stored as a versioned artifact:
  data/models/v{N}_signal_model.pkl
  data/models/v{N}_metrics.json
  data/models/active_model.json  ← pointer to current best
"""

import json
import shutil
import pickle
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import structlog

logger = structlog.get_logger()

IST = ZoneInfo("Asia/Kolkata")

from ..core.config import ML_MODEL_DIR  # noqa: E402
MODEL_DIR = ML_MODEL_DIR

ACTIVE_POINTER = MODEL_DIR / "active_model.json"
CURRENT_MODEL = MODEL_DIR / "signal_model.pkl"
CURRENT_METRICS = MODEL_DIR / "training_metrics.json"


def get_next_version() -> int:
    """Determine the next model version number."""
    existing = list(MODEL_DIR.glob("v*_signal_model.pkl"))
    if not existing:
        return 1
    versions = []
    for p in existing:
        try:
            v = int(p.stem.split("_")[0].replace("v", ""))
            versions.append(v)
        except ValueError:
            continue
    return max(versions) + 1 if versions else 1


def register_model(model_path: Path, metrics: dict) -> dict:
    """Register a newly trained model in the registry.
    
    Compares with the currently active model — only promotes
    the new model if its accuracy is higher.
    
    Returns registration result with version and promotion status.
    """
    version = get_next_version()
    
    # Copy model to versioned path
    versioned_model = MODEL_DIR / f"v{version}_signal_model.pkl"
    versioned_metrics = MODEL_DIR / f"v{version}_metrics.json"
    
    shutil.copy2(model_path, versioned_model)
    
    metrics["version"] = version
    metrics["registered_at"] = datetime.now(IST).isoformat()
    
    with open(versioned_metrics, "w") as f:
        json.dump(metrics, f, indent=2)
    
    # Decide whether to promote
    active = get_active_model_info()
    should_promote = True
    promotion_reason = "First model registered"
    
    if active and "accuracy" in active:
        old_acc = active.get("accuracy", 0)
        new_acc = metrics.get("accuracy", 0)

        # Practical trading metric: accuracy on high-confidence BUY/SELL calls.
        old_hit = float(active.get("trade_hit_rate_best_overall_pct", old_acc) or 0)
        new_hit = float(metrics.get("trade_hit_rate_best_overall_pct", 0) or 0)

        # Promotion priority:
        # 1) If hit-rate on actionable trades improves, promote even if overall
        #    multiclass accuracy is similar.
        # 2) Otherwise fall back to multiclass accuracy.
        if new_hit > old_hit + 0.5:
            promotion_reason = (
                f"Trade hit-rate improved: {old_hit}% -> {new_hit}% "
                f"(accuracy {old_acc}% -> {new_acc}%)"
            )
        elif new_acc > old_acc:
            promotion_reason = f"Accuracy improved: {old_acc}% -> {new_acc}%"
        elif new_acc == old_acc and new_hit > old_hit:
            promotion_reason = f"Accuracy unchanged but hit-rate improved: {old_hit}% -> {new_hit}%"
        elif new_acc == old_acc:
            promotion_reason = f"Accuracy unchanged ({new_acc}%), keeping new model (fresher data)"
        else:
            should_promote = False
            promotion_reason = (
                f"New model worse for promotion: "
                f"accuracy {new_acc}% < {old_acc}% and hit-rate {new_hit}% <= {old_hit}% "
                f"- keeping v{active.get('version', '?')}"
            )
    
    if should_promote:
        promote_model(version)
    
    result = {
        "version": version,
        "accuracy": metrics.get("accuracy", 0),
        "promoted": should_promote,
        "promotion_reason": promotion_reason,
        "model_path": str(versioned_model),
    }
    
    logger.info("Model registered", **result)
    return result


def promote_model(version: int) -> bool:
    """Promote a specific model version to be the active model."""
    versioned_model = MODEL_DIR / f"v{version}_signal_model.pkl"
    versioned_metrics = MODEL_DIR / f"v{version}_metrics.json"
    
    if not versioned_model.exists():
        logger.error("Cannot promote — model not found", version=version)
        return False
    
    # Copy to active slot
    shutil.copy2(versioned_model, CURRENT_MODEL)
    if versioned_metrics.exists():
        shutil.copy2(versioned_metrics, CURRENT_METRICS)
    
    # Update pointer
    with open(versioned_metrics) as f:
        metrics = json.load(f)
    
    pointer = {
        "active_version": version,
        "accuracy": metrics.get("accuracy", 0),
        "promoted_at": datetime.now(IST).isoformat(),
        "model_path": str(versioned_model),
    }
    
    with open(ACTIVE_POINTER, "w") as f:
        json.dump(pointer, f, indent=2)
    
    # Invalidate predictor cache
    try:
        from .predictor import invalidate_model_cache
        invalidate_model_cache()
    except Exception:
        pass
    
    logger.info("Model promoted", version=version)
    return True


def rollback_model(version: int) -> dict:
    """Rollback to a previous model version."""
    if promote_model(version):
        return {"status": "rolled_back", "active_version": version}
    return {"status": "failed", "error": f"Version {version} not found"}


def get_active_model_info() -> dict | None:
    """Get info about the currently active model."""
    if not ACTIVE_POINTER.exists():
        # Check if there's a legacy model without registry
        if CURRENT_METRICS.exists():
            with open(CURRENT_METRICS) as f:
                return json.load(f)
        return None
    
    with open(ACTIVE_POINTER) as f:
        return json.load(f)


def list_models() -> list[dict]:
    """List all registered model versions with their metrics."""
    models = []
    active = get_active_model_info()
    active_version = active.get("active_version") if active else None
    
    for metrics_file in sorted(MODEL_DIR.glob("v*_metrics.json")):
        try:
            with open(metrics_file) as f:
                m = json.load(f)
            m["is_active"] = m.get("version") == active_version
            models.append(m)
        except Exception:
            continue
    
    return models
