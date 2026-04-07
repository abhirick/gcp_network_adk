from __future__ import annotations

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.apps import App
from google.adk.tools.function_tool import FunctionTool

from gcp_network_adk.config import settings
from gcp_network_adk.logging_config import configure_logging, get_logger
from gcp_network_adk.prompts import (
    COLLECTOR_INSTRUCTION,
    ORCHESTRATOR_INSTRUCTION,
    REMEDIATION_INSTRUCTION,
)
from gcp_network_adk.schemas import ScanRequest
from gcp_network_adk.tools.recommender import scan_request_to_json
from gcp_network_adk.tools.remediation import generate_fix_suggestions

configure_logging()
logger = get_logger(__name__)

scan_request_to_json_tool = FunctionTool(func=scan_request_to_json)
generate_fix_suggestions_tool = FunctionTool(func=generate_fix_suggestions)

collector_agent = LlmAgent(
    name="collector_agent",
    model=settings.adk_model,
    description="Collects GCP Network Analyzer insights from the Recommender API.",
    instruction=COLLECTOR_INSTRUCTION,
    tools=[scan_request_to_json_tool],
    input_schema=ScanRequest,
    output_key="collector_output",
)

remediation_agent = LlmAgent(
    name="remediation_agent",
    model=settings.adk_model,
    description="Creates remediation suggestions from collected network insights.",
    instruction=REMEDIATION_INSTRUCTION,
    tools=[generate_fix_suggestions_tool],
    output_key="remediation_output",
)

root_agent = SequentialAgent(
    name="root_network_ops_agent",
    description=ORCHESTRATOR_INSTRUCTION,
    sub_agents=[
        collector_agent,
        remediation_agent,
    ],
)

app = App(
    name="gcp_network_analyzer_app",
    root_agent=root_agent,
)

logger.info("ADK app initialised with model=%s", settings.adk_model)