"""
Risk fusion layer: combine deterministic and predictive scores into
a final risk score and tier.

Design principles:
  - alpha * deterministic + (1-alpha) * ML  for normal conditions.
  - Deterministic veto: if det_score > VETO_THRESHOLD, the final score
    is at least as high as the deterministic score.  Hard safety rules
    cannot be overridden by a benign ML prediction.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


ALPHA = 0.4
VETO_THRESHOLD = 0.8

TIER_THRESHOLDS: List[Tuple[float, str]] = [
    (0.8, "CRITICAL"),
    (0.6, "HIGH"),
    (0.3, "MEDIUM"),
    (0.0, "LOW"),
]

TIER_ACTIONS: Dict[str, List[str]] = {
    "LOW":      ["standard_monitoring"],
    "MEDIUM":   ["increase_monitoring_frequency", "pre_alert_ops"],
    "HIGH":     ["active_intervention", "notify_ops_team", "evaluate_rerouting"],
    "CRITICAL": ["immediate_action", "escalate_to_human", "initiate_cold_storage_backup",
                 "prepare_insurance_documentation"],
}

HUMAN_APPROVAL_TIERS = {"HIGH", "CRITICAL"}


def assign_tier(score: float) -> str:
    if score is None or (isinstance(score, float) and np.isnan(score)):
        return "MEDIUM"  # NaN = unknown risk; escalate, don't suppress
    for threshold, tier in TIER_THRESHOLDS:
        if score >= threshold:
            return tier
    return "LOW"


def fuse_scores(
    det_score: float,
    ml_score: float,
    alpha: float = ALPHA,
) -> Tuple[float, str, List[str], bool]:
    """
    Combine deterministic and ML scores.

    Returns
    -------
    final_score : float in [0, 1]
    tier : str
    actions : list of recommended action strings
    requires_human : bool
    """
    if np.isnan(det_score) and np.isnan(ml_score):
        final = 0.5  # both unknown -> assume elevated risk
    elif np.isnan(det_score):
        final = float(ml_score)
    elif np.isnan(ml_score):
        final = float(det_score)
    else:
        blended = alpha * det_score + (1.0 - alpha) * ml_score
        if det_score >= VETO_THRESHOLD:
            final = max(det_score, blended)
        else:
            final = blended

    final = float(np.clip(final, 0.0, 1.0))
    tier = assign_tier(final)
    actions = TIER_ACTIONS[tier]
    requires_human = tier in HUMAN_APPROVAL_TIERS

    return final, tier, actions, requires_human


def fuse_dataframe(
    df: pd.DataFrame,
    alpha: float = ALPHA,
) -> pd.DataFrame:
    """
    Vectorised fusion over a DataFrame that already contains
    `det_score` and `ml_score` columns.  Adds:
      final_score, risk_tier, recommended_actions, requires_human_approval.
    """
    df = df.copy()

    det = df["det_score"].values.astype(float)
    ml = df["ml_score"].values.astype(float)

    blended = alpha * det + (1.0 - alpha) * ml
    veto_mask = det >= VETO_THRESHOLD
    final = np.where(veto_mask, np.maximum(det, blended), blended)

    both_nan = np.isnan(det) & np.isnan(ml)
    det_nan = np.isnan(det) & ~np.isnan(ml)
    ml_nan = ~np.isnan(det) & np.isnan(ml)
    final = np.where(both_nan, 0.5, final)
    final = np.where(det_nan, ml, final)
    final = np.where(ml_nan, det, final)

    final = np.clip(final, 0.0, 1.0)

    df["final_score"] = final
    df["risk_tier"] = [assign_tier(s) for s in final]
    df["recommended_actions"] = [
        ";".join(TIER_ACTIONS[assign_tier(s)]) for s in final
    ]
    df["requires_human_approval"] = [
        assign_tier(s) in HUMAN_APPROVAL_TIERS for s in final
    ]
    return df
