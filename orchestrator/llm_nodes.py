"""
LLM-powered agentic nodes for the orchestration graph.

These are TRUE agentic nodes: the LLM reasons about the situation, decides
which tools to call, AND constructs the tool input payloads itself.

The deterministic _build_tool_input() is only used as a safety net when the
LLM produces malformed inputs -- it does NOT drive the agent's decisions.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List

from orchestrator.llm_provider import get_llm
from orchestrator.state import OrchestratorState, PlanStep, ToolResult
from tools import TOOL_MAP

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response that may contain markdown fences."""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Find balanced outermost braces instead of greedy first-to-last match
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    start = -1
    return {}


TOOL_SCHEMAS = {}
for _name, _tool in TOOL_MAP.items():
    schema = _tool.args_schema.model_json_schema() if _tool.args_schema else {}
    props = schema.get("properties", {})
    required = schema.get("required", [])
    req_fields = [f for f in required if f in props]
    fields = []
    for fname in req_fields:
        finfo = props[fname]
        ftype = finfo.get("type", "string")
        fields.append(f"{fname}:{ftype}")
    TOOL_SCHEMAS[_name] = f"  {_name}({', '.join(fields)})"

TOOLS_REFERENCE = "\n".join(TOOL_SCHEMAS.values())


# ── Agentic Plan ─────────────────────────────────────────────────────

PLAN_SYSTEM = """You are an expert pharmaceutical cold-chain orchestration agent. You make autonomous decisions about shipment interventions based on GDP (Good Distribution Practice), FDA 21 CFR Part 211, and WHO PQS guidelines.

DOMAIN KNOWLEDGE:
- Temperature excursions degrade biologics exponentially, not linearly. A 2°C overshoot for 60 min is NOT equivalent to 1°C for 120 min.
- Cumulative excursion budget (related to Mean Kinetic Temperature) is the key metric. Once exceeded, product is suspect regardless of current temperature.
- Frozen products (-20°C) can tolerate brief warming but NEVER refreezing. Refrigerated products (2-8°C) can tolerate brief 0-12°C excursions.
- Delay + temperature stress is a compound risk: cooling systems degrade under extended operation, making breach more likely over time.
- Compliance logging MUST happen BEFORE any intervention (audit trail integrity per GDP Chapter 9).
- Downstream healthcare facilities need advance notice for appointment rescheduling -- patient impact is the ultimate consequence.

DECISION RULES:
- CRITICAL: compliance_agent FIRST (audit trail), then cold_storage_agent (temp recovery), notification_agent (stakeholder alert), insurance_agent (financial protection), scheduling_agent (patient impact), approval_workflow LAST (human sign-off on irreversible actions).
- HIGH: compliance_agent FIRST, notification_agent, scheduling_agent if delay_class is developing/critical, approval_workflow LAST.
- MEDIUM: compliance_agent, notification_agent. No approval needed.
- LOW: empty steps. Monitoring only.
- Construct tool inputs using the actual shipment data. Do NOT use placeholder values.
- Return ONLY valid JSON."""


