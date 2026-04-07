from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


class InsuranceInput(BaseModel):
    shipment_id: str
    container_id: str
    product_id: str
    risk_tier: str
    incident_summary: str = Field(description="Brief description of the incident")
    estimated_loss_usd: Optional[float] = Field(
        default=None, description="Estimated financial loss"
    )
    supporting_evidence: List[str] = Field(
        default_factory=list,
        description="References to audit log IDs or event records",
    )


def _execute(
    shipment_id: str,
    container_id: str,
    product_id: str,
    risk_tier: str,
    incident_summary: str,
    estimated_loss_usd: Optional[float] = None,
    supporting_evidence: List[str] | None = None,
) -> dict:
    claim_id = f"CLM-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    return {
        "tool": "insurance_agent",
        "status": "claim_draft_prepared",
        "claim_id": claim_id,
        "shipment_id": shipment_id,
        "container_id": container_id,
        "product_id": product_id,
        "risk_tier": risk_tier,
        "incident_summary": incident_summary,
        "estimated_loss_usd": estimated_loss_usd,
        "supporting_evidence": supporting_evidence or [],
        "next_steps": [
            "Attach full audit trail from compliance_agent logs",
            "Obtain QA sign-off on product disposition",
            "Submit to insurer portal within 72 hours",
        ],
        "requires_approval": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


insurance_tool = StructuredTool.from_function(
    func=_execute,
    name="insurance_agent",
    description=(
        "Prepare insurance claim documentation for a spoilage or "
        "excursion incident.  Produces a draft claim with references "
        "to compliance logs.  Does NOT file the claim -- requires approval."
    ),
    args_schema=InsuranceInput,
)
