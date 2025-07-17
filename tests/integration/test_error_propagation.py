"""Tests for error propagation throughout the system."""
# Test categories: integration, error_handling, error_propagation

import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from src.core.orchestrator import OrchestratorAgent
from src.core.planner import QueryPlanner
from src.core.executor import Executor
from src.tools.registry import ToolRegistry
from src.tools.mock_tools import create_mock_tools
from src.models.schemas import (
    AgentResponse,
    ConversationContext,
    ExecutionPlan,
    PlanStep,
    ExecutionContext,
    ExecutorConfig,
    PlannerConfig,
    OrchestratorConfig,
    FallbackStrategy,
)


@pytest.mark.integration
@pytest.mark.error_handling
class TestErrorPropagation:
    """Test error propagation between system components."""

    @pytest.fixture
    def tool_registry(self):
        """Create tool registry with mock tools."""
        registry = ToolRegistry()
        mock_tools = create_mock_tools()
        for tool in mock_tools:
            registry.register_tool(tool, category="research", metadata={})
        return registry

    @pytest.fixture
    def planner(self):
        """Create planner."""
        config = PlannerConfig(
            max_steps=5,
            parallel_execution=True,
            enable_conditional_execution=True
        )
        return QueryPlanner(config)

    @pytest.fixture
    def executor(self):
        """Create executor."""
        config = ExecutorConfig(
            max_retries=2,
            timeout_seconds=10,
            parallel_execution=True,
            retry_delay_seconds=0.1
        )
        return Executor(config)

    @pytest.fixture
    def orchestrator(self, tool_registry):
        """Create orchestrator."""
        config = OrchestratorConfig(
            cache_enabled=False,
            max_conversation_length=10
        )
        return OrchestratorAgent(tool_registry=tool_registry, config=config)

    @pytest.mark.asyncio
    async def test_tool_error_propagates_to_executor(self, executor, tool_registry):
        """Test that tool errors properly propagate to executor."""
        # Create plan with failing tool
        steps = [
            PlanStep(
                id="failing_step",
                tool_name="failing_tool",
                parameters={"failure_mode": "always"}
            )
        ]
        plan = ExecutionPlan(
            steps=steps,
            expected_outputs={},
            fallback_strategies={}
        )
        
        context = ExecutionContext(
            session_id="test",
            user_query="test query",
            available_tools=["failing_tool"],
            timeout_seconds=10
        )
        
        result = await executor.execute_plan(plan, context, tool_registry)
        
        # Verify error propagated correctly
        assert result.success is False
        assert result.steps_completed == 0
        assert "failing_step" in result.errors
        assert "failed to execute" in result.errors["failing_step"].lower()
        assert len(result.results) == 0

    @pytest.mark.asyncio
    async def test_executor_error_propagates_to_orchestrator(self, orchestrator):
        """Test that executor errors propagate to orchestrator."""
        # Mock planner to return plan with failing tool
        with patch.object(orchestrator.planner, 'create_plan') as mock_create_plan:
            failing_step = PlanStep(
                id="failing_step",
                tool_name="failing_tool",
                parameters={"failure_mode": "always"}
            )
            mock_create_plan.return_value = ExecutionPlan(
                steps=[failing_step],
                expected_outputs={},
                fallback_strategies={}
            )
            
            context = ConversationContext(
                session_id="test",
                message_history=[],
                metadata={}
            )
            
            response = await orchestrator.process_query("test query", context)
            
            # Verify error propagated to orchestrator response
            assert response.success is False
            assert response.error_message is not None
            assert "failed" in response.error_message.lower()
            assert response.tool_results is None

    @pytest.mark.asyncio
    async def test_planner_error_propagates_to_orchestrator(self, orchestrator):
        """Test that planner errors propagate to orchestrator."""
        # Mock planner to raise exception
        with patch.object(orchestrator.planner, 'create_plan') as mock_create_plan:
            mock_create_plan.side_effect = Exception("Planner failed to create plan")
            
            context = ConversationContext(
                session_id="test",
                message_history=[],
                metadata={}
            )
            
            response = await orchestrator.process_query("test query", context)
            
            # Verify planner error propagated
            assert response.success is False
            assert response.error_message is not None
            assert "error" in response.error_message.lower()

    @pytest.mark.asyncio
    async def test_tool_registry_error_propagates(self, executor):
        """Test that tool registry errors propagate properly."""
        # Create empty tool registry
        empty_registry = ToolRegistry()
        
        # Create plan with nonexistent tool
        steps = [
            PlanStep(
                id="missing_step",
                tool_name="nonexistent_tool",
                parameters={"param": "value"}
            )
        ]
        plan = ExecutionPlan(
            steps=steps,
            expected_outputs={},
            fallback_strategies={}
        )
        
        context = ExecutionContext(
            session_id="test",
            user_query="test query",
            available_tools=["nonexistent_tool"],
            timeout_seconds=10
        )
        
        result = await executor.execute_plan(plan, context, empty_registry)
        
        # Verify tool registry error propagated
        assert result.success is False
        assert "missing_step" in result.errors
        assert "not found" in result.errors["missing_step"].lower()

    @pytest.mark.asyncio
    async def test_timeout_error_propagation(self, executor, tool_registry):
        """Test that timeout errors propagate correctly."""
        # Create plan with slow tool and short timeout
        steps = [
            PlanStep(
                id="slow_step",
                tool_name="slow_tool",
                parameters={"delay": 5.0}  # 5 second delay
            )
        ]
        plan = ExecutionPlan(
            steps=steps,
            expected_outputs={},
            fallback_strategies={}
        )
        
        context = ExecutionContext(
            session_id="test",
            user_query="test query",
            available_tools=["slow_tool"],
            timeout_seconds=1  # 1 second timeout
        )
        
        result = await executor.execute_plan(plan, context, tool_registry)
        
        # Verify timeout error propagated
        assert result.success is False
        assert "slow_step" in result.errors
        assert "timeout" in result.errors["slow_step"].lower()

    @pytest.mark.asyncio
    async def test_dependency_error_propagation(self, executor, tool_registry):
        """Test that dependency errors propagate correctly."""
        # Create plan where first step fails and second depends on it
        steps = [
            PlanStep(
                id="failing_step",
                tool_name="failing_tool",
                parameters={"failure_mode": "always"}
            ),
            PlanStep(
                id="dependent_step",
                tool_name="search_publications",
                parameters={"query": "test"},
                dependencies=["failing_step"]
            )
        ]
        plan = ExecutionPlan(
            steps=steps,
            expected_outputs={},
            fallback_strategies={}
        )
        
        context = ExecutionContext(
            session_id="test",
            user_query="test query",
            available_tools=["failing_tool", "search_publications"],
            timeout_seconds=10
        )
        
        result = await executor.execute_plan(plan, context, tool_registry)
        
        # Verify dependency error propagation
        assert result.success is False
        assert "failing_step" in result.errors
        assert "dependent_step" not in result.results  # Should not execute
        assert result.steps_completed == 0

    @pytest.mark.asyncio
    async def test_retry_exhaustion_error_propagation(self, executor, tool_registry):
        """Test that retry exhaustion errors propagate correctly."""
        # Create plan with tool that fails after retries
        steps = [
            PlanStep(
                id="retry_step",
                tool_name="failing_tool",
                parameters={"failure_mode": "always"}
            )
        ]
        plan = ExecutionPlan(
            steps=steps,
            expected_outputs={},
            fallback_strategies={
                "failing_tool": FallbackStrategy(
                    strategy_type="retry",
                    max_retries=2,
                    retry_delay=0.1
                )
            }
        )
        
        context = ExecutionContext(
            session_id="test",
            user_query="test query",
            available_tools=["failing_tool"],
            timeout_seconds=10
        )
        
        result = await executor.execute_plan(plan, context, tool_registry)
        
        # Verify retry exhaustion error propagated
        assert result.success is False
        assert "retry_step" in result.errors
        assert "retry" in result.errors["retry_step"].lower() or "failed" in result.errors["retry_step"].lower()

    @pytest.mark.asyncio
    async def test_condition_evaluation_error_propagation(self, executor, tool_registry):
        """Test that condition evaluation errors propagate correctly."""
        # Create plan with invalid condition
        steps = [
            PlanStep(
                id="base_step",
                tool_name="search_publications",
                parameters={"query": "test"}
            ),
            PlanStep(
                id="conditional_step",
                tool_name="search_publications",
                parameters={"query": "test2"},
                dependencies=["base_step"],
                condition=Mock(field="invalid_field", operator="gt", value=5)
            )
        ]
        plan = ExecutionPlan(
            steps=steps,
            expected_outputs={},
            fallback_strategies={}
        )
        
        context = ExecutionContext(
            session_id="test",
            user_query="test query",
            available_tools=["search_publications"],
            timeout_seconds=10
        )
        
        result = await executor.execute_plan(plan, context, tool_registry)
        
        # Should handle condition evaluation error gracefully
        assert result.success is True  # Base step should succeed
        assert "base_step" in result.results
        assert result.results["base_step"] is not None
        # Conditional step should be skipped due to condition error
        assert "conditional_step" in result.results
        assert result.results["conditional_step"] is None

    @pytest.mark.asyncio
    async def test_parallel_execution_error_propagation(self, executor, tool_registry):
        """Test error propagation in parallel execution."""
        # Create plan with mix of successful and failing steps
        steps = [
            PlanStep(
                id="success_step",
                tool_name="search_publications",
                parameters={"query": "test"}
            ),
            PlanStep(
                id="failing_step",
                tool_name="failing_tool",
                parameters={"failure_mode": "always"}
            ),
            PlanStep(
                id="another_success_step",
                tool_name="search_by_author",
                parameters={"author": "test"}
            )
        ]
        plan = ExecutionPlan(
            steps=steps,
            expected_outputs={},
            fallback_strategies={}
        )
        
        context = ExecutionContext(
            session_id="test",
            user_query="test query",
            available_tools=["search_publications", "failing_tool", "search_by_author"],
            timeout_seconds=10,
            parallel_execution=True
        )
        
        result = await executor.execute_plan(plan, context, tool_registry)
        
        # Verify partial success with error propagation
        assert result.success is False  # Overall failure due to one failing step
        assert "success_step" in result.results
        assert "another_success_step" in result.results
        assert "failing_step" in result.errors
        assert result.steps_completed == 2  # Two successful steps

    @pytest.mark.asyncio
    async def test_error_message_quality(self, orchestrator):
        """Test that error messages are informative and helpful."""
        # Test various error scenarios and verify message quality
        
        # Scenario 1: Tool not found
        with patch.object(orchestrator.planner, 'create_plan') as mock_create_plan:
            mock_create_plan.return_value = ExecutionPlan(
                steps=[PlanStep(id="step1", tool_name="nonexistent_tool", parameters={})],
                expected_outputs={},
                fallback_strategies={}
            )
            
            context = ConversationContext(session_id="test", message_history=[], metadata={})
            response = await orchestrator.process_query("test query", context)
            
            assert response.success is False
            assert response.error_message is not None
            assert "not found" in response.error_message.lower()
            assert "nonexistent_tool" in response.error_message

        # Scenario 2: Tool execution failure
        with patch.object(orchestrator.planner, 'create_plan') as mock_create_plan:
            mock_create_plan.return_value = ExecutionPlan(
                steps=[PlanStep(id="step1", tool_name="failing_tool", parameters={"failure_mode": "always"})],
                expected_outputs={},
                fallback_strategies={}
            )
            
            context = ConversationContext(session_id="test", message_history=[], metadata={})
            response = await orchestrator.process_query("test query", context)
            
            assert response.success is False
            assert response.error_message is not None
            assert "failed" in response.error_message.lower()

    @pytest.mark.asyncio
    async def test_error_recovery_mechanisms(self, executor, tool_registry):
        """Test that error recovery mechanisms work correctly."""
        # Test retry mechanism
        steps = [
            PlanStep(
                id="retry_step",
                tool_name="failing_tool",
                parameters={"failure_mode": "after_n_calls", "fail_after": 2}
            )
        ]
        plan = ExecutionPlan(
            steps=steps,
            expected_outputs={},
            fallback_strategies={
                "failing_tool": FallbackStrategy(
                    strategy_type="retry",
                    max_retries=3,
                    retry_delay=0.1
                )
            }
        )
        
        context = ExecutionContext(
            session_id="test",
            user_query="test query",
            available_tools=["failing_tool"],
            timeout_seconds=10
        )
        
        result = await executor.execute_plan(plan, context, tool_registry)
        
        # Should succeed after retries
        assert result.success is True
        assert "retry_step" in result.results
        assert result.results["retry_step"] is not None
        assert len(result.errors) == 0