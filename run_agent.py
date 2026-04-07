from __future__ import annotations

import asyncio
import json
import sys
from typing import Sequence

from dotenv import load_dotenv
from google.adk.runners import InMemoryRunner

from src.gcp_network_adk.agent import app
from src.gcp_network_adk.logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)
load_dotenv()


def build_prompt(project_ids: Sequence[str]) -> str:
    return f"""
Scan these GCP projects using Network Analyzer insights through the Recommender API:
{json.dumps(list(project_ids))}

Workflow requirements:
1. collector_agent must collect active findings.
2. remediation_agent must generate remediation suggestions from the collector output.
3. Return:
   - executive summary
   - findings grouped by project
   - findings grouped by severity and type
   - remediation guidance
   - validation steps
   - rollback considerations

Use only facts returned from tools for the findings.
"""


async def main() -> int:
    project_ids = [item.strip() for item in sys.argv[1:] if item.strip()]
    if not project_ids:
        print("Usage: python run_agent.py <project-id> [<project-id> ...]")
        return 1

    logger.info("Starting ADK runner for projects=%s", project_ids)
    runner = InMemoryRunner(app=app)
    prompt = build_prompt(project_ids)

    try:
        response = await runner.run_debug(prompt)
        print("\n=== FINAL ADK RESPONSE ===\n")
        print(response)
        logger.info("ADK run completed successfully")
        return 0
    except Exception:
        logger.exception("ADK execution failed")
        return 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))