"""
Agent tools for the AI Cargo Monitoring orchestration layer.

Each tool is a LangChain StructuredTool with a Pydantic input schema.
The orchestrator imports `ALL_TOOLS` and registers them in a ToolNode.

Current implementations return realistic mock responses.  Swap the
`_execute` body for real integrations when external APIs are available.
"""

from tools.route_agent import route_tool
from tools.cold_storage_agent import cold_storage_tool
from tools.notification_agent import notification_tool
from tools.compliance_agent import compliance_tool
from tools.scheduling_agent import scheduling_tool
from tools.insurance_agent import insurance_tool
from tools.triage_agent import triage_tool
from tools.approval_workflow import approval_tool

ALL_TOOLS = [
    route_tool,
    cold_storage_tool,
    notification_tool,
    compliance_tool,
    scheduling_tool,
    insurance_tool,
    triage_tool,
    approval_tool,
]

TOOL_MAP = {t.name: t for t in ALL_TOOLS}
