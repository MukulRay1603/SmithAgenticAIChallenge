from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

_FACILITIES_PATH = Path(__file__).resolve().parent.parent / "data" / "facilities.json"
_facilities_cache: Optional[dict] = None


def _load_facilities() -> dict:
    global _facilities_cache
    if _facilities_cache is None:
        with open(_FACILITIES_PATH) as f:
            _facilities_cache = json.load(f)
    return _facilities_cache


class SchedulingInput(BaseModel):
    shipment_id: str
    product_id: str
    affected_facilities: List[str] = Field(
        description="Hospital/clinic names or codes expecting this shipment"
    )
    original_eta: str = Field(description="Original ETA as ISO datetime string or label")
    revised_eta: Optional[str] = Field(
        default=None,
        description="Revised ETA (ISO datetime), injected by cascade from delay computation",
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
    facilities = _load_facilities()
    facility_record = facilities.get(product_id, {})
    appointment_count = facility_record.get("appointment_count", 0)
    facility_contact = facility_record.get("contact", "")

    # Use facilities from cascade context if provided, otherwise fall back to profile lookup
    resolved_facilities = affected_facilities if affected_facilities and affected_facilities != ["facility_TBD"] \
        else [f"{facility_record.get('name', 'Unknown')} ({facility_record.get('location', '')})"]

    # Derive patient impact from revised_eta vs original_eta
    if revised_eta and revised_eta != "TBD":
        patient_impact = "high" if appointment_count >= 10 else "medium"
    else:
        patient_impact = "medium"

    recommendations = []
    for fac in resolved_facilities:
        recommendations.append({
            "facility": fac,
            "facility_contact": facility_contact,
            "action": "reschedule_appointments",
            "appointment_count": appointment_count,
            "original_eta": original_eta,
            "revised_eta": revised_eta or "TBD — awaiting reroute confirmation",
            "patient_impact": patient_impact,
            "notification_sent": False,
        })

    return {
        "tool": "scheduling_agent",
        "status": "recommendations_generated",
        "shipment_id": shipment_id,
        "product_id": product_id,
        "reason": reason,
        "facility_recommendations": recommendations,
        "total_appointments_affected": appointment_count * len(resolved_facilities),
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
        "facilities affected by shipment delays. Uses the destination "
        "facility record for the product type and accepts a cascade-injected "
        "revised ETA. Does NOT directly modify hospital systems."
    ),
    args_schema=SchedulingInput,
)
