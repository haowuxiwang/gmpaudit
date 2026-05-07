"""Supervisor Agent: routes work to specialized agents.

Phase 2: deterministic routing based on state fields.
Phase 2 upgrade: LLM-driven routing for more flexible workflows.
"""

from agent.state import AuditState


async def supervisor_node(state: AuditState) -> dict:
    """Route to the next agent based on current state.

    Routing order: regulation_expert -> risk_assessor -> report_writer -> FINISH
    """
    iteration = state.get("iteration", 0) + 1

    # Safety: prevent infinite loops
    if iteration > 10:
        return {
            "next_agent": "FINISH",
            "status": "error",
            "iteration": iteration,
            "messages": ["Supervisor: max iterations reached, stopping"],
        }

    # Check completion conditions
    if state.get("report_markdown"):
        return {
            "next_agent": "FINISH",
            "iteration": iteration,
            "status": "completed",
            "messages": [f"Supervisor (iter {iteration}): report generated, workflow complete"],
        }

    # Route to next agent
    if not state.get("matched_regulations"):
        return {
            "next_agent": "regulation_expert",
            "iteration": iteration,
            "supervisor_reasoning": "Need to retrieve relevant regulations first",
            "messages": [f"Supervisor (iter {iteration}): routing to regulation_expert"],
        }

    if not state.get("findings"):
        return {
            "next_agent": "risk_assessor",
            "iteration": iteration,
            "supervisor_reasoning": "Regulations matched, now assess compliance risk",
            "messages": [f"Supervisor (iter {iteration}): routing to risk_assessor"],
        }

    return {
        "next_agent": "report_writer",
        "iteration": iteration,
        "supervisor_reasoning": "Analysis complete, generate final report",
        "messages": [f"Supervisor (iter {iteration}): routing to report_writer"],
    }