def plan_llm(state: OrchestratorState) -> dict:
    """LLM agent generates plan with tool names AND tool input payloads."""
    llm = get_llm()
    if llm is None:
        from orchestrator.nodes import plan as det_plan
        return det_plan(state)

    ri = state["risk_input"]

    facility = ri.get("facility", {})
    cost = ri.get("product_cost", {})
    context_block = f"""
  delay_class: {ri.get('delay_class', 'unknown')}
  delay_ratio: {ri.get('delay_ratio', 'N/A')}
  hours_to_breach: {ri.get('hours_to_breach', 'N/A')}
  current_delay_min: {ri.get('current_delay_min', 0)}
  facility_name: {facility.get('name', 'unknown')}
  facility_location: {facility.get('location', 'unknown')}
  shipment_value_usd: {cost.get('shipment_value_usd', 'N/A')}
  product_name: {cost.get('product_name', ri.get('product_type', ''))}"""

    # Derive domain context the LLM needs to reason about
    delay_class = ri.get('delay_class', 'unknown')
    hours_breach = ri.get('hours_to_breach')
    breach_urgency = "ALREADY BREACHED" if hours_breach == 0.0 else (
        f"~{hours_breach:.1f}h until breach" if hours_breach else "stable"
    )
    spoilage = ri.get('ml_spoilage_probability', 0)
    spoilage_risk = "very high (>80%)" if spoilage > 0.8 else (
        "high (>50%)" if spoilage > 0.5 else "moderate" if spoilage > 0.2 else "low"
    )

    user_msg = f"""Analyze this risk event and create an action plan.

RISK EVENT:
  shipment_id: {ri.get('shipment_id')}
  container_id: {ri.get('container_id')}
  window_id: {ri.get('window_id')}
  leg_id: {ri.get('leg_id')}
  product_type: {ri.get('product_type')}
  transit_phase: {ri.get('transit_phase')}
  risk_tier: {ri.get('risk_tier')}
  fused_risk_score: {ri.get('fused_risk_score')}
  ml_spoilage_probability: {spoilage} ({spoilage_risk})
  deterministic_rule_flags: {ri.get('deterministic_rule_flags', [])}
  severity: {state.get('severity', 'unknown')}
  primary_issue: {state.get('primary_issue', '')}
{context_block}

DOMAIN ANALYSIS:
  excursion_budget_status: {delay_class} (delay_ratio={ri.get('delay_ratio', 'N/A')})
  breach_timeline: {breach_urgency}
  compound_risk: {"YES - delay + temperature stress" if 'delay_temp_stress' in ri.get('deterministic_rule_flags', []) else "no compound risk detected"}

AVAILABLE TOOLS (with input schemas):
{TOOLS_REFERENCE}

Respond with ONLY this JSON:
{{
  "reasoning": "2-3 sentences analyzing what this specific situation needs based on the domain context",
  "steps": [
    {{
      "step": 1,
      "action": "what this step does",
      "tool": "tool_name",
      "tool_input": {{...actual input fields for this tool...}},
      "reason": "why this step is needed"
    }}
  ],
  "requires_approval": true,
  "approval_reason": "why"
}}

Construct real tool_input values using the risk event data. Use actual shipment_id, container_id, etc."""

    try:
        response = llm.invoke([
            {"role": "system", "content": PLAN_SYSTEM},
            {"role": "user", "content": user_msg},
        ])
        parsed = _extract_json(response.content)

        if not parsed or "steps" not in parsed:
            logger.warning("AGENT_PLAN: unparseable LLM response, falling back")
            from orchestrator.nodes import plan as det_plan
            return det_plan(state)

        draft: List[PlanStep] = []
        seen_tools: set = set()
        for s in parsed["steps"]:
            tool_name = s.get("tool", "")
            if tool_name not in TOOL_MAP:
                logger.warning("AGENT_PLAN: unknown tool '%s', skipping", tool_name)
                continue
            if tool_name in seen_tools:
                logger.debug("AGENT_PLAN: skipping duplicate %s", tool_name)
                continue
            seen_tools.add(tool_name)

            llm_input = s.get("tool_input", {})
            if not isinstance(llm_input, dict) or not llm_input:
                from orchestrator.nodes import _build_tool_input
                llm_input = _build_tool_input(tool_name, ri, state)
                logger.debug("AGENT_PLAN: empty tool_input for %s, used fallback builder", tool_name)

            draft.append(PlanStep(
                step=len(draft) + 1,
                action=s.get("action", f"Execute {tool_name}"),
                tool=tool_name,
                tool_input=llm_input,
                reason=s.get("reason", ""),
            ))

        if not draft and ri.get("risk_tier") not in ("LOW", None):
            logger.warning("AGENT_PLAN: LLM returned 0 valid steps for %s tier, falling back",
                           ri.get("risk_tier"))
            from orchestrator.nodes import plan as det_plan
            return det_plan(state)

        reasoning = parsed.get("reasoning", "")
        requires_approval = parsed.get("requires_approval",
                                        ri.get("risk_tier") in ("CRITICAL", "HIGH"))

        logger.info("AGENT_PLAN: %d steps, reasoning=%s", len(draft), reasoning[:80])
        return {
            "draft_plan": draft,
            "plan_revised": False,
            "requires_approval": requires_approval,
            "approval_reason": parsed.get("approval_reason", state.get("primary_issue", "")),
            "llm_reasoning": reasoning,
        }

    except Exception as exc:
        logger.error("AGENT_PLAN failed (%s), falling back to deterministic", exc)
        from orchestrator.nodes import plan as det_plan
        return det_plan(state)


