"""
Tests for tools/route_agent.py

Author: Mukul Ray (Team Synapse, UMD Agentic AI Challenge 2026)
Covers: temp class classification, candidate option lookup, rule-based
urgency sort, approval gate, and LLM fallback to rule-based selection.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ── Temp class classification ─────────────────────────────────────────

def test_get_temp_class_frozen():
    from tools.route_agent import _get_temp_class
    with patch("tools.route_agent._load_profiles", return_value={"P_FROZEN": {"temp_high": -20}}):
        assert _get_temp_class("P_FROZEN") == "frozen"


def test_get_temp_class_refrigerated():
    from tools.route_agent import _get_temp_class
    with patch("tools.route_agent._load_profiles", return_value={"P_REF": {"temp_high": 8}}):
        assert _get_temp_class("P_REF") == "refrigerated"


def test_get_temp_class_crt():
    from tools.route_agent import _get_temp_class
    with patch("tools.route_agent._load_profiles", return_value={"P_CRT": {"temp_high": 25}}):
        assert _get_temp_class("P_CRT") == "crt"


def test_get_temp_class_unknown_product_defaults_refrigerated():
    from tools.route_agent import _get_temp_class
    with patch("tools.route_agent._load_profiles", return_value={}):
        assert _get_temp_class("UNKNOWN") == "refrigerated"


# ── Candidate options ─────────────────────────────────────────────────

def test_candidate_options_air_mode_returns_air_routes():
    from tools.route_agent import _candidate_options
    options = _candidate_options("refrigerated", "air")
    assert all("air" in route.lower() for route, _, _ in options)


def test_candidate_options_unknown_mode_falls_back_to_default():
    from tools.route_agent import _candidate_options
    default = _candidate_options("refrigerated", None)
    unknown = _candidate_options("refrigerated", "helicopter")
    assert default == unknown


def test_candidate_options_unknown_temp_class_falls_back_to_refrigerated():
    from tools.route_agent import _candidate_options
    ref = _candidate_options("refrigerated", None)
    unk = _candidate_options("nuclear", None)
    assert ref == unk


# ── Rule-based urgency sort ───────────────────────────────────────────

def test_rule_based_selects_fastest_eta_for_urgent_reason():
    from tools.route_agent import _select_route_rule_based
    result = _select_route_rule_based("refrigerated", "air", "CRITICAL excursion detected")
    # All air options have negative eta_change_hours; most negative = fastest
    assert result["eta_change_hours"] <= -2


def test_rule_based_non_urgent_reason_returns_first_candidate():
    from tools.route_agent import _select_route_rule_based, _candidate_options
    options = _candidate_options("refrigerated", "air")
    result = _select_route_rule_based("refrigerated", "air", "routine reroute")
    assert result["recommended_route"] == options[0][0]


# ── Approval gate ─────────────────────────────────────────────────────

def test_execute_always_sets_requires_approval():
    from tools.route_agent import _execute
    with patch("tools.route_agent._load_profiles", return_value={"P01": {"temp_high": 8}}), \
         patch("tools.route_agent._fetch_shipment_route", return_value=None), \
         patch("tools.route_agent.get_llm", return_value=None):
        result = _execute("SHP-001", "CNT-001", "LEG-001", "excursion", product_id="P01")
    assert result["requires_approval"] is True


# ── LLM fallback ──────────────────────────────────────────────────────

def test_execute_falls_back_to_rule_based_when_llm_unavailable():
    from tools.route_agent import _execute
    with patch("tools.route_agent._load_profiles", return_value={"P01": {"temp_high": 8}}), \
         patch("tools.route_agent._fetch_shipment_route", return_value=None), \
         patch("tools.route_agent.get_llm", return_value=None):
        result = _execute("SHP-001", "CNT-001", "LEG-001", "temperature breach", product_id="P01")
    assert result["selection_method"] == "rule_based"
    assert result["recommended_route"] != ""


def test_execute_uses_llm_method_when_llm_returns_valid_index():
    from tools.route_agent import _execute, _candidate_options
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content='{"selected_index": 0, "rationale": "fastest ETA"}')
    with patch("tools.route_agent._load_profiles", return_value={"P01": {"temp_high": 8}}), \
         patch("tools.route_agent._fetch_shipment_route", return_value=None), \
         patch("tools.route_agent.get_llm", return_value=mock_llm):
        result = _execute("SHP-001", "CNT-001", "LEG-001", "excursion", product_id="P01")
    assert result["selection_method"] == "llm"
