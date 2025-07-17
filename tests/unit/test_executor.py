"""Tests for the Executor component."""
# Test categories: unit, executor, async_execution

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import List, Dict, Any

from src.core.executor import Executor
from src.tools.base import BaseTool, ToolResult
from src.tools.mock_tools import create_mock_tools
from src.tools.registry import ToolRegistry
from src.models.schemas import (
    ExecutionPlan,
    PlanStep,
    PlanStepStatus,
    ExecutionResult,
    ExecutionContext,
    ExecutorConfig,
    Condition,
    FallbackStrategy,
)


@pytest.mark.unit
class TestExecutor:
    """Test cases for Executor class."""

    @pytest.fixture
    def executor_config(self):
        """Create executor configuration."""
        return ExecutorConfig(
            max_retries=3,
            timeout_seconds=30,
            parallel_execution=True,
            retry_delay_seconds=1,  # Shorter for testing
        )

    @pytest.fixture
    def executor(self, executor_config):
        """Create an Executor instance."""
        return Executor(executor_config)

    @pytest.fixture
    def tool_registry(self):
        """Create a tool registry with mock tools."""
        registry = ToolRegistry()
        mock_tools = create_mock_tools()
        for tool in mock_tools:
            registry.register_tool(tool, category="test", metadata={})
        return registry

    @pytest.fixture
    def execution_context(self):
        """Create execution context."""
        return ExecutionContext(
            session_id="test_session",
            user_query="test query",
            available_tools=["search_publications", "search_by_author"],
            timeout_seconds=30,
        )

    @pytest.fixture
    def simple_plan(self):
        """Create a simple execution plan."""
        steps = [
            PlanStep(
                id="step1",
                tool_name="search_publications",
                parameters={"query": "machine learning", "limit": 10},
            )
        ]
        return ExecutionPlan(steps=steps, expected_outputs={}, fallback_strategies={})

    @pytest.fixture
    def complex_plan(self):
        """Create a complex execution plan with dependencies."""
        steps = [
            PlanStep(
                id="step1",
                tool_name="search_by_author",
                parameters={"author": "John Smith"},
            ),
            PlanStep(
                id="step2",
                tool_name="get_field_statistics",
                parameters={"field": "machine learning"},
                dependencies=["step1"],
            ),
        ]
        return ExecutionPlan(steps=steps, expected_outputs={}, fallback_strategies={})

    @pytest.mark.asyncio
    async def test_executor_runs_simple_plan_successfully(
        self, executor, tool_registry, execution_context, simple_plan
    ):
        """Test that executor runs a simple plan successfully."""
        result = await executor.execute_plan(
            simple_plan, execution_context, tool_registry
        )

        # Verify result structure and success
        assert isinstance(result, ExecutionResult)
        assert result.success is True
        assert result.steps_completed == 1
        assert result.steps_total == 1
        assert len(result.errors) == 0
        
        # Verify step results contain expected data
        assert "step1" in result.results
        step_result = result.results["step1"]
        assert step_result is not None
        assert isinstance(step_result, dict)
        assert "publications" in step_result
        assert len(step_result["publications"]) > 0

    @pytest.mark.asyncio
    @pytest.mark.error_handling
    async def test_executor_handles_tool_timeout(
        self, executor, tool_registry, execution_context
    ):
        """Test that executor handles tool timeout."""
        # Create a plan with slow tool
        steps = [
            PlanStep(
                id="step1",
                tool_name="slow_tool",
                parameters={"delay": 5.0},  # 5 second delay
            )
        ]
        plan = ExecutionPlan(steps=steps, expected_outputs={}, fallback_strategies={})

        # Set very short timeout
        execution_context.timeout_seconds = 1

        result = await executor.execute_plan(plan, execution_context, tool_registry)

        # Verify timeout handling
        assert isinstance(result, ExecutionResult)
        assert result.success is False
        assert result.steps_completed == 0
        assert result.steps_total == 1
        assert len(result.results) == 0
        
        # Verify error details
        assert "step1" in result.errors
        error_message = result.errors["step1"].lower()
        assert "timeout" in error_message or "timed out" in error_message

    @pytest.mark.asyncio
    async def test_executor_retries_failed_tool_calls(
        self, executor, tool_registry, execution_context
    ):
        """Test that executor retries failed tool calls."""
        # Create a plan with failing tool
        steps = [
            PlanStep(
                id="step1",
                tool_name="failing_tool",
                parameters={"failure_mode": "after_n_calls", "fail_after": 3},
            )
        ]
        plan = ExecutionPlan(
            steps=steps,
            expected_outputs={},
            fallback_strategies={
                "failing_tool": FallbackStrategy(
                    strategy_type="retry", max_retries=5, retry_delay=0.1
                )
            },
        )

        result = await executor.execute_plan(plan, execution_context, tool_registry)

        assert isinstance(result, ExecutionResult)
        assert result.success is True  # Should succeed after retries
        assert result.steps_completed == 1
        assert "step1" in result.results

    @pytest.mark.asyncio
    async def test_executor_respects_dependency_order(
        self, executor, tool_registry, execution_context, complex_plan
    ):
        """Test that executor respects dependency order."""
        result = await executor.execute_plan(
            complex_plan, execution_context, tool_registry
        )

        assert isinstance(result, ExecutionResult)
        assert result.success is True
        assert result.steps_completed == 2
        assert result.steps_total == 2

        # Both steps should have results
        assert "step1" in result.results
        assert "step2" in result.results

        # Check that dependencies were respected (this would be evident in execution order)
        # The dependent step should have access to the first step's results
        assert result.results["step1"] is not None
        assert result.results["step2"] is not None

    @pytest.mark.asyncio
    async def test_executor_evaluates_conditions_correctly(
        self, executor, tool_registry, execution_context
    ):
        """Test that executor evaluates conditions correctly."""
        # Create a plan with conditional step
        steps = [
            PlanStep(
                id="step1",
                tool_name="search_by_author",
                parameters={"author": "John Smith"},
            ),
            PlanStep(
                id="step2",
                tool_name="get_field_statistics",
                parameters={"field": "machine learning"},
                dependencies=["step1"],
                condition=Condition(field="total_publications", operator="gt", value=1),
            ),
        ]
        plan = ExecutionPlan(steps=steps, expected_outputs={}, fallback_strategies={})

        result = await executor.execute_plan(plan, execution_context, tool_registry)

        assert isinstance(result, ExecutionResult)
        assert result.success is True

        # First step should always execute
        assert "step1" in result.results

        # Second step execution depends on condition
        # John Smith has 2 publications in mock data, so condition should be true
        assert "step2" in result.results

    @pytest.mark.asyncio
    async def test_executor_collects_all_results(
        self, executor, tool_registry, execution_context, complex_plan
    ):
        """Test that executor collects all results."""
        result = await executor.execute_plan(
            complex_plan, execution_context, tool_registry
        )

        assert isinstance(result, ExecutionResult)
        assert result.success is True

        # Should have results for all steps
        assert len(result.results) == len(complex_plan.steps)

        # Results should contain actual data
        for step_id, step_result in result.results.items():
            assert step_result is not None
            assert isinstance(step_result, dict)

    @pytest.mark.asyncio
    async def test_executor_stops_on_critical_failure(
        self, executor, tool_registry, execution_context
    ):
        """Test that executor stops on critical failure."""
        # Create a plan with failing tool that has no fallback
        steps = [
            PlanStep(
                id="step1",
                tool_name="failing_tool",
                parameters={"failure_mode": "always"},
            ),
            PlanStep(
                id="step2",
                tool_name="search_publications",
                parameters={"query": "test"},
                dependencies=["step1"],
            ),
        ]
        plan = ExecutionPlan(
            steps=steps,
            expected_outputs={},
            fallback_strategies={},  # No fallback for failing tool
        )

        result = await executor.execute_plan(plan, execution_context, tool_registry)

        assert isinstance(result, ExecutionResult)
        assert result.success is False
        assert result.steps_completed == 0
        assert "step1" in result.errors
        assert "step2" not in result.results  # Should not execute dependent step

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_executor_handles_parallel_execution(
        self, executor, tool_registry, execution_context
    ):
        """Test that executor handles parallel execution."""
        # Create a plan with independent steps
        steps = [
            PlanStep(
                id="step1",
                tool_name="search_publications",
                parameters={"query": "machine learning"},
            ),
            PlanStep(
                id="step2",
                tool_name="search_publications",
                parameters={"query": "deep learning"},
            ),
            PlanStep(
                id="step3",
                tool_name="search_publications",
                parameters={"query": "neural networks"},
            ),
        ]
        plan = ExecutionPlan(steps=steps, expected_outputs={}, fallback_strategies={})

        # Enable parallel execution
        execution_context.parallel_execution = True

        result = await executor.execute_plan(plan, execution_context, tool_registry)

        # Verify execution success and completeness
        assert isinstance(result, ExecutionResult)
        assert result.success is True
        assert result.steps_completed == 3
        assert result.steps_total == 3
        assert len(result.errors) == 0

        # Verify all steps completed successfully with expected data
        assert len(result.results) == 3
        for step_id in ["step1", "step2", "step3"]:
            assert step_id in result.results
            step_result = result.results[step_id]
            assert step_result is not None
            assert isinstance(step_result, dict)
            assert "publications" in step_result
            assert isinstance(step_result["publications"], list)
            assert len(step_result["publications"]) > 0

    @pytest.mark.asyncio
    async def test_executor_step_with_missing_tool(
        self, executor, tool_registry, execution_context
    ):
        """Test executor handling of missing tools."""
        steps = [
            PlanStep(
                id="step1", tool_name="nonexistent_tool", parameters={"param": "value"}
            )
        ]
        plan = ExecutionPlan(steps=steps, expected_outputs={}, fallback_strategies={})

        result = await executor.execute_plan(plan, execution_context, tool_registry)

        assert isinstance(result, ExecutionResult)
        assert result.success is False
        assert result.steps_completed == 0
        assert "step1" in result.errors
        assert "not found" in result.errors["step1"].lower()

    @pytest.mark.asyncio
    async def test_executor_handles_empty_plan(
        self, executor, tool_registry, execution_context
    ):
        """Test executor handling of empty plans."""
        plan = ExecutionPlan(steps=[], expected_outputs={}, fallback_strategies={})

        result = await executor.execute_plan(plan, execution_context, tool_registry)

        assert isinstance(result, ExecutionResult)
        assert result.success is True
        assert result.steps_completed == 0
        assert result.steps_total == 0
        assert len(result.results) == 0
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_executor_handles_condition_evaluation_error(
        self, executor, tool_registry, execution_context
    ):
        """Test executor handling of condition evaluation errors."""
        steps = [
            PlanStep(
                id="step1",
                tool_name="search_publications",
                parameters={"query": "test"},
            ),
            PlanStep(
                id="step2",
                tool_name="search_publications",
                parameters={"query": "test2"},
                condition=Condition(field="nonexistent_field", operator="gt", value=5),
            ),
        ]
        plan = ExecutionPlan(steps=steps, expected_outputs={}, fallback_strategies={})

        result = await executor.execute_plan(plan, execution_context, tool_registry)

        assert isinstance(result, ExecutionResult)
        # Should still succeed for step1, step2 should be skipped due to condition error
        assert result.success is True
        assert (
            result.steps_completed == 2
        )  # Both steps are "completed" (one executed, one skipped)
        assert "step1" in result.results
        assert "step2" in result.results
        assert result.results["step1"] is not None  # Has actual data
        assert result.results["step2"] is None  # Was skipped

    @pytest.mark.asyncio
    async def test_executor_config_affects_behavior(
        self, tool_registry, execution_context
    ):
        """Test that executor configuration affects behavior."""
        # Create executor with custom config
        config = ExecutorConfig(
            max_retries=1,
            timeout_seconds=5,
            parallel_execution=False,
            retry_delay_seconds=0.1,
        )
        executor = Executor(config)

        # Test with failing tool
        steps = [
            PlanStep(
                id="step1",
                tool_name="failing_tool",
                parameters={"failure_mode": "always"},
            )
        ]
        plan = ExecutionPlan(
            steps=steps,
            expected_outputs={},
            fallback_strategies={
                "failing_tool": FallbackStrategy(
                    strategy_type="retry",
                    max_retries=3,  # This should be overridden by config
                )
            },
        )

        result = await executor.execute_plan(plan, execution_context, tool_registry)

        assert isinstance(result, ExecutionResult)
        assert result.success is False
        # Should have attempted only 1 retry (as per config)
        assert "step1" in result.errors

    @pytest.mark.asyncio
    async def test_execute_step_directly(self, executor, tool_registry):
        """Test executing a single step directly."""
        step = PlanStep(
            id="step1",
            tool_name="search_publications",
            parameters={"query": "machine learning"},
        )

        result = await executor.execute_step(step, {}, tool_registry)

        assert isinstance(result, ToolResult)
        assert result.success is True
        assert result.data is not None
        assert "publications" in result.data
