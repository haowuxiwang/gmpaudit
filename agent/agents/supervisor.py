"""Supervisor Agent: routes work to specialized agents."""

import logging

from agent.state import AuditState

logger = logging.getLogger(__name__)


async def supervisor_node(state: AuditState) -> dict:
    iteration = state.get("iteration", 0) + 1
    logger.info("Supervisor: iteration=%s", iteration)

    if state.get("status") == "error" and not state.get("regulation_checked"):
        return {
            "next_agent": "FINISH",
            "iteration": iteration,
            "status": "error",
            "supervisor_reasoning": "Error before regulation check completed, stopping pipeline",
            "messages": [f"Supervisor (iter {iteration}): early error state detected, stopping"],
        }

    if iteration > 10:
        return {
            "next_agent": "FINISH",
            "status": "error",
            "iteration": iteration,
            "supervisor_reasoning": "Max iterations reached",
            "messages": ["Supervisor: max iterations reached, stopping"],
        }

    if state.get("report_generated"):
        return {
            "next_agent": "FINISH",
            "iteration": iteration,
            "status": "completed",
            "supervisor_reasoning": "Report generated",
            "messages": [f"Supervisor (iter {iteration}): report generated, workflow complete"],
        }

    if not state.get("regulation_checked"):
        return {
            "next_agent": "regulation_expert",
            "iteration": iteration,
            "supervisor_reasoning": "Need to retrieve relevant regulations first",
            "messages": [f"Supervisor (iter {iteration}): routing to regulation_expert"],
        }

    if not state.get("risk_assessed"):
        return {
            "next_agent": "risk_assessor",
            "iteration": iteration,
            "supervisor_reasoning": "Regulation retrieval finished, now assess risk",
            "messages": [f"Supervisor (iter {iteration}): routing to risk_assessor"],
        }

    return {
        "next_agent": "report_writer",
        "iteration": iteration,
        "supervisor_reasoning": "Analysis finished, generate final report",
        "messages": [f"Supervisor (iter {iteration}): routing to report_writer"],
    }
