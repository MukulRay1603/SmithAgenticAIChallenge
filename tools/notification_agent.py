from __future__ import annotations

from datetime import datetime, timezone
from typing import List

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
        default="email", description="Delivery channel: email, sms, dashboard, webhook"
    )


def _execute(
    shipment_id: str,
    container_id: str,
    risk_tier: str,
    recipients: List[str],
    message: str,
    channel: str = "email",
) -> dict:
    return {
        "tool": "notification_agent",
        "status": "notification_queued",
        "shipment_id": shipment_id,
        "container_id": container_id,
        "risk_tier": risk_tier,
        "recipients": recipients,
        "channel": channel,
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
        "For HIGH/CRITICAL tiers, notifications are queued for approval "
        "before delivery."
    ),
    args_schema=NotificationInput,
)
