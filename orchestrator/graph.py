"""
Advanced orchestration agent -- LangGraph StateGraph.

Graph topology:
  interpret -> plan -> reflect -> [revise?] -> execute -> fallback -> output

Agentic mode (when any LLM provider is available):
  plan and reflect nodes use the LLM to reason, decide tools, and construct inputs.

Deterministic fallback:
  If no LLM provider is available or CARGO_LLM_ENABLED=0, all nodes are template-based.

Multi-provider LLM system (priority configurable):
  CARGO_LLM_PRIORITY=ollama,openai,anthropic  (default)
  OPENAI_API_KEY=...        (slot for cloud API)
  ANTHROPIC_API_KEY=...     (slot for cloud API)
  CARGO_OLLAMA_MODEL=...    (default: qwen2.5:7b)

Usage:
    from orchestrator.graph import run_orchestrator
    decision = run_orchestrator(risk_engine_output_dict)
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
    revise,
)
from orchestrator.state import OrchestratorState

logger = logging.getLogger(__name__)


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


def build_orchestrator() -> StateGraph:
    """Construct the orchestration StateGraph with agentic or deterministic nodes."""
    graph = StateGraph(OrchestratorState)

    plan_node = _get_plan_node()
    reflect_node = _get_reflect_node()

    graph.add_node("interpret", interpret_risk)
    graph.add_node("plan", plan_node)
    graph.add_node("reflect", reflect_node)
    graph.add_node("revise", revise)
    graph.add_node("execute", execute)
    graph.add_node("fallback", build_fallback)
    graph.add_node("output", compile_output)

    graph.set_entry_point("interpret")
    graph.add_edge("interpret", "plan")
    graph.add_edge("plan", "reflect")

    graph.add_conditional_edges(
        "reflect",
        _should_revise,
        {
            "revise": "revise",
            "execute": "execute",
            "skip_to_output": "output",
        },
    )

    graph.add_edge("revise", "execute")
    graph.add_edge("execute", "fallback")
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
    """
    Run the orchestration agent on a single risk engine output.
    Returns the OrchestratorDecision dict.
    """
    app = get_compiled()
    initial: OrchestratorState = {"risk_input": risk_input}
    final_state = app.invoke(initial)
    return final_state.get("final_output", {})


def get_graph_mermaid() -> str:
    """Return the Mermaid diagram string for the orchestration graph."""
    graph = build_orchestrator()
    return graph.compile().get_graph().draw_mermaid()


def get_mode() -> Dict[str, str]:
    """Return current orchestrator mode details."""
    return {
        "mode": "agentic" if get_llm() is not None else "deterministic",
        "provider": get_provider_name(),
        "model": get_model_name(),
    }
