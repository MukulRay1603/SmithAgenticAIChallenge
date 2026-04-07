"""
Compliance logger: produces audit-ready JSON records for every
risk-scored telemetry window.

Each record contains the full decision trail: deterministic score,
rules that fired, ML probability, top SHAP features, fused score,
risk tier, recommended actions, and whether human approval is needed.

Records are written to a JSONL file (one JSON object per line)
for easy downstream ingestion and regulatory audit.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

LOG_DIR = Path(__file__).resolve().parent.parent / "audit_logs"


def build_audit_record(
    row: pd.Series,
    ml_top_features: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Build a single audit record from a fully-scored DataFrame row.

    Expected columns on row:
      window_id, shipment_id, container_id, product_id,
      det_score, det_rules_fired, ml_score,
      final_score, risk_tier, recommended_actions, requires_human_approval
    """
    rules_fired = row.get("det_rules_fired", "")
    if isinstance(rules_fired, str) and rules_fired:
        rules_list = rules_fired.split(";")
    else:
        rules_list = []

    actions = row.get("recommended_actions", "")
    if isinstance(actions, str) and actions:
        actions_list = actions.split(";")
    else:
        actions_list = []

    return {
        "assessment_timestamp": datetime.now(timezone.utc).isoformat(),
        "window_id": row["window_id"],
        "shipment_id": row["shipment_id"],
        "container_id": row["container_id"],
        "product_id": row["product_id"],
        "window_start": str(row.get("window_start", "")),
        "window_end": str(row.get("window_end", "")),
        "telemetry_snapshot": {
            "avg_temp_c": _safe_float(row.get("avg_temp_c")),
            "humidity_avg_pct": _safe_float(row.get("humidity_avg_pct")),
            "current_delay_min": _safe_float(row.get("current_delay_min")),
            "battery_avg_pct": _safe_float(row.get("battery_avg_pct")),
            "transit_phase": row.get("transit_phase", ""),
        },
        "deterministic_score": _safe_float(row.get("det_score")),
        "deterministic_rules_fired": rules_list,
        "ml_score": _safe_float(row.get("ml_score")),
        "ml_top_features": ml_top_features or [],
        "final_score": _safe_float(row.get("final_score")),
        "risk_tier": row.get("risk_tier", ""),
        "recommended_actions": actions_list,
        "requires_human_approval": bool(row.get("requires_human_approval", False)),
    }


def write_audit_log(
    df: pd.DataFrame,
    shap_explanations: Optional[List[List[Dict[str, Any]]]] = None,
    output_path: Optional[Path] = None,
) -> Path:
    """
    Write JSONL audit log for all rows in the scored DataFrame.
    Returns the path to the written file.
    """
    LOG_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = output_path or LOG_DIR / f"audit_{ts}.jsonl"

    records_written = 0
    with open(output_path, "w") as f:
        for idx, (_, row) in enumerate(df.iterrows()):
            ml_feats = shap_explanations[idx] if shap_explanations else None
            record = build_audit_record(row, ml_feats)
            f.write(json.dumps(record) + "\n")
            records_written += 1

    logger.info("Wrote %d audit records to %s", records_written, output_path)
    return output_path


def _safe_float(val: Any) -> Optional[float]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    return round(float(val), 4)
