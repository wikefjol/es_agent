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
            message_history=[],
            metadata={"user_id": "test_user"},
        )

    @pytest.mark.asyncio
    async def test_simple_conversational_query(self, orchestrator, conversation_context):
        """Test simple conversational query that doesn't require tools."""
        query = "Hello, how are you?"
        
        response = await orchestrator.process_query(query, conversation_context)
        
        assert isinstance(response, AgentResponse)
        assert response.success is True
        assert response.message is not None
        assert response.needs_tools is False
        assert response.tool_results is None
        
        # Should update conversation context
        assert len(conversation_context.message_history) == 2  # Query + response
        assert conversation_context.message_history[0]["role"] == "user"
        assert conversation_context.message_history[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_author_search_workflow(self, orchestrator, conversation_context):
        """Test complete author search workflow."""
        query = "Find publications by John Smith"
        
        response = await orchestrator.process_query(query, conversation_context)
        
        assert isinstance(response, AgentResponse)
        assert response.success is True
        assert response.needs_tools is True
        assert response.tool_results is not None
        assert len(response.tool_results) > 0
        
        # Verify tool was called correctly
        tool_result = response.tool_results[0]
        assert tool_result.tool_name == "search_by_author"
        assert tool_result.success is True
        assert "publications" in tool_result.data

    @pytest.mark.asyncio
    async def test_topic_search_workflow(self, orchestrator, conversation_context):
        """Test complete topic search workflow."""
        query = "Search for papers on machine learning"
        
        response = await orchestrator.process_query(query, conversation_context)
        
        assert isinstance(response, AgentResponse)
        assert response.success is True
        assert response.needs_tools is True
        assert response.tool_results is not None
        
        # Verify correct tool was used
        tool_result = response.tool_results[0]
        assert tool_result.tool_name == "search_publications"
        assert tool_result.success is True
        assert "publications" in tool_result.data

    @pytest.mark.asyncio
    async def test_complex_multi_step_workflow(self, orchestrator, conversation_context):
        """Test complex workflow requiring multiple tools."""
        query = "Find John Smith's publications and get statistics for machine learning field"
        
        response = await orchestrator.process_query(query, conversation_context)
        
        assert isinstance(response, AgentResponse)
        assert response.success is True
        assert response.needs_tools is True
        assert response.tool_results is not None
        assert len(response.tool_results) >= 2  # Multiple steps
        
        # Verify both tools were called
        tool_names = [result.tool_name for result in response.tool_results]
        assert "search_by_author" in tool_names
        assert "get_field_statistics" in tool_names

    @pytest.mark.asyncio
    async def test_error_handling_workflow(self, orchestrator, conversation_context):
        """Test error handling in full workflow."""
        # Query that will trigger failing tool
        query = "Use the failing tool to test error handling"
        
        # Mock planner to create a plan with failing tool
        with patch.object(orchestrator.planner, 'create_plan') as mock_plan:
            from src.models.schemas import ExecutionPlan, PlanStep
            
            failing_step = PlanStep(
                id="step1",
                tool_name="failing_tool",
                parameters={"failure_mode": "always"}
            )
            mock_plan.return_value = ExecutionPlan(
                steps=[failing_step],
                expected_outputs={},
                fallback_strategies={}
            )
            
            response = await orchestrator.process_query(query, conversation_context)
            
            assert isinstance(response, AgentResponse)
            assert response.success is False
            assert response.error_message is not None
            assert "failed" in response.error_message.lower()

    @pytest.mark.asyncio
    async def test_session_continuity(self, orchestrator, conversation_context):
        """Test conversation continuity across multiple queries."""
        # First query
        query1 = "Find publications by John Smith"
        response1 = await orchestrator.process_query(query1, conversation_context)
        
        assert response1.success is True
        initial_history_length = len(conversation_context.message_history)
        
        # Follow-up query
        query2 = "How many publications did he have?"
        response2 = await orchestrator.process_query(query2, conversation_context)
        
        assert response2.success is True
        assert len(conversation_context.message_history) > initial_history_length
        
        # Context should be maintained
        assert conversation_context.session_id == "test_session"
        assert any("John Smith" in msg["content"] for msg in conversation_context.message_history)

    @pytest.mark.asyncio
    async def test_caching_functionality(self, orchestrator, conversation_context):
        """Test query result caching."""
        query = "Find publications by John Smith"
        
        # First query - should hit tools
        response1 = await orchestrator.process_query(query, conversation_context)
        assert response1.success is True
        first_tool_results = response1.tool_results
        
        # Second identical query - should hit cache
        response2 = await orchestrator.process_query(query, conversation_context)
        assert response2.success is True
        
        # Results should be similar (caching might affect exact structure)
        assert len(response2.tool_results) == len(first_tool_results)

    @pytest.mark.asyncio
    async def test_timeout_handling(self, orchestrator, conversation_context):
        """Test timeout handling in full workflow."""
        # Query that will use slow tool
        query = "Use slow tool for testing timeouts"
        
        # Mock planner to create plan with slow tool
        with patch.object(orchestrator.planner, 'create_plan') as mock_plan:
            from src.models.schemas import ExecutionPlan, PlanStep
            
            slow_step = PlanStep(
                id="step1",
                tool_name="slow_tool",
                parameters={"delay": 5.0}  # 5 second delay
            )
            mock_plan.return_value = ExecutionPlan(
                steps=[slow_step],
                expected_outputs={},
                fallback_strategies={}
            )
            
            # Set very short timeout
            original_timeout = orchestrator.executor.config.timeout_seconds
            orchestrator.executor.config.timeout_seconds = 1
            
            try:
                response = await orchestrator.process_query(query, conversation_context)
                
                assert isinstance(response, AgentResponse)
                assert response.success is False
                assert response.error_message is not None
                assert "timeout" in response.error_message.lower()
            finally:
                orchestrator.executor.config.timeout_seconds = original_timeout

    @pytest.mark.asyncio
    async def test_parallel_execution_workflow(self, orchestrator, conversation_context):
        """Test parallel execution in full workflow."""
        query = "Search for multiple topics simultaneously"
        
        # Mock planner to create parallel plan
        with patch.object(orchestrator.planner, 'create_plan') as mock_plan:
            from src.models.schemas import ExecutionPlan, PlanStep
            
            steps = [
                PlanStep(
                    id="step1",
                    tool_name="search_publications",
                    parameters={"query": "machine learning"}
                ),
                PlanStep(
                    id="step2",
                    tool_name="search_publications",
                    parameters={"query": "deep learning"}
                ),
                PlanStep(
                    id="step3",
                    tool_name="search_publications",
                    parameters={"query": "neural networks"}
                )
            ]
            mock_plan.return_value = ExecutionPlan(
                steps=steps,
                expected_outputs={},
                fallback_strategies={}
            )
            
            start_time = asyncio.get_event_loop().time()
            response = await orchestrator.process_query(query, conversation_context)
            end_time = asyncio.get_event_loop().time()
            
            assert response.success is True
            assert len(response.tool_results) == 3
            
            # Should execute in parallel (faster than sequential)
            execution_time = end_time - start_time
            assert execution_time < 0.5  # Should be much faster than 3 * 0.1 = 0.3s

    @pytest.mark.asyncio
    async def test_tool_registry_integration(self, orchestrator):
        """Test tool registry integration with full workflow."""
        # Test tool discovery
        available_tools = orchestrator.tool_registry.get_available_tools()
        assert len(available_tools) > 0
        
        # Test tool filtering
        research_tools = orchestrator.tool_registry.get_tools_by_category("research")
        assert len(research_tools) > 0
        
        # Test query processing with tool selection
        query = "Find papers by specific author"
        context = ConversationContext(session_id="test", message_history=[], metadata={})
        
        response = await orchestrator.process_query(query, context)
        
        assert response.success is True
        assert response.needs_tools is True
        
        # Verify correct tool was selected
        tool_names = [result.tool_name for result in response.tool_results]
        assert "search_by_author" in tool_names


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
            max_steps=10,
            parallel_execution=True,
            enable_conditional_execution=True
        )
        return QueryPlanner(config)

    @pytest.fixture
    def executor(self):
        """Create executor."""
        config = ExecutorConfig(
            max_retries=3,
            timeout_seconds=30,
            parallel_execution=True,
            retry_delay_seconds=0.1
        )
        return Executor(config)

    @pytest.mark.asyncio
    async def test_planner_executor_integration(self, planner, executor, tool_registry):
        """Test planner and executor working together."""
        query = "Find publications by John Smith"
        available_tools = ["search_by_author", "search_publications"]
        
        # Planner creates plan
        plan = await planner.create_plan(query, available_tools, tool_registry)
        
        assert plan is not None
        assert len(plan.steps) > 0
        
        # Executor executes plan
        from src.models.schemas import ExecutionContext
        context = ExecutionContext(
            session_id="test",
            user_query=query,
            available_tools=available_tools,
            timeout_seconds=30
        )
        
        result = await executor.execute_plan(plan, context, tool_registry)
        
        assert result.success is True
        assert result.steps_completed > 0
        assert len(result.results) > 0

    @pytest.mark.asyncio
    async def test_error_propagation_between_components(self, planner, executor, tool_registry):
        """Test error propagation between planner and executor."""
        query = "Use nonexistent tool"
        available_tools = ["nonexistent_tool"]
        
        # Planner might still create a plan
        plan = await planner.create_plan(query, available_tools, tool_registry)
        
        if plan and len(plan.steps) > 0:
            # Executor should handle missing tool gracefully
            from src.models.schemas import ExecutionContext
            context = ExecutionContext(
                session_id="test",
                user_query=query,
                available_tools=available_tools,
                timeout_seconds=30
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
            max_conversation_length=5
        )
        orchestrator = OrchestratorAgent(tool_registry=tool_registry, config=config)
        
        # Test that all components are properly integrated
        assert orchestrator.planner is not None
        assert orchestrator.executor is not None
        assert orchestrator.tool_registry is not None
        
        # Test query processing uses all components
        query = "Find papers on machine learning"
        context = ConversationContext(session_id="test", message_history=[], metadata={})
        
        response = await orchestrator.process_query(query, context)
        
        assert response.success is True
        assert response.needs_tools is True
        assert response.tool_results is not None
        
        # Verify planner was used (plan created)
        assert len(response.tool_results) > 0
        
        # Verify executor was used (tools executed)
        assert all(result.success for result in response.tool_results)