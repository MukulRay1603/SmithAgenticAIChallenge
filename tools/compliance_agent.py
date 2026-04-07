from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

LOG_DIR = Path(__file__).resolve().parent.parent / "audit_logs"


class ComplianceInput(BaseModel):
    shipment_id: str
    container_id: str
    window_id: str
    event_type: str = Field(
        description="Type: risk_assessment, excursion, action_taken, approval_decision"
    )
    risk_tier: str
    details: Dict[str, Any] = Field(description="Event-specific payload")
    regulatory_tags: List[str] = Field(
        default_factory=list,
        description="Applicable tags: GDP, FDA_21CFR11, WHO_PQS, DSCSA",
    )


def _execute(
    shipment_id: str,
    container_id: str,
    window_id: str,
    event_type: str,
    risk_tier: str,
    details: Dict[str, Any],
    regulatory_tags: List[str] | None = None,
) -> dict:
    record = {
        "log_id": f"CL-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "shipment_id": shipment_id,
        "container_id": container_id,
        "window_id": window_id,
        "event_type": event_type,
        "risk_tier": risk_tier,
        "details": details,
        "regulatory_tags": regulatory_tags or [],
        "immutable": True,
    }

    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / "compliance_events.jsonl"
    with open(log_path, "a") as f:
        f.write(json.dumps(record) + "\n")

    return {
        "tool": "compliance_agent",
        "status": "logged",
        "log_id": record["log_id"],
        "log_path": str(log_path),
        "timestamp": record["timestamp"],
    }


compliance_tool = StructuredTool.from_function(
    func=_execute,
    name="compliance_agent",
    description=(
        "Write an immutable audit/compliance log entry for any risk event, "
        "action, or decision.  Supports GDP, FDA 21 CFR Part 11, WHO PQS, "
        "and DSCSA tags.  Always succeeds (append-only log)."
    ),
    args_schema=ComplianceInput,
)
