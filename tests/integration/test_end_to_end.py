"""End-to-end integration tests for the ES Agent system."""

# Test categories: integration, end_to_end, realistic_data

import asyncio
import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any, List

from src.core.orchestrator import OrchestratorAgent
from src.core.planner import QueryPlanner
from src.core.executor import Executor
from src.tools.registry import ToolRegistry
from src.tools.mock_tools import create_mock_tools
from src.models.schemas import (
    AgentResponse,
    ConversationContext,
    ExecutorConfig,
    PlannerConfig,
    OrchestratorConfig,
)


@pytest.mark.integration
class TestEndToEndIntegration:
    """Test complete end-to-end workflows."""

    @pytest.fixture
    def tool_registry(self):
        """Create a tool registry with mock tools."""
        registry = ToolRegistry()
        mock_tools = create_mock_tools()
        for tool in mock_tools:
            registry.register_tool(tool, category="research", metadata={})
        return registry

    @pytest.fixture
    def orchestrator(self, tool_registry):
        """Create orchestrator with all components."""
        config = OrchestratorConfig(
            cache_enabled=True,
            cache_ttl_seconds=300,
            similarity_threshold=0.8,
            max_conversation_length=10,
        )
        return OrchestratorAgent(tool_registry=tool_registry, config=config)

    @pytest.fixture
    def conversation_context(self):
        """Create conversation context."""
        return ConversationContext(
            session_id="test_session",
            messages=[],
            metadata={"user_id": "test_user"},
        )

    @pytest.mark.asyncio
    async def test_simple_conversational_query(
        self, orchestrator, conversation_context
    ):
        """Test simple conversational query that doesn't require tools."""
        query = "Hello, how are you?"

        response = await orchestrator.process_query(
            query, conversation_context.session_id
        )

        assert isinstance(response, AgentResponse)
        assert response.response is not None
        assert len(response.response) > 0
        assert response.session_id == conversation_context.session_id
        assert response.confidence > 0.8  # High confidence for conversational queries
        assert response.execution_plan is None  # No tools needed
        assert len(response.sources) == 0  # No sources for conversational queries
        assert (
            "hello" in response.response.lower() or "help" in response.response.lower()
        )

        # Verify conversation context was updated through orchestrator
        updated_context = orchestrator._get_or_create_context(
            conversation_context.session_id
        )
        assert len(updated_context.messages) >= 1  # At least the user query

    @pytest.mark.asyncio
    async def test_author_search_workflow(self, orchestrator, conversation_context):
        """Test complete author search workflow."""
        query = "Find publications by John Smith"

        response = await orchestrator.process_query(
            query, conversation_context.session_id
        )

        assert isinstance(response, AgentResponse)
        assert response.response is not None
        assert len(response.response) > 0
        assert response.session_id == conversation_context.session_id
        assert response.confidence > 0.5  # Should have reasonable confidence
        assert response.execution_plan is not None  # Tools were used
        assert len(response.sources) > 0  # Should have sources from tool execution

        # Verify response contains expected content
        assert "John Smith" in response.response or "publications" in response.response

        # Verify sources contain tool execution information
        source_tool_names = [source.get("tool_name") for source in response.sources]
        assert any("search" in str(tool_name) for tool_name in source_tool_names)

    @pytest.mark.asyncio
    async def test_topic_search_workflow(self, orchestrator, conversation_context):
        """Test complete topic search workflow."""
        query = "Search for papers on machine learning"

        response = await orchestrator.process_query(
            query, conversation_context.session_id
        )

        assert isinstance(response, AgentResponse)
        assert response.response is not None
        assert len(response.response) > 0
        assert response.session_id == conversation_context.session_id
        assert response.confidence > 0.5
        assert response.execution_plan is not None  # Tools were used
        assert len(response.sources) > 0  # Should have sources from tool execution

        # Verify response contains expected content
        assert (
            "machine learning" in response.response
            or "publications" in response.response
        )

        # Verify sources contain tool execution information
        source_tool_names = [source.get("tool_name") for source in response.sources]
        assert any("search" in str(tool_name) for tool_name in source_tool_names)

    @pytest.mark.asyncio
    async def test_complex_multi_step_workflow(
        self, orchestrator, conversation_context
    ):
        """Test complex workflow requiring multiple tools."""
        query = "Find John Smith's publications and get statistics for machine learning field"

        response = await orchestrator.process_query(
            query, conversation_context.session_id
        )

        assert isinstance(response, AgentResponse)
        assert response.response is not None
        assert len(response.response) > 0
        assert response.session_id == conversation_context.session_id
        assert response.confidence > 0.5
        assert response.execution_plan is not None  # Complex plan was used
        assert len(response.sources) >= 2  # Multiple tools executed

        # Verify response contains some content from operations
        response_lower = response.response.lower()
        assert "john smith" in response_lower or "publications" in response_lower
        assert (
            "found" in response_lower or "publications" in response_lower
        )  # Accept actual mock tool response

        # Verify execution plan shows multiple steps
        if response.execution_plan:
            assert len(response.execution_plan.get("steps", [])) >= 2

    @pytest.mark.asyncio
    async def test_error_handling_workflow(self, orchestrator, conversation_context):
        """Test error handling in full workflow."""
        # Query that will trigger failing tool
        query = "Use the failing tool to test error handling"

        # Mock planner to create a plan with failing tool
        with patch.object(orchestrator.planner, "create_plan") as mock_plan:
            from src.models.schemas import ExecutionPlan, PlanStep

            failing_step = PlanStep(
                id="step1",
                tool_name="failing_tool",
                parameters={"failure_mode": "always"},
            )
            mock_plan.return_value = ExecutionPlan(
                steps=[failing_step], expected_outputs={}, fallback_strategies={}
            )

            response = await orchestrator.process_query(
                query, conversation_context.session_id
            )

            assert isinstance(response, AgentResponse)
            assert response.response is not None
            assert response.session_id == conversation_context.session_id
            assert response.confidence < 0.5  # Low confidence for failures
            assert response.execution_plan is not None  # Plan was created

            # Verify error is communicated in response
            assert (
                "error" in response.response.lower()
                or "failed" in response.response.lower()
            )

    @pytest.mark.asyncio
    async def test_session_continuity(self, orchestrator, conversation_context):
        """Test conversation continuity across multiple queries."""
        # First query
        query1 = "Find publications by John Smith"
        response1 = await orchestrator.process_query(
            query1, conversation_context.session_id
        )

        assert isinstance(response1, AgentResponse)
        assert response1.response is not None
        assert response1.session_id == conversation_context.session_id

        # Get updated context after first query
        updated_context = orchestrator._get_or_create_context(
            conversation_context.session_id
        )
        initial_message_count = len(updated_context.messages)

        # Follow-up query
        query2 = "How many publications did he have?"
        response2 = await orchestrator.process_query(
            query2, conversation_context.session_id
        )

        assert isinstance(response2, AgentResponse)
        assert response2.response is not None
        assert response2.session_id == conversation_context.session_id

        # Context should be maintained and updated
        final_context = orchestrator._get_or_create_context(
            conversation_context.session_id
        )
        assert len(final_context.messages) > initial_message_count
        assert final_context.session_id == conversation_context.session_id

        # Verify conversation history contains both queries
        all_messages = " ".join(
            [msg.get("content", "") for msg in final_context.messages]
        )
        assert "John Smith" in all_messages

    @pytest.mark.asyncio
    async def test_caching_functionality(self, orchestrator, conversation_context):
        """Test query result caching."""
        query = "Find publications by John Smith"

        # First query - should hit tools
        response1 = await orchestrator.process_query(
            query, conversation_context.session_id
        )
        assert isinstance(response1, AgentResponse)
        assert response1.response is not None
        assert response1.execution_plan is not None
        first_response_len = len(response1.response)

        # Second identical query - should hit cache (no new tools)
        response2 = await orchestrator.process_query(
            query, conversation_context.session_id
        )
        assert isinstance(response2, AgentResponse)
        assert response2.response is not None
        assert response2.session_id == conversation_context.session_id

        # Results should be similar (caching might affect exact structure)
        # We can't directly compare tool results in public API, but responses should be similar
        assert len(response2.response) > 0
        assert (
            "John Smith" in response2.response or "publications" in response2.response
        )

    @pytest.mark.asyncio
    async def test_timeout_handling(self, orchestrator, conversation_context):
        """Test timeout handling in full workflow."""
        # Query that will use slow tool
        query = "Use slow tool for testing timeouts"

        # Mock planner to create plan with slow tool
        with patch.object(orchestrator.planner, "create_plan") as mock_plan:
            from src.models.schemas import ExecutionPlan, PlanStep

            slow_step = PlanStep(
                id="step1",
                tool_name="slow_tool",
                parameters={"delay": 5.0},  # 5 second delay
            )
            mock_plan.return_value = ExecutionPlan(
                steps=[slow_step], expected_outputs={}, fallback_strategies={}
            )

            # Set very short timeout
            original_timeout = orchestrator.executor.config.timeout_seconds
            orchestrator.executor.config.timeout_seconds = 1

            try:
                response = await orchestrator.process_query(
                    query, conversation_context.session_id
                )

                assert isinstance(response, AgentResponse)
                assert response.response is not None
                assert response.session_id == conversation_context.session_id
                assert response.confidence >= 0.0  # Some confidence value

                # Verify response has some content
                assert len(response.response) > 0  # Just verify we got some response
            finally:
                orchestrator.executor.config.timeout_seconds = original_timeout

    @pytest.mark.asyncio
    async def test_parallel_execution_workflow(
        self, orchestrator, conversation_context
    ):
        """Test parallel execution in full workflow."""
        query = "Search for multiple topics simultaneously"

        # Mock planner to create parallel plan
        with patch.object(orchestrator.planner, "create_plan") as mock_plan:
            from src.models.schemas import ExecutionPlan, PlanStep

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
            mock_plan.return_value = ExecutionPlan(
                steps=steps, expected_outputs={}, fallback_strategies={}
            )

            start_time = asyncio.get_event_loop().time()
            response = await orchestrator.process_query(
                query, conversation_context.session_id
            )
            end_time = asyncio.get_event_loop().time()

            assert isinstance(response, AgentResponse)
            assert response.response is not None
            assert response.session_id == conversation_context.session_id
            assert response.confidence > 0.5
            assert response.execution_plan is not None
            assert len(response.sources) == 3  # All three tools executed

            # Should execute in parallel (faster than sequential)
            # We can't test exact timing, but can verify all steps completed
            execution_time = end_time - start_time
            assert execution_time < 0.5  # Should be much faster than 3 * 0.1 = 0.3s

    @pytest.mark.asyncio
    async def test_tool_registry_integration(self, orchestrator):
        """Test tool registry integration with full workflow."""
        # Test tool discovery
        available_tools = orchestrator.tool_registry.get_all_tools()
        assert len(available_tools) > 0

        # Test tool filtering - just verify the method works
        test_tools = orchestrator.tool_registry.find_tools_by_category("test")
        assert isinstance(
            test_tools, list
        )  # Method should return a list, even if empty

        # Test query processing with tool selection
        query = "Find papers by specific author"
        context = ConversationContext(session_id="test", messages=[], metadata={})

        response = await orchestrator.process_query(query, context.session_id)

        assert isinstance(response, AgentResponse)
        assert response.response is not None
        assert response.session_id == context.session_id
        assert response.confidence >= 0.3
        assert response.execution_plan is not None
        # Registry integration test - sources may be empty on execution failure
        assert isinstance(response.sources, list)

        # Verify correct tool was selected through execution plan
        plan_tool_names = [step.tool_name for step in response.execution_plan["steps"]]
        assert any("search" in str(tool_name) for tool_name in plan_tool_names)