# ── Agentic Reflect ──────────────────────────────────────────────────

REFLECT_SYSTEM = """You are a GDP/FDA compliance auditor for pharmaceutical cold-chain logistics.
You review action plans against regulatory requirements. Be specific and cite the regulation.

KEY COMPLIANCE CHECKS:
- GDP Ch 9: Every risk event MUST have an immutable audit record BEFORE any intervention.
- FDA 21 CFR 211.150: Distribution records must include all actions taken during excursions.
- WHO PQS: Stakeholders (healthcare facilities, patients) must be notified of any delivery impact.
- GDP Ch 5: Irreversible actions (rerouting, disposal) require documented human approval.
- Insurance: CRITICAL excursions with product at risk require claim preparation for financial recovery.

If a check fails, prefix with "GAP [check_name]:" exactly. Be specific about WHAT is missing.
Return ONLY valid JSON."""


def reflect_llm(state: OrchestratorState) -> dict:
    """LLM agent critiques the plan and identifies compliance gaps."""
    ri = state["risk_input"]
    tier = ri.get("risk_tier", "LOW")

    if tier == "LOW":
        return {"reflection_notes": ["LOW risk: monitoring only, no action needed."]}

    llm = get_llm()
    if llm is None:
        from orchestrator.nodes import reflect as det_reflect
        return det_reflect(state)

    draft = state.get("draft_plan", [])
    tools_in_plan = [s.get("tool", "unknown") for s in draft if isinstance(s, dict)]
    plan_summary = "\n".join(
        f"  {s.get('step', i)}. [{s.get('tool', '?')}] {s.get('action', '?')}"
        for i, s in enumerate(draft, 1) if isinstance(s, dict)
    )

    user_msg = f"""Review this {tier} risk action plan for compliance gaps.

CONTEXT:
  risk_tier: {tier}
  fused_risk_score: {ri.get('fused_risk_score')}
  ml_spoilage_probability: {ri.get('ml_spoilage_probability')}
  rules_fired: {ri.get('deterministic_rule_flags', [])}
  primary_issue: {state.get('primary_issue', '')}

PLAN ({len(draft)} steps):
{plan_summary}

Tools in plan: {tools_in_plan}

MANDATORY CHECKS for {tier}:
1. compliance_agent present? {"YES" if "compliance_agent" in tools_in_plan else "NO - MISSING"}
2. notification_agent present? {"YES" if "notification_agent" in tools_in_plan else "NO - MISSING"}
3. approval_workflow present? {"YES" if "approval_workflow" in tools_in_plan else "NO - MISSING"}
{"4. cold_storage_agent present? " + ("YES" if "cold_storage_agent" in tools_in_plan else "NO - MISSING") if tier == "CRITICAL" else ""}
{"5. insurance_agent present? " + ("YES" if "insurance_agent" in tools_in_plan else "NO - MISSING") if tier == "CRITICAL" else ""}

Respond with ONLY this JSON:
{{
  "notes": ["observation or GAP [name]: description"],
  "has_gaps": true/false
}}"""

    try:
        response = llm.invoke([
            {"role": "system", "content": REFLECT_SYSTEM},
            {"role": "user", "content": user_msg},
        ])
        parsed = _extract_json(response.content)

        if not parsed or "notes" not in parsed:
            from orchestrator.nodes import reflect as det_reflect
            return det_reflect(state)

        notes = parsed.get("notes", [])
        if not isinstance(notes, list):
            notes = [str(notes)]

        logger.info("AGENT_REFLECT: %d notes, has_gaps=%s", len(notes), parsed.get("has_gaps"))
        return {"reflection_notes": notes}

    except Exception as exc:
        logger.error("AGENT_REFLECT failed (%s), falling back", exc)
        from orchestrator.nodes import reflect as det_reflect
        return det_reflect(state)


