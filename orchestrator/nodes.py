"""
Node functions for the orchestration agent.

Each node receives OrchestratorState and returns a partial dict to merge.
The deterministic logic follows the rules in system_prompt.md exactly.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from orchestrator.state import OrchestratorState, PlanStep, ToolResult
from tools import TOOL_MAP

logger = logging.getLogger(__name__)


# ── 1. Interpret risk ────────────────────────────────────────────────

def interpret_risk(state: OrchestratorState) -> dict:
    """Parse the risk engine output and classify severity."""
    ri = state["risk_input"]
    tier = ri.get("risk_tier", "LOW")
    score = ri.get("fused_risk_score", 0.0)
    rules = ri.get("deterministic_rule_flags", [])
    ml_prob = ri.get("ml_spoilage_probability", 0.0)

    if tier == "CRITICAL":
        severity = "critical"
        urgency = "immediate"
        primary = _identify_primary_issue(rules, score, ml_prob)
    elif tier == "HIGH":
        severity = "high"
        urgency = "urgent"
        primary = _identify_primary_issue(rules, score, ml_prob)
    elif tier == "MEDIUM":
        severity = "elevated"
        urgency = "monitor"
        primary = "Elevated risk metrics detected; preparing contingency."
    else:
        severity = "normal"
        urgency = "routine"
        primary = "All metrics within acceptable range."

    logger.info("INTERPRET  tier=%s severity=%s urgency=%s", tier, severity, urgency)
    return {
        "severity": severity,
        "urgency": urgency,
        "primary_issue": primary,
    }


def _identify_primary_issue(rules: list, score: float, ml_prob: float) -> str:
    if "temp_critical_breach" in rules:
        return "Temperature has breached critical limits. Product integrity at immediate risk."
    if "temp_warning_breach" in rules:
        return "Temperature outside acceptable range. Excursion in progress."
    if "excursion_duration" in rules:
        return "Cumulative excursion duration exceeds product tolerance."
    if "delay_temp_stress" in rules:
        return "Extended delay combined with temperature stress near boundary."
    if ml_prob > 0.8:
        return f"ML model predicts {ml_prob:.0%} spoilage probability within 6 hours."
    if "battery_critical" in rules:
        return "Sensor battery critical. Risk of monitoring loss."
    return f"Multiple risk signals detected (score={score:.3f})."


# ── 2. Plan ──────────────────────────────────────────────────────────

TIER_PLAN_TEMPLATES: Dict[str, List[Dict[str, str]]] = {
    "CRITICAL": [
        {"action": "Log compliance event for critical risk detection",
         "tool": "compliance_agent", "reason": "GDP/FDA requires immediate logging of critical excursions"},
        {"action": "Notify operations team and downstream stakeholders",
         "tool": "notification_agent", "reason": "Critical risk requires immediate stakeholder awareness"},
        {"action": "Evaluate reroute or backup cold-storage options",
         "tool": "cold_storage_agent", "reason": "Product integrity at risk; need temperature recovery"},
        {"action": "Submit plan for human approval before execution",
         "tool": "approval_workflow", "reason": "Critical actions are irreversible and require operator sign-off"},
    ],
    "HIGH": [
        {"action": "Log compliance event for high-risk detection",
         "tool": "compliance_agent", "reason": "Audit trail for elevated risk events"},
        {"action": "Send pre-alert to operations team",
         "tool": "notification_agent", "reason": "Ops team needs to prepare intervention options"},
        {"action": "Request human approval for recommended mitigation",
         "tool": "approval_workflow", "reason": "High-risk actions need operator confirmation"},
    ],
    "MEDIUM": [
        {"action": "Log monitoring event",
         "tool": "compliance_agent", "reason": "Traceability for elevated monitoring state"},
        {"action": "Send soft notification to ops dashboard",
         "tool": "notification_agent", "reason": "Situational awareness without escalation"},
    ],
    "LOW": [],
}


def plan(state: OrchestratorState) -> dict:
    """Generate a draft action plan based on risk tier and rules."""
    ri = state["risk_input"]
    tier = ri.get("risk_tier", "LOW")
    templates = TIER_PLAN_TEMPLATES.get(tier, [])

    draft: List[PlanStep] = []
    for i, tmpl in enumerate(templates, 1):
        tool_input = _build_tool_input(tmpl["tool"], ri, state)
        draft.append(PlanStep(
            step=i,
            action=tmpl["action"],
            tool=tmpl["tool"],
            tool_input=tool_input,
            reason=tmpl["reason"],
        ))

    if tier == "CRITICAL" and "excursion_duration" in ri.get("deterministic_rule_flags", []):
        draft.append(PlanStep(
            step=len(draft) + 1,
            action="Prepare insurance claim documentation",
            tool="insurance_agent",
            tool_input=_build_tool_input("insurance_agent", ri, state),
            reason="Excursion duration exceeded; potential product loss requires claim preparation",
        ))

    if tier in ("CRITICAL", "HIGH") and ri.get("transit_phase") in ("air_handoff", "customs_clearance"):
        draft.append(PlanStep(
            step=len(draft) + 1,
            action="Evaluate alternative routing options",
            tool="route_agent",
            tool_input=_build_tool_input("route_agent", ri, state),
            reason=f"Shipment at {ri.get('transit_phase')} with high risk; rerouting may recover ETA",
        ))

    logger.info("PLAN  %d steps for tier=%s", len(draft), tier)
    return {
        "draft_plan": draft,
        "plan_revised": False,
        "requires_approval": tier in ("CRITICAL", "HIGH"),
        "approval_reason": f"{tier} risk detected: {state.get('primary_issue', '')}",
    }


def _build_tool_input(tool_name: str, ri: dict, state: dict) -> dict:
    """Construct the tool-specific input payload from risk data."""
    base = {
        "shipment_id": ri.get("shipment_id", ""),
        "container_id": ri.get("container_id", ""),
    }
    if tool_name == "compliance_agent":
        return {
            **base,
            "window_id": ri.get("window_id", ""),
            "event_type": "risk_assessment",
            "risk_tier": ri.get("risk_tier", "LOW"),
            "details": {
                "fused_score": ri.get("fused_risk_score"),
                "ml_prob": ri.get("ml_spoilage_probability"),
                "rules": ri.get("deterministic_rule_flags", []),
                "primary_issue": state.get("primary_issue", ""),
            },
            "regulatory_tags": ["GDP", "FDA_21CFR11"],
        }
    if tool_name == "notification_agent":
        tier = ri.get("risk_tier", "LOW")
        recipients = ["ops_team"]
        if tier == "CRITICAL":
            recipients.extend(["management", "clinic"])
        return {
            **base,
            "risk_tier": tier,
            "recipients": recipients,
            "message": (
                f"[{tier}] Shipment {ri.get('shipment_id')} container {ri.get('container_id')}: "
                f"{state.get('primary_issue', 'Risk detected')}. "
                f"Score={ri.get('fused_risk_score', 0):.3f}, "
                f"Phase={ri.get('transit_phase', 'unknown')}."
            ),
            "channel": "dashboard",
        }
    if tool_name == "cold_storage_agent":
        return {
            **base,
            "product_id": ri.get("product_type", ""),
            "urgency": "critical" if ri.get("risk_tier") == "CRITICAL" else "high",
        }
    if tool_name == "route_agent":
        return {
            **base,
            "current_leg_id": ri.get("leg_id", ""),
            "reason": state.get("primary_issue", "Risk detected"),
        }
    if tool_name == "insurance_agent":
        return {
            **base,
            "product_id": ri.get("product_type", ""),
            "risk_tier": ri.get("risk_tier", ""),
            "incident_summary": state.get("primary_issue", ""),
        }
    if tool_name == "scheduling_agent":
        return {
            **base,
            "product_id": ri.get("product_type", ""),
            "affected_facilities": ["facility_TBD"],
            "original_eta": "TBD",
            "reason": state.get("primary_issue", ""),
        }
    if tool_name == "approval_workflow":
        active = state.get("draft_plan") or state.get("revised_plan") or []
        return {
            "shipment_id": ri.get("shipment_id", ""),
            "action_description": f"Execute mitigation plan ({len(active)} steps) for {ri.get('risk_tier')} risk",
            "risk_tier": ri.get("risk_tier", "LOW"),
            "urgency": state.get("urgency", "high"),
            "proposed_actions": [s.get("action", "") for s in active if isinstance(s, dict)],
            "justification": state.get("primary_issue", ""),
        }
    return base


# ── 3. Reflect (self-critique) ───────────────────────────────────────

REFLECTION_CHECKLIST = [
    ("compliance_covered", lambda plan: any(s["tool"] == "compliance_agent" for s in plan),
     "Plan missing compliance logging. Must add for audit trail."),
    ("notification_included", lambda plan: any(s["tool"] == "notification_agent" for s in plan),
     "Plan missing stakeholder notification."),
    ("approval_for_irreversible", lambda plan: any(s["tool"] == "approval_workflow" for s in plan),
     "Plan lacks human approval step for potentially irreversible actions."),
    ("has_fallback", lambda plan: len(plan) > 1,
     "Plan has only one step; should include fallback."),
    ("no_empty_steps", lambda plan: all(s.get("tool") in TOOL_MAP for s in plan),
     "Plan references a tool that does not exist."),
]


def reflect(state: OrchestratorState) -> dict:
    """Critique the draft plan against feasibility and compliance checklist."""
    tier = state["risk_input"].get("risk_tier", "LOW")
    if tier == "LOW":
        return {"reflection_notes": ["LOW risk: no action plan needed. Monitoring only."]}

    plan_to_check = state.get("draft_plan", [])
    notes: List[str] = []

    for check_name, check_fn, fix_note in REFLECTION_CHECKLIST:
        if tier in ("CRITICAL", "HIGH") and not check_fn(plan_to_check):
            notes.append(f"GAP [{check_name}]: {fix_note}")

    if not notes:
        notes.append("Plan passes all reflection checks. Ready for execution.")

    logger.info("REFLECT  %d notes", len(notes))
    return {"reflection_notes": notes}


# ── 4. Revise ────────────────────────────────────────────────────────

def revise(state: OrchestratorState) -> dict:
    """Patch the plan to fix gaps identified during reflection."""
    ri = state["risk_input"]
    revised = list(state.get("draft_plan", []))
    notes = state.get("reflection_notes", [])

    existing_tools = {s["tool"] for s in revised}

    for note in notes:
        if "compliance_covered" in note and "compliance_agent" not in existing_tools:
            revised.insert(0, PlanStep(
                step=0, action="Log compliance event (added by reflection)",
                tool="compliance_agent",
                tool_input=_build_tool_input("compliance_agent", ri, state),
                reason="Reflection gap: compliance logging was missing",
            ))
            existing_tools.add("compliance_agent")
        if "notification_included" in note and "notification_agent" not in existing_tools:
            revised.append(PlanStep(
                step=0, action="Send stakeholder notification (added by reflection)",
                tool="notification_agent",
                tool_input=_build_tool_input("notification_agent", ri, state),
                reason="Reflection gap: notification was missing",
            ))
            existing_tools.add("notification_agent")
        if "approval_for_irreversible" in note and "approval_workflow" not in existing_tools:
            revised.append(PlanStep(
                step=0, action="Request human approval (added by reflection)",
                tool="approval_workflow",
                tool_input=_build_tool_input("approval_workflow", ri, state),
                reason="Reflection gap: approval was missing for HIGH/CRITICAL action",
            ))
            existing_tools.add("approval_workflow")

    for i, step in enumerate(revised, 1):
        step["step"] = i

    logger.info("REVISE  %d steps (was %d)", len(revised), len(state.get("draft_plan", [])))
    return {"revised_plan": revised, "plan_revised": True, "active_plan": revised}


# ── 5. Execute ───────────────────────────────────────────────────────

def execute(state: OrchestratorState) -> dict:
    """Run each tool in the active plan sequentially."""
    active = state.get("active_plan") or state.get("draft_plan", [])
    results: List[ToolResult] = []
    errors: List[str] = []

    for step in active:
        tool_name = step["tool"]
        tool_input = step.get("tool_input", {})
        if tool_name not in TOOL_MAP:
            errors.append(f"Tool '{tool_name}' not available")
            continue
        try:
            tool = TOOL_MAP[tool_name]
            result = tool.invoke(tool_input)
            results.append(ToolResult(
                tool=tool_name, input=tool_input,
                result=result, success=True,
            ))
            if tool_name == "approval_workflow" and isinstance(result, dict):
                return {
                    "tool_results": results,
                    "execution_errors": errors,
                    "approval_id": result.get("approval_id"),
                }
        except Exception as exc:
            logger.error("EXECUTE  tool=%s failed: %s", tool_name, exc)
            errors.append(f"{tool_name}: {exc}")
            results.append(ToolResult(
                tool=tool_name, input=tool_input,
                result={"error": str(exc)}, success=False,
            ))

    logger.info("EXECUTE  %d tools run, %d errors", len(results), len(errors))
    return {"tool_results": results, "execution_errors": errors}


# ── 6. Build fallback ────────────────────────────────────────────────

def build_fallback(state: OrchestratorState) -> dict:
    """Create a minimal fallback plan in case primary plan fails."""
    ri = state["risk_input"]
    tier = ri.get("risk_tier", "LOW")
    if tier == "LOW":
        return {"fallback_plan": []}

    fallback = [
        PlanStep(step=1, action="Escalate to on-call operations manager",
                 tool="notification_agent",
                 tool_input=_build_tool_input("notification_agent", ri, state),
                 reason="Primary plan failed; manual intervention required"),
        PlanStep(step=2, action="Log escalation event for audit trail",
                 tool="compliance_agent",
                 tool_input=_build_tool_input("compliance_agent", ri, state),
                 reason="Compliance: all escalations must be logged"),
    ]
    return {"fallback_plan": fallback}


# ── 7. Compile output ────────────────────────────────────────────────

def compile_output(state: OrchestratorState) -> dict:
    """Assemble the final structured output matching system_prompt.md format."""
    ri = state["risk_input"]
    tier = ri.get("risk_tier", "LOW")

    tool_results = state.get("tool_results", [])
    errors = state.get("execution_errors", [])
    success_count = sum(1 for r in tool_results if r.get("success"))
    total_count = len(tool_results)

    if tier == "LOW":
        summary = "Monitoring only. All metrics within acceptable range."
        confidence = 0.95
    elif errors:
        summary = f"Partial execution: {success_count}/{total_count} tools succeeded. Manual review needed."
        confidence = 0.5
    else:
        summary = (
            f"Executed {total_count}-step mitigation plan for {tier} risk. "
            f"Primary issue: {state.get('primary_issue', 'N/A')}."
        )
        confidence = 0.85

    def _steps_to_dicts(steps):
        return [{"step": s["step"], "action": s["action"], "reason": s["reason"]}
                for s in (steps or [])]

    output = {
        "shipment_id": ri.get("shipment_id"),
        "container_id": ri.get("container_id"),
        "window_id": ri.get("window_id"),
        "leg_id": ri.get("leg_id"),
        "risk_tier": tier,
        "fused_risk_score": ri.get("fused_risk_score", 0),
        "ml_spoilage_probability": ri.get("ml_spoilage_probability", 0),
        "decision_summary": summary,
        "key_drivers": [d.get("feature", str(d)) for d in ri.get("key_drivers", [])],
        "draft_plan": _steps_to_dicts(state.get("draft_plan")),
        "reflection_notes": state.get("reflection_notes", []),
        "revised_plan": _steps_to_dicts(state.get("revised_plan")),
        "actions_taken": [
            {"tool": r["tool"], "input": r["input"], "result": r["result"]}
            for r in tool_results
        ],
        "fallback_plan": _steps_to_dicts(state.get("fallback_plan")),
        "requires_approval": state.get("requires_approval", False),
        "approval_reason": state.get("approval_reason", ""),
        "approval_id": state.get("approval_id"),
        "audit_log_summary": f"{total_count} tools executed, {len(errors)} errors, tier={tier}",
        "confidence": confidence,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    logger.info("OUTPUT  tier=%s confidence=%.2f tools=%d", tier, confidence, total_count)
    return {"final_output": output, "decision_summary": summary, "confidence": confidence}
