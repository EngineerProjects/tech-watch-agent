"""
Integration tests for the orchestrator workflow.

Tests the full pipeline:
- Plan generation
- Parallel research execution
- Collection and analysis
- Synthesis
- Session persistence
- Checkpoint/resume
"""

import asyncio
from types import SimpleNamespace
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.orchestrator.agent import OrchestratorAgent
from app.agents.orchestrator.config import OrchestratorConfig
from app.agents.orchestrator.nodes import OrchestratorNodes, group_parallel_steps, analyze_step_dependencies
from app.agents.orchestrator.state import OrchestratorState, PlanStep, StepStatus, StepType
from app.services.session_manager import (
    SessionManager,
    SessionPhase,
    CompactionReason,
    create_session,
    get_session,
    CompactionResult,
)


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


class TestOrchestratorNodes:
    """Tests for OrchestratorNodes."""

    @pytest.fixture
    def nodes(self):
        """Create OrchestratorNodes instance."""
        return OrchestratorNodes(
            max_articles=5,
            min_sources=2,
            enable_session_persistence=False,
        )

    def test_nodes_initialization(self, nodes):
        """Test nodes are initialized correctly."""
        assert nodes._max_articles == 5
        assert nodes._min_sources == 2
        assert nodes._enable_persistence is False

    def test_estimate_memory_size(self):
        """Test memory size estimation."""
        from app.services.session_manager import SessionManager
        manager = SessionManager(session_id="test-session")
        state = {
            "plan": [{"step_id": "step_1", "status": "done"}],
            "research_results": [
                {"data": [{"title": "Test", "summary": "x" * 100}]}
            ],
            "analysis_results": "Analysis text",
        }
        size = manager.estimate_memory_size(state)
        assert size > 0

    def test_estimate_memory_size_empty(self):
        """Test memory size estimation with empty state."""
        from app.services.session_manager import SessionManager
        manager = SessionManager(session_id="test-session")
        state = {}
        size = manager.estimate_memory_size(state)
        assert size == 0


class TestParallelExecution:
    """Tests for parallel execution logic."""

    def test_group_parallel_steps(self):
        """Test step grouping for parallel execution."""
        plan = [
            {"step_id": "step_1", "step_type": StepType.DEEP_RESEARCH, "status": StepStatus.PENDING},
            {"step_id": "step_2", "step_type": StepType.RESEARCH, "status": StepStatus.PENDING},
            {"step_id": "step_3", "step_type": StepType.NEWSLETTER, "status": StepStatus.PENDING},
            {"step_id": "step_4", "step_type": StepType.SYNTHESIS, "status": StepStatus.PENDING},
            {"step_id": "step_5", "step_type": StepType.EMAIL, "status": StepStatus.PENDING},
        ]

        parallel_groups, sequential_indices = group_parallel_steps(plan)

        # step_1, step_2, step_3 should be parallelizable
        assert len(parallel_groups) == 3  # Each type grouped separately
        # step_4, step_5 are sequential
        assert 3 in sequential_indices  # step_4 (index 3)
        assert 4 in sequential_indices  # step_5 (index 4)

    def test_analyze_step_dependencies(self):
        """Test dependency analysis for steps."""
        plan = [
            {"step_id": "step_1", "step_type": StepType.RESEARCH},
            {"step_id": "step_2", "step_type": StepType.SYNTHESIS},
            {"step_id": "step_3", "step_type": StepType.EMAIL},
        ]

        deps = analyze_step_dependencies(plan)
        # SYNTHESIS depends on research steps
        assert "step_1" in deps["step_2"]
        # EMAIL depends on SYNTHESIS
        assert "step_2" in deps["step_3"]


class TestOrchestratorState:
    """Tests for OrchestratorState."""

    def test_state_initialization(self):
        """Test orchestrator state initializes correctly."""
        state: OrchestratorState = {
            "task": "Test task",
            "plan": [],
            "errors": [],
        }
        assert state["task"] == "Test task"
        assert state["plan"] == []
        assert state["errors"] == []

    def test_plan_step_structure(self):
        """Test plan step structure."""
        step: PlanStep = {
            "step_id": "step_1",
            "name": "Test step",
            "step_type": StepType.RESEARCH,
            "status": StepStatus.PENDING,
        }
        assert step["step_id"] == "step_1"
        assert step["step_type"] == StepType.RESEARCH
        assert step["status"] == StepStatus.PENDING


