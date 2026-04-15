"""
Advanced orchestration agent -- LangGraph StateGraph.

Graph topology (with observation loop):
  interpret → plan → reflect → [revise] → execute → observe → [re-plan?] → output

The observation loop allows the agent to inspect execution results and
re-plan if critical tools failed (max 1 re-plan to avoid infinite loops).

Agentic mode (when any LLM provider is available):
  plan, reflect, revise, and observe nodes use the LLM.

Deterministic fallback:
  If no LLM provider is available or CARGO_LLM_ENABLED=0, all nodes are template-based.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from langgraph.graph import END, StateGraph

from orchestrator.llm_provider import get_llm, get_provider_name, get_model_name
from orchestrator.nodes import (
    build_fallback,
    compile_output,
    execute,
    interpret_risk,
    plan as plan_deterministic,
    reflect as reflect_deterministic,
    revise as revise_deterministic,
)
from orchestrator.state import OrchestratorState

logger = logging.getLogger(__name__)

MAX_REPLAN = 1


def _get_plan_node():
    if get_llm() is not None:
        from orchestrator.llm_nodes import plan_llm
        logger.info("Plan node: AGENTIC (%s/%s)", get_provider_name(), get_model_name())
        return plan_llm
    logger.info("Plan node: DETERMINISTIC (no LLM available)")
    return plan_deterministic


def _get_reflect_node():
    if get_llm() is not None:
        from orchestrator.llm_nodes import reflect_llm
        logger.info("Reflect node: AGENTIC (%s/%s)", get_provider_name(), get_model_name())
        return reflect_llm
    logger.info("Reflect node: DETERMINISTIC")
    return reflect_deterministic


def _get_revise_node():
    if get_llm() is not None:
        from orchestrator.llm_nodes import revise_llm
        logger.info("Revise node: AGENTIC (%s/%s)", get_provider_name(), get_model_name())
        return revise_llm
    logger.info("Revise node: DETERMINISTIC")
    return revise_deterministic


def _get_observe_node():
    if get_llm() is not None:
        from orchestrator.llm_nodes import observe_llm
        logger.info("Observe node: AGENTIC (%s/%s)", get_provider_name(), get_model_name())
        return observe_llm
    return _observe_deterministic


def _observe_deterministic(state: OrchestratorState) -> dict:
    """Deterministic post-execution check: flag if critical tools failed."""
    tool_results = state.get("tool_results", [])
    tier = state.get("risk_input", {}).get("risk_tier", "LOW")
    failed = [r["tool"] for r in tool_results if not r.get("success")]

    if failed and tier == "CRITICAL":
        return {
            "observation": f"CRITICAL: {len(failed)} tools failed: {failed}",
            "needs_replan": True,
            "observation_issues": [f"{t} failed" for t in failed],
            "observation_actions": [f"retry or replace {t}" for t in failed],
        }
    return {"observation": "adequate", "needs_replan": False}


def _should_revise(state: OrchestratorState) -> str:
    notes = state.get("reflection_notes", [])
    tier = state["risk_input"].get("risk_tier", "LOW")

    if tier == "LOW":
        return "skip_to_output"

    has_gaps = any("GAP" in str(n).upper() for n in notes)
    already_revised = state.get("plan_revised", False)

    if has_gaps and not already_revised:
        return "revise"
    return "execute"


def _should_replan(state: OrchestratorState) -> str:
    """After observe: re-plan if needed and under the iteration limit."""
    needs = state.get("needs_replan", False)
    count = state.get("replan_count", 0)

    if needs and count < MAX_REPLAN:
        logger.info("OBSERVE→REPLAN: iteration %d, re-planning", count + 1)
        return "replan"
    return "finalize"


def _replan_increment(state: OrchestratorState) -> dict:
    """Bump the replan counter and feed observation back into planning context."""
    count = state.get("replan_count", 0)
    issues = state.get("observation_issues", [])
    obs = state.get("observation", "")

    existing_notes = state.get("reflection_notes", [])
    new_notes = list(existing_notes) + [f"OBSERVATION: {obs}"] + [f"ISSUE: {i}" for i in issues]

    return {
        "replan_count": count + 1,
        "plan_revised": False,
        "reflection_notes": new_notes,
    }


def build_orchestrator() -> StateGraph:
    """Construct the orchestration StateGraph with observation loop."""
    graph = StateGraph(OrchestratorState)

    plan_node = _get_plan_node()
    reflect_node = _get_reflect_node()
    revise_node = _get_revise_node()
    observe_node = _get_observe_node()

    graph.add_node("interpret", interpret_risk)
    graph.add_node("plan", plan_node)
    graph.add_node("reflect", reflect_node)
    graph.add_node("revise", revise_node)
    graph.add_node("execute", execute)
    graph.add_node("observe", observe_node)
    graph.add_node("replan_bridge", _replan_increment)
    graph.add_node("fallback", build_fallback)
    graph.add_node("output", compile_output)

    graph.set_entry_point("interpret")
    graph.add_edge("interpret", "plan")
    graph.add_edge("plan", "reflect")

    graph.add_conditional_edges(
        "reflect",
        _should_revise,
        {"revise": "revise", "execute": "execute", "skip_to_output": "output"},
    )

    graph.add_edge("revise", "execute")
    graph.add_edge("execute", "observe")

    graph.add_conditional_edges(
        "observe",
        _should_replan,
        {"replan": "replan_bridge", "finalize": "fallback"},
    )

    graph.add_edge("replan_bridge", "plan")
    graph.add_edge("fallback", "output")
    graph.add_edge("output", END)

    return graph


_compiled = None
_last_provider = None


def get_compiled():
    global _compiled, _last_provider
    current = get_provider_name()
    if _compiled is None or current != _last_provider:
        _compiled = build_orchestrator().compile()
        _last_provider = current
    return _compiled


def run_orchestrator(risk_input: Dict[str, Any]) -> Dict[str, Any]:
    """Run the orchestration agent on a single risk engine output."""
    app = get_compiled()
    initial: OrchestratorState = {"risk_input": risk_input, "replan_count": 0}
    final_state = app.invoke(initial)
    return final_state.get("final_output", {})


def run_orchestrator_selective(
    risk_input: Dict[str, Any],
    selected_tools: list[str],
) -> Dict[str, Any]:
    """Execute only the human-selected tools — bypasses plan/reflect/revise.

    Directly runs: interpret → build plan → execute → observe → compile.
    Does NOT go through the LangGraph to avoid the LLM overwriting the
    human-selected plan.
    """
    from orchestrator.nodes import (
        interpret_risk, execute, build_fallback, compile_output, _build_tool_input,
    )
    from orchestrator.state import PlanStep

    plan_steps = []
    for i, tool_name in enumerate(selected_tools, 1):
        if tool_name in TOOL_MAP:
            plan_steps.append(PlanStep(
                step=i, action=f"Execute {tool_name} (human-selected)",
                tool=tool_name,
                tool_input=_build_tool_input(tool_name, risk_input, {"risk_input": risk_input}),
                reason="Selected by human operator",
            ))

    state: OrchestratorState = {
        "risk_input": risk_input,
        "replan_count": 0,
        "draft_plan": plan_steps,
        "active_plan": plan_steps,
        "plan_revised": True,
        "reflection_notes": ["Human-selected tools — skipping plan/reflect/revise."],
        "llm_reasoning": "Plan constructed by human operator via tool selection UI.",
    }

    state.update(interpret_risk(state))
    state.update(execute(state))

    observe_node = _get_observe_node()
    state.update(observe_node(state))

    state.update(build_fallback(state))
    state.update(compile_output(state))

    return state.get("final_output", {})


def get_graph_mermaid() -> str:
    graph = build_orchestrator()
    return graph.compile().get_graph().draw_mermaid()


def get_mode() -> Dict[str, str]:
    return {
        "mode": "agentic" if get_llm() is not None else "deterministic",
        "provider": get_provider_name(),
        "model": get_model_name(),
    }


# Re-export TOOL_MAP for the selective runner
from tools import TOOL_MAP
