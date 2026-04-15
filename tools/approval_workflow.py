from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

_PENDING_APPROVALS: Dict[str, dict] = {}


class ApprovalInput(BaseModel):
    shipment_id: str
    action_description: str = Field(description="What action needs approval")
    risk_tier: str
    urgency: str = Field(default="high", description="low, medium, high, critical")
    proposed_actions: List[str] = Field(
        description="Ordered list of actions to execute upon approval"
    )
    justification: str = Field(description="Why this action is needed")
    requested_by: str = Field(
        default="orchestrator", description="Agent or system requesting approval"
    )
    window_id: Optional[str] = Field(default=None, description="Window ID for re-execution")
    container_id: Optional[str] = Field(default=None, description="Container ID")


def _execute(
    shipment_id: str,
    action_description: str,
    risk_tier: str,
    urgency: str = "high",
    proposed_actions: List[str] | None = None,
    justification: str = "",
    requested_by: str = "orchestrator",
    window_id: Optional[str] = None,
    container_id: Optional[str] = None,
) -> dict:
    approval_id = f"APR-{uuid.uuid4().hex[:8].upper()}"
    record = {
        "approval_id": approval_id,
        "shipment_id": shipment_id,
        "window_id": window_id,
        "container_id": container_id,
        "action_description": action_description,
        "risk_tier": risk_tier,
        "urgency": urgency,
        "proposed_actions": proposed_actions or [],
        "justification": justification,
        "requested_by": requested_by,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decided_at": None,
        "decided_by": None,
        "decision": None,
    }
    _PENDING_APPROVALS[approval_id] = record

    return {
        "tool": "approval_workflow",
        "status": "approval_requested",
        "approval_id": approval_id,
        "shipment_id": shipment_id,
        "message": "Approval request created. Awaiting human decision via dashboard.",
        "timestamp": record["created_at"],
    }


def get_pending() -> List[dict]:
    return [v for v in _PENDING_APPROVALS.values() if v["status"] == "pending"]


def get_all() -> List[dict]:
    """Return all approvals sorted by created_at descending."""
    items = list(_PENDING_APPROVALS.values())
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items


def decide(approval_id: str, decision: str, decided_by: str = "operator") -> dict:
    if approval_id not in _PENDING_APPROVALS:
        return {"error": f"Approval {approval_id} not found"}
    record = _PENDING_APPROVALS[approval_id]
    record["status"] = decision  # "approved" or "rejected"
    record["decided_at"] = datetime.now(timezone.utc).isoformat()
    record["decided_by"] = decided_by
    record["decision"] = decision
    return record


approval_tool = StructuredTool.from_function(
    func=_execute,
    name="approval_workflow",
    description=(
        "Submit an action for human-in-the-loop approval. Creates a "
        "pending approval request that appears on the ops dashboard. "
        "The action is NOT executed until a human approves it."
    ),
    args_schema=ApprovalInput,
)