# ── Agentic Revise ───────────────────────────────────────────────────

REVISE_SYSTEM = """You are a pharmaceutical cold-chain action plan editor.
You receive a draft plan and reflection notes (which may contain GAP warnings).
Your job: produce a CORRECTED plan that addresses every gap.

RULES:
- Keep all existing valid steps. Do NOT remove steps that are already correct.
- Add missing tools identified in GAP notes. Place compliance_agent FIRST, approval_workflow LAST.
- IMPORTANT: Each tool should appear EXACTLY ONCE in the plan. Do NOT duplicate any tool.
- Construct real tool_input using the shipment data provided. No placeholders.
- Return ONLY valid JSON."""


def revise_llm(state: OrchestratorState) -> dict:
    """LLM rewrites the plan to fix gaps identified during reflection."""
    llm = get_llm()
    if llm is None:
        from orchestrator.nodes import revise as det_revise
        return det_revise(state)

    ri = state["risk_input"]
    draft = state.get("draft_plan", [])
    notes = state.get("reflection_notes", [])

    plan_text = "\n".join(
        f"  {s.get('step', i)}. [{s.get('tool', '?')}] {s.get('action', '?')}"
        for i, s in enumerate(draft, 1) if isinstance(s, dict)
    )
    notes_text = "\n".join(f"  - {n}" for n in notes)

    user_msg = f"""Fix this action plan based on the reflection gaps.

SHIPMENT CONTEXT:
  shipment_id: {ri.get('shipment_id')}
  container_id: {ri.get('container_id')}
  window_id: {ri.get('window_id')}
  risk_tier: {ri.get('risk_tier')}
  product_type: {ri.get('product_type')}
  transit_phase: {ri.get('transit_phase')}
  ml_spoilage_probability: {ri.get('ml_spoilage_probability')}

CURRENT PLAN:
{plan_text}

REFLECTION NOTES (fix ALL gaps):
{notes_text}

AVAILABLE TOOLS:
{TOOLS_REFERENCE}

Return ONLY this JSON:
{{
  "steps": [
    {{"step": 1, "action": "...", "tool": "tool_name", "tool_input": {{...}}, "reason": "..."}}
  ]
}}"""

    try:
        response = llm.invoke([
            {"role": "system", "content": REVISE_SYSTEM},
            {"role": "user", "content": user_msg},
        ])
        parsed = _extract_json(response.content)

        if not parsed or "steps" not in parsed:
            logger.warning("AGENT_REVISE: unparseable, falling back to deterministic")
            from orchestrator.nodes import revise as det_revise
            return det_revise(state)

        revised: List[PlanStep] = []
        seen_tools: set = set()
        for s in parsed["steps"]:
            tool_name = s.get("tool", "")
            if tool_name not in TOOL_MAP:
                continue
            if tool_name in seen_tools:
                logger.debug("AGENT_REVISE: skipping duplicate %s", tool_name)
                continue
            seen_tools.add(tool_name)
            llm_input = s.get("tool_input", {})
            if not isinstance(llm_input, dict) or not llm_input:
                from orchestrator.nodes import _build_tool_input
                llm_input = _build_tool_input(tool_name, ri, state)
            revised.append(PlanStep(
                step=len(revised) + 1,
                action=s.get("action", f"Execute {tool_name}"),
                tool=tool_name,
                tool_input=llm_input,
                reason=s.get("reason", ""),
            ))

        if not revised:
            logger.warning("AGENT_REVISE: 0 valid steps, falling back")
            from orchestrator.nodes import revise as det_revise
            return det_revise(state)

        logger.info("AGENT_REVISE: %d steps (was %d)", len(revised), len(draft))
        return {"revised_plan": revised, "plan_revised": True, "active_plan": revised}

    except Exception as exc:
        logger.error("AGENT_REVISE failed (%s), falling back", exc)
        from orchestrator.nodes import revise as det_revise
        return det_revise(state)


