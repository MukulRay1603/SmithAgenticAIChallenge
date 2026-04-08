from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


class NotificationInput(BaseModel):
    shipment_id: str
    container_id: str
    risk_tier: str = Field(description="LOW, MEDIUM, HIGH, or CRITICAL")
    recipients: List[str] = Field(
        description="Recipient roles: ops_team, clinic, hospital, management, regulatory"
    )
    message: str = Field(description="Notification body text")
    channel: str = Field(
        default="dashboard", description="Delivery channel: email, sms, dashboard, webhook"
    )
    # Cascade-enriched fields — populated by _enrich_tool_input() at runtime
    revised_eta: Optional[str] = Field(
        default=None,
        description="Revised arrival ETA (ISO datetime) computed from current_delay_min",
    )
    spoilage_probability: Optional[float] = Field(
        default=None,
        description="ML spoilage probability (0-1) for this window",
    )
    facility_name: Optional[str] = Field(
        default=None,
        description="Destination or backup facility name, injected from cold_storage result",
    )


def _execute(
    shipment_id: str,
    container_id: str,
    risk_tier: str,
    recipients: List[str],
    message: str,
    channel: str = "dashboard",
    revised_eta: Optional[str] = None,
    spoilage_probability: Optional[float] = None,
    facility_name: Optional[str] = None,
) -> dict:
    # Build a structured alert payload — richer than a plain message string
    alert_payload: dict = {
        "shipment_id": shipment_id,
        "container_id": container_id,
        "risk_tier": risk_tier,
        "message": message,
    }
    if revised_eta:
        alert_payload["revised_eta"] = revised_eta
    if spoilage_probability is not None:
        alert_payload["spoilage_probability_pct"] = round(spoilage_probability * 100, 1)
    if facility_name:
        alert_payload["destination_facility"] = facility_name

    return {
        "tool": "notification_agent",
        "status": "notification_queued",
        "shipment_id": shipment_id,
        "container_id": container_id,
        "risk_tier": risk_tier,
        "recipients": recipients,
        "channel": channel,
        "alert_payload": alert_payload,
        "message_preview": message[:200],
        "delivered": False,
        "requires_approval": risk_tier in ("HIGH", "CRITICAL"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


notification_tool = StructuredTool.from_function(
    func=_execute,
    name="notification_agent",
    description=(
        "Send an alert or notification to specified stakeholders. "
        "Accepts revised ETA, spoilage probability, and facility name "
        "to produce a product-specific alert payload. "
        "For HIGH/CRITICAL tiers, notifications are queued for approval "
        "before delivery."
    ),
    args_schema=NotificationInput,
)
