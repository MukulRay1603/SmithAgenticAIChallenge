"""
Deterministic rule engine for cold-chain risk scoring.

Each rule evaluates a specific physical / compliance condition and returns
a sub-score in [0, 1].  The composite deterministic score is the clamped
sum of all fired sub-scores.

Rules are product-aware: temperature thresholds come from product_profiles.json.
Critical deterministic scores (>0.8) carry veto power in the fusion layer --
they cannot be reduced by a low ML prediction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


@dataclass
class RuleResult:
    rule_name: str
    fired: bool
    sub_score: float
    detail: str = ""


def _rule_temp_breach(row: pd.Series, profiles: Dict[str, dict]) -> RuleResult:
    """Temperature outside acceptable or critical product range."""
    prof = profiles[row["product_id"]]
    temp = row["avg_temp_c"]
    tl, th = prof["temp_low"], prof["temp_high"]
    cl, ch = prof["temp_critical_low"], prof["temp_critical_high"]

    if temp < cl or temp > ch:
        return RuleResult("temp_critical_breach", True, 0.60,
                          f"temp {temp:.1f}C outside critical [{cl}, {ch}]")
    if temp < tl or temp > th:
        return RuleResult("temp_warning_breach", True, 0.30,
                          f"temp {temp:.1f}C outside range [{tl}, {th}]")
    return RuleResult("temp_breach", False, 0.0)


def _rule_temp_trend(row: pd.Series, profiles: Dict[str, dict]) -> RuleResult:
    """
    Temperature slope heading toward a breach boundary.
    Fires when slope > 1.5 C/hr AND current temp is within 2C of a boundary.
    """
    prof = profiles[row["product_id"]]
    temp = row["avg_temp_c"]
    slope = row["temp_slope_c_per_hr"]
    tl, th = prof["temp_low"], prof["temp_high"]

    heading_high = slope > 1.0 and (th - temp) < 2.0
    heading_low = slope < -1.0 and (temp - tl) < 2.0

    if heading_high or heading_low:
        direction = "rising toward ceiling" if heading_high else "falling toward floor"
        score = min(abs(slope) / 3.0, 1.0) * 0.20
        return RuleResult("temp_trend_warning", True, round(score, 4),
                          f"slope {slope:+.2f}C/hr, {direction}")
    return RuleResult("temp_trend", False, 0.0)


def _rule_excursion_duration(row: pd.Series, profiles: Dict[str, dict]) -> RuleResult:
    """Cumulative minutes outside range exceeds product tolerance."""
    prof = profiles[row["product_id"]]
    cum = row.get("cumulative_breach_min", 0.0)
    threshold = prof["max_excursion_min"]

    if cum > threshold:
        ratio = min(cum / threshold, 3.0) / 3.0
        score = 0.15 + ratio * 0.15
        return RuleResult("excursion_duration", True, round(score, 4),
                          f"cumulative {cum:.0f} min > limit {threshold} min")
    return RuleResult("excursion_duration", False, 0.0)


def _rule_battery_critical(row: pd.Series, _profiles: Dict[str, dict]) -> RuleResult:
    """Sensor battery below critical level -- risk of monitoring loss."""
    batt = row["battery_avg_pct"]
    if batt < 15.0:
        return RuleResult("battery_critical", True, 0.15,
                          f"battery {batt:.1f}% < 15%")
    if batt < 25.0:
        return RuleResult("battery_low", True, 0.07,
                          f"battery {batt:.1f}% < 25%")
    return RuleResult("battery", False, 0.0)


def _rule_humidity(row: pd.Series, profiles: Dict[str, dict]) -> RuleResult:
    """Relative humidity above product threshold."""
    prof = profiles[row["product_id"]]
    hum = row["humidity_avg_pct"]
    limit = prof["humidity_max"]

    if hum > limit:
        return RuleResult("high_humidity", True, 0.10,
                          f"humidity {hum:.1f}% > {limit}%")
    return RuleResult("humidity", False, 0.0)


def _rule_delay_temp_stress(row: pd.Series, profiles: Dict[str, dict]) -> RuleResult:
    """
    Delay combined with temperature near breach boundary.
    A delay alone is not dangerous; it becomes risky when the cooling
    system is struggling (temp within 1C of boundary).
    """
    prof = profiles[row["product_id"]]
    delay = row["current_delay_min"]
    temp = row["avg_temp_c"]
    tl, th = prof["temp_low"], prof["temp_high"]

    near_boundary = (th - temp) < 1.0 or (temp - tl) < 1.0
    if delay > 120.0 and near_boundary:
        score = min(delay / 600.0, 1.0) * 0.25
        return RuleResult("delay_temp_stress", True, round(score, 4),
                          f"delay {delay:.0f}min + temp {temp:.1f}C near boundary")
    return RuleResult("delay_temp_stress", False, 0.0)


def _rule_shock_event(row: pd.Series, _profiles: Dict[str, dict]) -> RuleResult:
    """Any shock or door-open event in the window."""
    shocks = row.get("shock_count", 0)
    doors = row.get("door_open_count", 0)
    if shocks > 0 or doors > 0:
        score = min((shocks * 0.05 + doors * 0.03), 0.15)
        return RuleResult("handling_event", True, round(score, 4),
                          f"shocks={shocks}, door_opens={doors}")
    return RuleResult("handling_event", False, 0.0)


ALL_RULES = [
    _rule_temp_breach,
    _rule_temp_trend,
    _rule_excursion_duration,
    _rule_battery_critical,
    _rule_humidity,
    _rule_delay_temp_stress,
    _rule_shock_event,
]


def score_row(
    row: pd.Series,
    profiles: Dict[str, dict],
) -> Tuple[float, List[RuleResult]]:
    """
    Run all deterministic rules on a single window row.
    Returns (composite_score, list_of_rule_results).
    """
    results: List[RuleResult] = []
    total = 0.0
    for rule_fn in ALL_RULES:
        r = rule_fn(row, profiles)
        results.append(r)
        total += r.sub_score
    composite = float(np.clip(total, 0.0, 1.0))
    return composite, results


def score_dataframe(
    df: pd.DataFrame,
    profiles: Dict[str, dict],
) -> pd.DataFrame:
    """
    Vectorised deterministic scoring over an entire DataFrame.
    Adds columns: det_score, det_rules_fired (semicolon-separated names).
    """
    scores = []
    rules_fired = []

    for _, row in df.iterrows():
        s, results = score_row(row, profiles)
        scores.append(s)
        fired = [r.rule_name for r in results if r.fired]
        rules_fired.append(";".join(fired) if fired else "")

    df = df.copy()
    df["det_score"] = scores
    df["det_rules_fired"] = rules_fired
    return df
