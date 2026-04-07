from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


class RouteInput(BaseModel):
    shipment_id: str = Field(description="Shipment to reroute")
    container_id: str = Field(description="Container within the shipment")
    current_leg_id: str = Field(description="Current transport leg")
    reason: str = Field(description="Why rerouting is requested")
    preferred_mode: Optional[str] = Field(
        default=None,
        description="Preferred transport mode: air, road, sea, or None for auto",
    )


ALTERNATE_ROUTES = [
    {"route": "FRA→LHR→JFK (air)", "carrier": "Lufthansa Cargo", "eta_delta_hrs": -4},
    {"route": "AMS→ORD direct (air)", "carrier": "KLM Cargo", "eta_delta_hrs": -2},
    {"route": "CDG→MIA via road+air", "carrier": "DHL Express", "eta_delta_hrs": 1},
    {"route": "BRU→IAD (air charter)", "carrier": "Atlas Air", "eta_delta_hrs": -6},
]


def _execute(
    shipment_id: str,
    container_id: str,
    current_leg_id: str,
    reason: str,
    preferred_mode: Optional[str] = None,
) -> dict:
    option = random.choice(ALTERNATE_ROUTES)
    return {
        "tool": "route_agent",
        "status": "recommendation_generated",
        "shipment_id": shipment_id,
        "container_id": container_id,
        "original_leg": current_leg_id,
        "recommended_route": option["route"],
        "carrier": option["carrier"],
        "eta_change_hours": option["eta_delta_hrs"],
        "reason": reason,
        "requires_approval": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


route_tool = StructuredTool.from_function(
    func=_execute,
    name="route_agent",
    description=(
        "Recommend an alternative route or carrier for a shipment. "
        "Returns a route option with ETA impact. Does NOT auto-execute; "
        "requires human approval."
    ),
    args_schema=RouteInput,
)
