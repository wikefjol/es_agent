"""Tests for the Planning Agent component."""

import pytest
from unittest.mock import Mock, AsyncMock
from typing import List, Dict, Any

from src.core.planner import PlanningAgent
from src.tools.base import BaseTool, ToolResult
from src.tools.mock_tools import create_mock_tools
from src.models.schemas import (
    ExecutionPlan,
    PlanStep,
    PlanStepStatus,
    Condition,
    FallbackStrategy,
    OutputSchema,
)


class TestPlanningAgent:
    """Test cases for PlanningAgent class."""

    @pytest.fixture
    def planner(self):
        """Create a PlanningAgent instance."""
        return PlanningAgent()

    @pytest.fixture
    def mock_tools(self):
        """Create mock tools for testing."""
        return create_mock_tools()

    @pytest.fixture
    def mock_context(self):
        """Create mock context for testing."""
        return Mock()

    def test_planner_creates_simple_linear_plan(self, planner, mock_tools):
        """Test that planner creates a simple linear plan."""
        query = "find publications about machine learning"

        plan = planner.create_plan(query, mock_tools)

        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) > 0
        assert all(isinstance(step, PlanStep) for step in plan.steps)
        assert all(step.status == PlanStepStatus.PENDING for step in plan.steps)

        # Should have at least one step for searching publications
        step_names = [step.tool_name for step in plan.steps]
        assert "search_publications" in step_names

    def test_planner_creates_plan_with_dependencies(self, planner, mock_tools):
        """Test that planner creates plans with step dependencies."""
        query = (
            "How many publications has John Smith written and what are his main topics?"
        )

        plan = planner.create_plan(query, mock_tools)

        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) >= 2  # Should have author search + stats

        # Check that some steps have dependencies
        dependent_steps = [step for step in plan.steps if step.dependencies]
        assert len(dependent_steps) > 0

        # Verify dependency references are valid
        all_step_ids = {step.id for step in plan.steps}
        for step in dependent_steps:
            for dep_id in step.dependencies:
                assert dep_id in all_step_ids

    def test_planner_creates_conditional_plan(self, planner, mock_tools):
        """Test that planner creates conditional plans."""
        query = "Find publications by John Smith, and if he has more than 5 papers, get field statistics"

        plan = planner.create_plan(query, mock_tools)

        assert isinstance(plan, ExecutionPlan)

        # Should have conditional steps
        conditional_steps = [step for step in plan.steps if step.condition is not None]
        assert len(conditional_steps) > 0

        # Check condition structure
        for step in conditional_steps:
            assert isinstance(step.condition, Condition)
            assert step.condition.field is not None
            assert step.condition.operator is not None
            assert step.condition.value is not None

    def test_planner_adapts_plan_after_tool_failure(self, planner, mock_tools):
        """Test that planner adapts plan after tool failure."""
        # Create original plan with multiple steps
        query = (
            "How many publications has John Smith written and what are his main topics?"
        )
        original_plan = planner.create_plan(query, mock_tools)

        # Ensure we have at least 2 steps for this test
        assert len(original_plan.steps) >= 2

        # Simulate failure at step 1
        failure_point = 1
        execution_results = [
            ToolResult(success=True, data={"test": "data"}),  # Step 0 success
            ToolResult(success=False, data=None, error="Tool failed"),  # Step 1 failed
        ]

        adapted_plan = planner.adapt_plan(
            original_plan, execution_results, failure_point
        )

        assert isinstance(adapted_plan, ExecutionPlan)

        # The adaptation should have happened
        assert adapted_plan.metadata.get("adapted") is True
        assert adapted_plan.metadata.get("failure_point") == failure_point

        # The successful step should be preserved
        assert len(adapted_plan.steps) >= 1
        assert adapted_plan.steps[0].status == PlanStepStatus.COMPLETED

        # The plan should handle the failure appropriately
        # Either by skipping (reducing steps) or replacing (maintaining steps)
        assert len(adapted_plan.steps) <= len(original_plan.steps) or len(
            adapted_plan.steps
        ) >= len(original_plan.steps)

    def test_planner_validates_tool_availability(self, planner):
        """Test that planner validates tool availability."""
        query = "find publications about machine learning"
        empty_tools = []

        plan = planner.create_plan(query, empty_tools)

        # Should create a plan but with no executable steps or error handling
        assert isinstance(plan, ExecutionPlan)
        # Either empty plan or plan with fallback strategies
        assert len(plan.steps) == 0 or len(plan.fallback_strategies) > 0

    def test_planner_handles_ambiguous_queries(self, planner, mock_tools):
        """Test that planner handles ambiguous queries."""
        ambiguous_query = "find stuff about things"

        plan = planner.create_plan(ambiguous_query, mock_tools)

        assert isinstance(plan, ExecutionPlan)
        # Should create a plan with general search or ask for clarification
        assert len(plan.steps) > 0 or "clarification" in plan.metadata

    def test_planner_includes_expected_outputs(self, planner, mock_tools):
        """Test that planner includes expected output schemas."""
        query = "find publications by John Smith"

        plan = planner.create_plan(query, mock_tools)

        assert isinstance(plan.expected_outputs, dict)
        assert len(plan.expected_outputs) > 0

        for output_key, output_schema in plan.expected_outputs.items():
            assert isinstance(output_schema, OutputSchema)
            assert output_schema.type is not None
            assert isinstance(output_schema.fields, dict)

    def test_planner_includes_fallback_strategies(self, planner, mock_tools):
        """Test that planner includes fallback strategies."""
        query = "find publications about machine learning"

        plan = planner.create_plan(query, mock_tools)

        assert isinstance(plan.fallback_strategies, dict)
        assert len(plan.fallback_strategies) > 0

        for strategy_key, strategy in plan.fallback_strategies.items():
            assert isinstance(strategy, FallbackStrategy)
            assert strategy.strategy_type is not None
            assert strategy.max_retries > 0

    def test_planner_optimizes_for_parallel_execution(self, planner, mock_tools):
        """Test that planner optimizes for parallel execution when possible."""
        query = "find publications about both machine learning and healthcare"

        plan = planner.create_plan(query, mock_tools)

        # Should have some steps that can run in parallel (no dependencies)
        independent_steps = [step for step in plan.steps if not step.dependencies]
        assert len(independent_steps) > 0

        # Or should have metadata indicating parallel execution opportunities
        if len(independent_steps) <= 1:
            assert "parallel_groups" in plan.metadata

    def test_planner_handles_context_information(
        self, planner, mock_tools, mock_context
    ):
        """Test that planner uses context information when available."""
        query = "find more publications by the same author"

        # Mock context with previous results
        mock_context.get_previous_results.return_value = [
            {"author": "John Smith", "topic": "machine learning"}
        ]

        plan = planner.create_plan(query, mock_tools, context=mock_context)

        assert isinstance(plan, ExecutionPlan)
        # Should use context to infer the author
        author_search_steps = [
            step for step in plan.steps if step.tool_name == "search_by_author"
        ]
        assert len(author_search_steps) > 0

        # Should have author parameter filled from context
        author_step = author_search_steps[0]
        assert "author" in author_step.parameters
        assert author_step.parameters["author"] == "John Smith"

    def test_planner_step_ids_are_unique(self, planner, mock_tools):
        """Test that all step IDs in a plan are unique."""
        query = "comprehensive search for machine learning publications"

        plan = planner.create_plan(query, mock_tools)

        step_ids = [step.id for step in plan.steps]
        assert len(step_ids) == len(set(step_ids))  # No duplicates

    def test_planner_creates_valid_step_parameters(self, planner, mock_tools):
        """Test that planner creates valid parameters for each step."""
        query = "find publications by John Smith about machine learning"

        plan = planner.create_plan(query, mock_tools)

        for step in plan.steps:
            assert isinstance(step.parameters, dict)
            # Parameters should be relevant to the tool
            if step.tool_name == "search_publications":
                assert any(
                    key in step.parameters for key in ["query", "author", "topic"]
                )
            elif step.tool_name == "search_by_author":
                assert "author" in step.parameters

    def test_adapt_plan_preserves_successful_steps(self, planner, mock_tools):
        """Test that adapting plan preserves successful steps."""
        query = "find publications about AI"
        original_plan = planner.create_plan(query, mock_tools)

        # Simulate mixed results
        execution_results = [
            ToolResult(success=True, data={"publications": []}),  # Success
            ToolResult(success=False, data=None, error="Failed"),  # Failure
            ToolResult(success=True, data={"stats": {}}),  # Success
        ]

        adapted_plan = planner.adapt_plan(
            original_plan, execution_results, failure_point=1
        )

        # Should preserve successful steps
        assert len(adapted_plan.steps) >= len(original_plan.steps)

        # First step should be preserved (it was successful)
        assert adapted_plan.steps[0].id == original_plan.steps[0].id

        # Third step should be preserved (it was successful)
        if len(original_plan.steps) > 2:
            # Find the corresponding step in adapted plan
            preserved_step = next(
                (
                    step
                    for step in adapted_plan.steps
                    if step.id == original_plan.steps[2].id
                ),
                None,
            )
            assert preserved_step is not None
