"""Tests for agent/agents/supervisor.py"""

import pytest

from agent.agents.supervisor import supervisor_node


@pytest.mark.asyncio
class TestSupervisorNode:
    """Test supervisor_node routing logic."""

    async def test_error_status_finishes(self, sample_state):
        """Error status routes to FINISH."""
        sample_state["status"] = "error"
        result = await supervisor_node(sample_state)
        assert result["next_agent"] == "FINISH"
        assert result["status"] == "error"

    async def test_max_iterations_finishes(self, sample_state):
        """Iteration > 10 routes to FINISH with error."""
        sample_state["iteration"] = 10
        result = await supervisor_node(sample_state)
        assert result["next_agent"] == "FINISH"
        assert result["status"] == "error"
        assert "max iterations" in result["supervisor_reasoning"].lower()

    async def test_report_generated_finishes(self, sample_state):
        """Completed report routes to FINISH with completed status."""
        sample_state["report_generated"] = True
        result = await supervisor_node(sample_state)
        assert result["next_agent"] == "FINISH"
        assert result["status"] == "completed"

    async def test_need_regulation_first(self, sample_state):
        """Unchecked regulation routes to regulation_expert."""
        sample_state["regulation_checked"] = False
        result = await supervisor_node(sample_state)
        assert result["next_agent"] == "regulation_expert"

    async def test_need_risk_assessment(self, sample_state):
        """Checked regulation but unassessed risk routes to risk_assessor."""
        sample_state["regulation_checked"] = True
        sample_state["risk_assessed"] = False
        result = await supervisor_node(sample_state)
        assert result["next_agent"] == "risk_assessor"

    async def test_need_report_writer(self, sample_state):
        """All analysis done routes to report_writer."""
        sample_state["regulation_checked"] = True
        sample_state["risk_assessed"] = True
        sample_state["report_generated"] = False
        result = await supervisor_node(sample_state)
        assert result["next_agent"] == "report_writer"

    async def test_iteration_increments(self, sample_state):
        """Iteration counter increments on each call."""
        sample_state["iteration"] = 0
        result = await supervisor_node(sample_state)
        assert result["iteration"] == 1

        # Simulate next call with updated state
        sample_state["iteration"] = result["iteration"]
        result2 = await supervisor_node(sample_state)
        assert result2["iteration"] == 2

    async def test_error_takes_priority_over_max_iterations(self, sample_state):
        """Error status checked before max iterations."""
        sample_state["status"] = "error"
        sample_state["iteration"] = 15
        result = await supervisor_node(sample_state)
        assert result["next_agent"] == "FINISH"
        assert result["status"] == "error"

    async def test_report_takes_priority_over_regulation(self, sample_state):
        """Report generated checked before regulation."""
        sample_state["report_generated"] = True
        sample_state["regulation_checked"] = False
        result = await supervisor_node(sample_state)
        assert result["next_agent"] == "FINISH"
        assert result["status"] == "completed"

    async def test_messages_appended(self, sample_state):
        """Messages list contains routing info."""
        result = await supervisor_node(sample_state)
        assert "messages" in result
        assert len(result["messages"]) > 0
        assert "Supervisor" in result["messages"][0]