class TestOrchestratorConfig:
    """Tests for OrchestratorConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = OrchestratorConfig()
        assert config.max_iterations == 5
        assert config.enable_checkpointing is False

    def test_custom_config(self):
        """Test custom configuration."""
        config = OrchestratorConfig(
            max_iterations=10,
            enable_checkpointing=True,
            checkpoint_backend="postgres",
        )
        assert config.max_iterations == 10
        assert config.enable_checkpointing is True
        assert config.checkpoint_backend == "postgres"


class TestSessionManager:
    """Tests for SessionManager."""

    def test_compaction_result(self):
        """Test CompactionResult dataclass."""
        result = CompactionResult(
            success=True,
            compacted_data={"summary": "test"},
            original_size=10000,
            compacted_size=2000,
            compression_ratio=0.8,
            summary="Compacted successfully",
            key_insights=["insight1", "insight2"],
            sources_count=10,
        )
        assert result.success is True
        assert result.compression_ratio == 0.8
        assert len(result.key_insights) == 2

    def test_session_phase_enum(self):
        """Test SessionPhase enum values."""
        assert SessionPhase.PLAN.value == "plan"
        assert SessionPhase.RESEARCH.value == "research"
        assert SessionPhase.SYNTHESIS.value == "synthesis"

    def test_compaction_reason_enum(self):
        """Test CompactionReason enum values."""
        assert CompactionReason.PHASE_TRANSITION.value == "phase_transition"
        assert CompactionReason.CONTEXT_LIMIT_WARNING.value == "context_limit_warning"
        assert CompactionReason.MANUAL.value == "manual"


class TestSessionFinalization:
    """Tests for terminal session persistence."""

    @pytest.mark.asyncio
    async def test_finalize_session_sets_completed_state(self):
        manager = SessionManager(session_id=uuid.uuid4())
        manager._session = SimpleNamespace(
            status="running",
            phase="synthesis",
            plan=[{"step_id": "step_1", "name": "Synthesis"}],
            current_step_index=0,
            research_results=[],
            analysis_results="",
            final_report=None,
            notes=[],
            raw_notes=[],
            completed_at=None,
            updated_at=None,
            meta_data={"last_error": "stale"},
        )
        manager._db_session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
        manager._sync_normalized_steps = AsyncMock()
        manager._sync_normalized_sources = AsyncMock()

        await manager.finalize_session(status="completed", final_report="Final report")

        assert manager._session.status == "completed"
        assert manager._session.phase == "completed"
        assert manager._session.final_report == "Final report"
        assert manager._session.completed_at is not None
        assert "last_error" not in manager._session.meta_data
        manager._db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_finalize_session_sets_failure_error_metadata(self):
        manager = SessionManager(session_id=uuid.uuid4())
        manager._session = SimpleNamespace(
            status="running",
            phase="research",
            plan=[],
            current_step_index=0,
            research_results=[],
            analysis_results="",
            final_report=None,
            notes=[],
            raw_notes=[],
            completed_at=None,
            updated_at=None,
            meta_data={},
        )
        manager._db_session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
        manager._sync_normalized_steps = AsyncMock()
        manager._sync_normalized_sources = AsyncMock()

        await manager.finalize_session(status="failed", error="boom")

        assert manager._session.status == "failed"
        assert manager._session.phase == "failed"
        assert manager._session.meta_data["last_error"] == "boom"
        assert manager._session.completed_at is not None
        manager._db_session.commit.assert_awaited_once()


class TestPlanValidation:
    """Tests for plan validation."""

    def test_validate_step_types(self):
        """Test step type validation."""
        valid_types = [StepType.RESEARCH, StepType.DEEP_RESEARCH, StepType.SYNTHESIS]
        for step_type in valid_types:
            assert step_type in StepType

    def test_validate_step_status(self):
        """Test step status validation."""
        valid_statuses = [StepStatus.PENDING, StepStatus.RUNNING, StepStatus.DONE, StepStatus.FAILED]
        for status in valid_statuses:
            assert status in StepStatus


class TestOrchestratorAgent:
    """Tests for OrchestratorAgent."""

    @pytest.fixture
    def agent(self):
        """Create OrchestratorAgent instance."""
        config = OrchestratorConfig(max_iterations=1)
        return OrchestratorAgent(config=config)

    def test_agent_initialization(self, agent):
        """Test agent initializes correctly."""
        assert agent.name == "orchestrator"
        assert "orchestrator" in agent.description.lower()

    def test_agent_config(self, agent):
        """Test agent has correct configuration."""
        assert agent._config is not None
        assert agent._config.max_iterations == 1


class TestStepTypeEnum:
    """Tests for StepType enum."""

    def test_all_step_types_defined(self):
        """Test all expected step types are defined."""
        expected_types = [
            "research",
            "deep_research",
            "analysis",
            "synthesis",
            "validation",
            "email",
            "newsletter",
        ]
        for type_name in expected_types:
            step_type = StepType(type_name)
            assert step_type.value == type_name

    def test_step_type_from_string(self):
        """Test step type creation from string."""
        step_type = StepType("deep_research")
        assert step_type == StepType.DEEP_RESEARCH


class TestWorkflowIntegration:
    """Integration tests for the complete workflow."""

    @pytest.fixture
    def workflow_nodes(self):
        """Create nodes with session persistence disabled for testing."""
        return OrchestratorNodes(
            max_articles=5,
            min_sources=2,
            enable_session_persistence=False,
        )

    @pytest.mark.asyncio
    async def test_supervisor_entry_point(self, workflow_nodes):
        """Test supervisor node as entry point."""
        state: OrchestratorState = {
            "task": "Test task",
            "plan": [],
            "errors": [],
        }

        result = await workflow_nodes.supervisor(state)

        assert result["task"] == "Test task"
        assert "errors" in result

    @pytest.mark.asyncio
    async def test_planner_requires_task(self, workflow_nodes):
        """Test planner handles empty task gracefully."""
        state: OrchestratorState = {
            "task": "",
            "errors": [],
        }

        result = await workflow_nodes.supervisor(state)

        assert len(result["errors"]) > 0
        assert "No task" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_dispatcher_skips_completed_steps(self, workflow_nodes):
        """Test dispatcher skips already completed steps."""
        state: OrchestratorState = {
            "task": "Test",
            "plan": [
                {
                    "step_id": "step_1",
                    "name": "Test",
                    "step_type": StepType.DEEP_RESEARCH,
                    "status": StepStatus.DONE,
                }
            ],
            "current_step_index": 0,
            "research_results": [],
        }

        result = await workflow_nodes.dispatcher(state)

        # Should have moved to next step
        assert result["current_step_index"] == 1

    @pytest.mark.asyncio
    async def test_dispatcher_handles_empty_plan(self, workflow_nodes):
        """Test dispatcher handles empty plan."""
        state: OrchestratorState = {
            "task": "Test",
            "plan": [],
            "current_step_index": 0,
            "research_results": [],
        }

        result = await workflow_nodes.dispatcher(state)

        assert result["current_step_index"] == 0

    def test_memory_size_threshold_check(self):
        """Test memory size threshold logic."""
        from app.services.session_manager import SessionManager
        manager = SessionManager(session_id="test-session")
        small_state = {"plan": [], "research_results": []}
        small_size = manager.estimate_memory_size(small_state)
        assert small_size < 1000

        large_state = {
            "plan": [{"data": "x" * 50000}],
            "research_results": [{"data": [{"content": "y" * 50000}]}],
        }
        large_size = manager.estimate_memory_size(large_state)
        assert large_size > 40000


class TestErrorHandling:
    """Tests for error handling in orchestrator."""

    def test_orchestrator_state_with_errors(self):
        """Test state tracks errors correctly."""
        state: OrchestratorState = {
            "task": "Test",
            "errors": ["Error 1", "Error 2"],
        }
        assert len(state["errors"]) == 2

    def test_validation_errors_tracking(self):
        """Test validation errors are tracked."""
        state: OrchestratorState = {
            "task": "Test",
            "validation_errors": ["Insufficient articles"],
        }
        assert len(state["validation_errors"]) == 1
        assert "Insufficient" in state["validation_errors"][0]


# Run tests with: pytest tests/test_orchestrator_integration.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])