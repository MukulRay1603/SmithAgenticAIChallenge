"""
Advanced orchestration agent -- LangGraph StateGraph.

Graph topology:
  interpret -> plan -> reflect -> [revise?] -> execute -> fallback -> output

The conditional edge after reflect checks whether the reflection found
gaps that need revision.  For LOW risk, execution is skipped entirely.

Usage:
    from orchestrator.graph import build_orchestrator, run_orchestrator
    decision = run_orchestrator(risk_engine_output_dict)
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from langgraph.graph import END, StateGraph

from orchestrator.nodes import (
    build_fallback,
    compile_output,
    execute,
    interpret_risk,
    plan,
    reflect,
    revise,
)
from orchestrator.state import OrchestratorState

logger = logging.getLogger(__name__)


def _should_revise(state: OrchestratorState) -> str:
    """Route after reflection: revise if gaps found, else straight to execute."""
    notes = state.get("reflection_notes", [])
    tier = state["risk_input"].get("risk_tier", "LOW")

    if tier == "LOW":
        return "skip_to_output"

    has_gaps = any("GAP" in n for n in notes)
    already_revised = state.get("plan_revised", False)

    if has_gaps and not already_revised:
        return "revise"
    return "execute"


def _should_execute(state: OrchestratorState) -> str:
    """After possible revision, decide whether to execute or skip."""
    tier = state["risk_input"].get("risk_tier", "LOW")
    if tier == "LOW":
        return "skip_to_output"
    return "execute"


def build_orchestrator() -> StateGraph:
    """Construct the orchestration StateGraph."""
    graph = StateGraph(OrchestratorState)

    graph.add_node("interpret", interpret_risk)
    graph.add_node("plan", plan)
    graph.add_node("reflect", reflect)
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


def get_compiled():
    global _compiled
    if _compiled is None:
        _compiled = build_orchestrator().compile()
    return _compiled


def run_orchestrator(risk_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the orchestration agent on a single risk engine output.
    Returns the OrchestratorDecision dict (matches system_prompt.md output format).
    """
    app = get_compiled()
    initial: OrchestratorState = {"risk_input": risk_input}
    final_state = app.invoke(initial)
    return final_state.get("final_output", {})


def get_graph_mermaid() -> str:
    """Return the Mermaid diagram string for the orchestration graph."""
    graph = build_orchestrator()
    return graph.compile().get_graph().draw_mermaid()
