from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


class ColdStorageInput(BaseModel):
    shipment_id: str = Field(description="Shipment needing cold storage")
    container_id: str = Field(description="Container ID")
    product_id: str = Field(description="Product type for temp matching")
    location_hint: Optional[str] = Field(
        default=None, description="Nearest airport/city code"
    )
    urgency: str = Field(
        default="high", description="low, medium, high, or critical"
    )


FACILITIES = [
    {"name": "PharmaPort FRA", "location": "Frankfurt", "capacity_pct": 42, "temp_range": "-25 to +8C"},
    {"name": "ColdChain Hub LHR", "location": "London Heathrow", "capacity_pct": 68, "temp_range": "-30 to +15C"},
    {"name": "BioStore AMS", "location": "Amsterdam", "capacity_pct": 25, "temp_range": "-20 to +8C"},
    {"name": "MedFreeze JFK", "location": "New York JFK", "capacity_pct": 55, "temp_range": "-40 to +10C"},
]


def _execute(
    shipment_id: str,
    container_id: str,
    product_id: str,
    location_hint: Optional[str] = None,
    urgency: str = "high",
) -> dict:
    facility = random.choice(FACILITIES)
    return {
        "tool": "cold_storage_agent",
        "status": "facility_identified",
        "shipment_id": shipment_id,
        "container_id": container_id,
        "product_id": product_id,
        "recommended_facility": facility["name"],
        "location": facility["location"],
        "available_capacity_pct": facility["capacity_pct"],
        "temp_range": facility["temp_range"],
        "urgency": urgency,
        "requires_approval": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


cold_storage_tool = StructuredTool.from_function(
    func=_execute,
    name="cold_storage_agent",
    description=(
        "Find and recommend a backup cold-storage facility near the "
        "shipment's current location.  Returns facility details and "
        "available capacity.  Does NOT reserve; requires approval."
    ),
    args_schema=ColdStorageInput,
)