# ── Agentic Observe (post-execution reflection) ──────────────────────

OBSERVE_SYSTEM = """You are a pharmaceutical cold-chain operations supervisor.
You review tool execution results and decide if the response was adequate.

If a critical tool failed or returned inadequate results, recommend specific
corrective actions. If all tools succeeded, confirm the response is adequate.
Return ONLY valid JSON."""


def observe_llm(state: OrchestratorState) -> dict:
    """LLM reviews execution results and decides if re-planning is needed."""
    ri = state["risk_input"]
    tier = ri.get("risk_tier", "LOW")

    if tier in ("LOW", "MEDIUM"):
        return {"observation": "adequate", "needs_replan": False}

    tool_results = state.get("tool_results", [])
    errors = state.get("execution_errors", [])

    if not tool_results:
        return {"observation": "no tools executed", "needs_replan": tier in ("CRITICAL", "HIGH")}

    llm = get_llm()
    if llm is None:
        failed = [r["tool"] for r in tool_results if not r.get("success")]
        return {
            "observation": f"deterministic check: {len(failed)} failures",
            "needs_replan": len(failed) > 0 and tier == "CRITICAL",
            "failed_tools": failed,
        }

    results_text = ""
    for r in tool_results:
        status = "SUCCESS" if r.get("success") else "FAILED"
        result_data = r.get("result", {})
        result_summary = ""
        if isinstance(result_data, dict):
            result_summary = ", ".join(
                f"{k}={repr(v)[:60]}" for k, v in list(result_data.items())[:5]
            )
        results_text += f"\n  [{status}] {r['tool']}: {result_summary}"

    if errors:
        results_text += "\n  ERRORS: " + "; ".join(errors)

    user_msg = f"""Review these execution results for a {tier} risk event.

CONTEXT:
  shipment_id: {ri.get('shipment_id')}
  risk_tier: {tier}
  product: {ri.get('product_type')}
  spoilage_probability: {ri.get('ml_spoilage_probability')}

EXECUTION RESULTS:{results_text}

Questions to answer:
1. Did cold_storage_agent find a viable facility? (check status != "no_facility_found")
2. Did compliance_agent detect violations that need escalation?
3. Were any critical tools missing from execution?
4. Is the overall response adequate for a {tier} event?

Return ONLY this JSON:
{{
  "observation": "brief assessment of execution quality",
  "adequate": true/false,
  "issues": ["list of specific issues found, empty if adequate"],
  "recommended_actions": ["additional tools to run or actions needed, empty if adequate"]
}}"""

    try:
        response = llm.invoke([
            {"role": "system", "content": OBSERVE_SYSTEM},
            {"role": "user", "content": user_msg},
        ])
        parsed = _extract_json(response.content)

        if not parsed:
            return {"observation": "unparseable", "needs_replan": False}

        adequate = parsed.get("adequate", True)
        issues = parsed.get("issues", [])
        recommended = parsed.get("recommended_actions", [])

        logger.info("AGENT_OBSERVE: adequate=%s, issues=%d, recommended=%d",
                     adequate, len(issues), len(recommended))
        return {
            "observation": parsed.get("observation", ""),
            "needs_replan": not adequate and tier == "CRITICAL",
            "observation_issues": issues,
            "observation_actions": recommended,
        }

    except Exception as exc:
        logger.error("AGENT_OBSERVE failed (%s)", exc)
        return {"observation": f"error: {exc}", "needs_replan": False}