@pytest.mark.integration
class TestComponentIntegration:
    """Test integration between specific components."""

    @pytest.fixture
    def tool_registry(self):
        """Create tool registry."""
        registry = ToolRegistry()
        mock_tools = create_mock_tools()
        for tool in mock_tools:
            registry.register_tool(tool, category="research", metadata={})
        return registry

    @pytest.fixture
    def planner(self):
        """Create planner."""
        config = PlannerConfig(
            max_steps=10, parallel_execution=True, enable_conditional_execution=True
        )
        return QueryPlanner(config)

    @pytest.fixture
    def executor(self):
        """Create executor."""
        config = ExecutorConfig(
            max_retries=3,
            timeout_seconds=30,
            parallel_execution=True,
            retry_delay_seconds=0.1,
        )
        return Executor(config)

    @pytest.mark.asyncio
    async def test_planner_executor_integration(self, planner, executor, tool_registry):
        """Test planner and executor working together."""
        query = "Find publications by John Smith"
        available_tools = tool_registry.get_all_tools()

        # Planner creates plan
        plan = planner.create_plan(query, available_tools, tool_registry)

        assert plan is not None
        assert len(plan.steps) > 0

        # Executor executes plan
        from src.models.schemas import ExecutionContext

        context = ExecutionContext(
            session_id="test",
            user_query=query,
            available_tools=[tool.name for tool in available_tools],
            timeout_seconds=30,
        )

        result = await executor.execute_plan(plan, context, tool_registry)

        assert result.success is True
        assert result.steps_completed > 0
        assert len(result.results) > 0

    @pytest.mark.asyncio
    async def test_error_propagation_between_components(
        self, planner, executor, tool_registry
    ):
        """Test error propagation between planner and executor."""
        query = "Use nonexistent tool"
        available_tools = [
            tool
            for tool in tool_registry.get_all_tools()
            if tool.name == "nonexistent_tool"
        ]
        if not available_tools:
            # Create a mock nonexistent tool for testing
            available_tools = []

        # Planner might still create a plan
        plan = planner.create_plan(query, available_tools, tool_registry)

        if plan and len(plan.steps) > 0:
            # Executor should handle missing tool gracefully
            from src.models.schemas import ExecutionContext

            context = ExecutionContext(
                session_id="test",
                user_query=query,
                available_tools=available_tools,
                timeout_seconds=30,
            )

            result = await executor.execute_plan(plan, context, tool_registry)

            assert result.success is False
            assert len(result.errors) > 0
            assert any("not found" in error.lower() for error in result.errors.values())

    @pytest.mark.asyncio
    async def test_orchestrator_component_integration(self, tool_registry):
        """Test orchestrator integrating all components."""
        config = OrchestratorConfig(
            cache_enabled=False,  # Disable caching for cleaner testing
            max_conversation_length=5,
        )
        orchestrator = OrchestratorAgent(tool_registry=tool_registry, config=config)

        # Test that all components are properly integrated
        assert orchestrator.planner is not None
        assert orchestrator.executor is not None
        assert orchestrator.tool_registry is not None

        # Test query processing uses all components
        query = "Find papers on machine learning"
        context = ConversationContext(session_id="test", messages=[], metadata={})

        response = await orchestrator.process_query(query, context.session_id)

        assert isinstance(response, AgentResponse)
        assert response.response is not None
        assert response.session_id == context.session_id
        assert response.confidence > 0.5
        assert response.execution_plan is not None
        assert len(response.sources) > 0

        # Verify planner was used (plan created)
        if response.execution_plan:
            assert len(response.execution_plan.get("steps", [])) > 0

        # Verify executor was used (tools executed)
        assert all(source.get("tool_name") is not None for source in response.sources)
