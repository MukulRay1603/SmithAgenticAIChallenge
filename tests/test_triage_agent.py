"""
Tests for tools/triage_agent.py

Author: Mukul Ray (Team Synapse, UMD Agentic AI Challenge 2026)
Covers: tier sort order, score tiebreaker within tier, recommended_orchestration_order
filtering, enrich flag bypass, and empty list handling.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


# ── Tier sort order ───────────────────────────────────────────────────

def test_critical_ranked_before_high():
    from tools.triage_agent import _execute
    shipments = [
        {"shipment_id": "S1", "risk_tier": "HIGH", "fused_risk_score": 0.9, "product_id": "P01"},
        {"shipment_id": "S2", "risk_tier": "CRITICAL", "fused_risk_score": 0.7, "product_id": "P01"},
    ]
    result = _execute(shipments, enrich=False)
    assert result["priority_list"][0]["shipment_id"] == "S2"
    assert result["priority_list"][0]["risk_tier"] == "CRITICAL"


def test_all_tiers_sorted_correctly():
    from tools.triage_agent import _execute
    shipments = [
        {"shipment_id": "S_LOW",    "risk_tier": "LOW",      "fused_risk_score": 0.1, "product_id": "P01"},
        {"shipment_id": "S_MEDIUM", "risk_tier": "MEDIUM",   "fused_risk_score": 0.4, "product_id": "P01"},
        {"shipment_id": "S_HIGH",   "risk_tier": "HIGH",     "fused_risk_score": 0.7, "product_id": "P01"},
        {"shipment_id": "S_CRIT",   "risk_tier": "CRITICAL", "fused_risk_score": 0.9, "product_id": "P01"},
    ]
    result = _execute(shipments, enrich=False)
    tiers = [item["risk_tier"] for item in result["priority_list"]]
    assert tiers == ["CRITICAL", "HIGH", "MEDIUM", "LOW"]


# ── Score tiebreaker within tier ──────────────────────────────────────

def test_higher_score_ranks_first_within_same_tier():
    from tools.triage_agent import _execute
    shipments = [
        {"shipment_id": "S_LOW_SCORE", "risk_tier": "HIGH", "fused_risk_score": 0.61, "product_id": "P01"},
        {"shipment_id": "S_HIGH_SCORE","risk_tier": "HIGH", "fused_risk_score": 0.89, "product_id": "P01"},
    ]
    result = _execute(shipments, enrich=False)
    assert result["priority_list"][0]["shipment_id"] == "S_HIGH_SCORE"


# ── recommended_orchestration_order ──────────────────────────────────

def test_orchestration_order_contains_only_critical_and_high():
    from tools.triage_agent import _execute
    shipments = [
        {"shipment_id": "S_CRIT",   "risk_tier": "CRITICAL", "fused_risk_score": 0.95, "product_id": "P01"},
        {"shipment_id": "S_HIGH",   "risk_tier": "HIGH",     "fused_risk_score": 0.70, "product_id": "P01"},
        {"shipment_id": "S_MEDIUM", "risk_tier": "MEDIUM",   "fused_risk_score": 0.40, "product_id": "P01"},
        {"shipment_id": "S_LOW",    "risk_tier": "LOW",      "fused_risk_score": 0.10, "product_id": "P01"},
    ]
    result = _execute(shipments, enrich=False)
    order = result["recommended_orchestration_order"]
    assert "S_CRIT" in order
    assert "S_HIGH" in order
    assert "S_MEDIUM" not in order
    assert "S_LOW" not in order


def test_counts_match_tiers():
    from tools.triage_agent import _execute
    shipments = [
        {"shipment_id": "S1", "risk_tier": "CRITICAL", "fused_risk_score": 0.9, "product_id": "P01"},
        {"shipment_id": "S2", "risk_tier": "CRITICAL", "fused_risk_score": 0.85, "product_id": "P01"},
        {"shipment_id": "S3", "risk_tier": "HIGH",     "fused_risk_score": 0.65, "product_id": "P01"},
    ]
    result = _execute(shipments, enrich=False)
    assert result["critical_count"] == 2
    assert result["high_count"] == 1
    assert result["shipments_requiring_action"] == 3


# ── enrich=False bypasses scored_windows.csv ─────────────────────────

def test_enrich_false_does_not_call_scored_csv(tmp_path):
    from tools.triage_agent import _execute
    shipments = [
        {"shipment_id": "S1", "risk_tier": "HIGH", "fused_risk_score": 0.75, "product_id": "P01"},
    ]
    with patch("tools.triage_agent._SCORED_CSV", tmp_path / "nonexistent.csv"):
        result = _execute(shipments, enrich=False)
    assert result["status"] == "ranked"
    assert result["priority_list"][0]["hours_at_risk"] is None


# ── Empty list handling ───────────────────────────────────────────────

def test_empty_shipment_list_returns_zero_counts():
    from tools.triage_agent import _execute
    result = _execute([], enrich=False)
    assert result["total_shipments"] == 0
    assert result["critical_count"] == 0
    assert result["recommended_orchestration_order"] == []
