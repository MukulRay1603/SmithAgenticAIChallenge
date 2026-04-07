from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


class SchedulingInput(BaseModel):
    shipment_id: str
    product_id: str
    affected_facilities: List[str] = Field(
        description="Hospital/clinic codes that expect this shipment"
    )
    original_eta: str = Field(description="Original ETA as ISO datetime string")
    revised_eta: Optional[str] = Field(
        default=None, description="New ETA if known"
    )
    reason: str = Field(description="Reason for schedule change")


def _execute(
    shipment_id: str,
    product_id: str,
    affected_facilities: List[str],
    original_eta: str,
    revised_eta: Optional[str] = None,
    reason: str = "",
) -> dict:
    recommendations = []
    for fac in affected_facilities:
        recommendations.append({
            "facility": fac,
            "action": "reschedule_appointments",
            "original_eta": original_eta,
            "revised_eta": revised_eta or "TBD -- awaiting reroute confirmation",
            "patient_impact": "low" if revised_eta else "medium",
            "notification_sent": False,
        })
    return {
        "tool": "scheduling_agent",
        "status": "recommendations_generated",
        "shipment_id": shipment_id,
        "product_id": product_id,
        "reason": reason,
        "facility_recommendations": recommendations,
        "note": "This tool generates reschedule recommendations only. "
                "It does not modify EMR or hospital scheduling systems.",
        "requires_approval": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


scheduling_tool = StructuredTool.from_function(
    func=_execute,
    name="scheduling_agent",
    description=(
        "Generate reschedule recommendations for downstream healthcare "
        "facilities affected by shipment delays.  Does NOT directly "
        "modify hospital systems -- produces a recommendation payload."
    ),
    args_schema=SchedulingInput,
)
