"""Tests for the Orchestrator component."""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from src.core.orchestrator import OrchestratorAgent
from src.core.planner import PlanningAgent
from src.core.executor import Executor
from src.tools.registry import ToolRegistry
from src.tools.base import BaseTool, ToolResult
from src.models.schemas import (
    AgentResponse,
    ConversationContext,
    ExecutionPlan,
    ExecutionResult,
    ExecutionContext,
    ExecutorConfig,
    PlanStep,
    OutputSchema,
    FallbackStrategy,
)


class TestOrchestratorAgent:
    """Test cases for OrchestratorAgent class."""
    
    @pytest.fixture
    def mock_planner(self):
        """Create a mock planning agent."""
        planner = Mock(spec=PlanningAgent)
        planner.create_plan = Mock(return_value=ExecutionPlan(
            steps=[
                PlanStep(
                    id="step1",
                    tool_name="search_publications",
                    parameters={"query": "test"}
                )
            ],
            expected_outputs={"step1": OutputSchema(type="json", fields={})},
            fallback_strategies={"step1": FallbackStrategy(strategy_type="retry")}
        ))
        return planner
    
    @pytest.fixture
    def mock_executor(self):
        """Create a mock executor."""
        executor = Mock(spec=Executor)
        executor.execute_plan = AsyncMock(return_value=ExecutionResult(
            plan_id="test_plan",
            success=True,
            results={
                "step1": ToolResult(
                    success=True,
                    data={"publications": ["pub1", "pub2"]},
                    metadata={"tool_name": "search_publications", "execution_time": 0.1}
                )
            },
            errors={},
            execution_time=0.1,
            steps_completed=1,
            steps_total=1
        ))
        return executor
    
    @pytest.fixture
    def mock_tool_registry(self):
        """Create a mock tool registry."""
        registry = Mock(spec=ToolRegistry)
        mock_tool = Mock(spec=BaseTool)
        mock_tool.name = "search_publications"
        mock_tool.description = "Search for publications"
        registry.list_tools = Mock(return_value=[mock_tool])
        registry.get_all_tools = Mock(return_value=[mock_tool])
        return registry
    
    @pytest.fixture
    def orchestrator(self, mock_planner, mock_executor, mock_tool_registry):
        """Create an orchestrator instance with mocks."""
        return OrchestratorAgent(
            planner=mock_planner,
            executor=mock_executor,
            tool_registry=mock_tool_registry
        )
    
    def test_orchestrator_initializes_correctly(self):
        """Test that orchestrator initializes with default components."""
        orchestrator = OrchestratorAgent()
        
        assert orchestrator.planner is not None
        assert orchestrator.executor is not None
        assert orchestrator.tool_registry is not None
        assert orchestrator._conversation_contexts == {}
    
    def test_orchestrator_initializes_with_custom_components(self, mock_planner, mock_executor, mock_tool_registry):
        """Test that orchestrator can be initialized with custom components."""
        orchestrator = OrchestratorAgent(
            planner=mock_planner,
            executor=mock_executor,
            tool_registry=mock_tool_registry
        )
        
        assert orchestrator.planner == mock_planner
        assert orchestrator.executor == mock_executor
        assert orchestrator.tool_registry == mock_tool_registry
    
    @pytest.mark.asyncio
    async def test_orchestrator_identifies_new_query_requiring_tools(self, orchestrator):
        """Test that orchestrator identifies queries requiring tools."""
        query = "find publications by John Smith"
        session_id = "test_session"
        
        response = await orchestrator.process_query(query, session_id)
        
        assert isinstance(response, AgentResponse)
        assert response.session_id == session_id
        assert response.confidence > 0.5
        assert response.execution_plan is not None
        
        # Verify planner was called
        orchestrator.planner.create_plan.assert_called_once()
        
        # Verify executor was called
        orchestrator.executor.execute_plan.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_orchestrator_handles_conversational_queries(self, orchestrator):
        """Test that orchestrator handles simple conversational queries."""
        query = "hello"
        session_id = "test_session"
        
        response = await orchestrator.process_query(query, session_id)
        
        assert isinstance(response, AgentResponse)
        assert response.session_id == session_id
        assert response.confidence > 0.8
        assert response.execution_plan is None
        assert "Hello!" in response.response
        
        # Verify planner was not called
        orchestrator.planner.create_plan.assert_not_called()
        
        # Verify executor was not called
        orchestrator.executor.execute_plan.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_orchestrator_uses_cached_results_for_similar_query(self, orchestrator):
        """Test that orchestrator uses cached results for similar queries."""
        query1 = "find publications by John Smith"
        query2 = "find publications by John Smith"
        session_id = "test_session"
        
        # First query - should use tools
        response1 = await orchestrator.process_query(query1, session_id)
        assert response1.execution_plan is not None
        
        # Second identical query - should use cached results and be conversational
        response2 = await orchestrator.process_query(query2, session_id)
        
        # The second query should be detected as having cached results
        # and should be handled as a conversational query
        context = orchestrator._get_or_create_context(session_id)
        assert len(context.cached_results) > 0  # Results should be cached
        
        # Verify planner was called only once for the first query
        assert orchestrator.planner.create_plan.call_count == 1
    
    @pytest.mark.asyncio
    async def test_orchestrator_handles_clarification_questions(self, orchestrator):
        """Test that orchestrator handles clarification questions."""
        query = "what can you do?"
        session_id = "test_session"
        
        response = await orchestrator.process_query(query, session_id)
        
        assert isinstance(response, AgentResponse)
        assert response.session_id == session_id
        assert response.confidence > 0.8
        assert response.execution_plan is None
        assert "help" in response.response.lower()
        
        # Verify tools were not called
        orchestrator.planner.create_plan.assert_not_called()
        orchestrator.executor.execute_plan.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_orchestrator_maintains_conversation_context(self, orchestrator):
        """Test that orchestrator maintains conversation context."""
        query1 = "hello"
        query2 = "find publications by John Smith"
        session_id = "test_session"
        
        # First query
        await orchestrator.process_query(query1, session_id)
        
        # Second query
        await orchestrator.process_query(query2, session_id)
        
        # Check that context was maintained
        context = orchestrator._get_or_create_context(session_id)
        assert len(context.messages) == 2
        assert context.messages[0]["content"] == query1
        assert context.messages[1]["content"] == query2
    
    @pytest.mark.asyncio
    async def test_orchestrator_handles_invalid_queries(self, orchestrator):
        """Test that orchestrator handles invalid or unclear queries."""
        query = "xyz abc def"
        session_id = "test_session"
        
        response = await orchestrator.process_query(query, session_id)
        
        assert isinstance(response, AgentResponse)
        assert response.session_id == session_id
        assert response.confidence > 0.0
        
        # Should either use tools or provide helpful response
        assert response.response is not None
        assert len(response.response) > 0
    
    def test_requires_new_tools_identifies_tool_queries(self, orchestrator):
        """Test that _requires_new_tools correctly identifies tool-requiring queries."""
        context = ConversationContext(session_id="test", messages=[], cached_results={})
        
        # Tool-requiring queries
        assert orchestrator._requires_new_tools("find publications by John Smith", context) == True
        assert orchestrator._requires_new_tools("search for machine learning papers", context) == True
        assert orchestrator._requires_new_tools("show me research on AI", context) == True
        assert orchestrator._requires_new_tools("get statistics about publications", context) == True
        assert orchestrator._requires_new_tools("how many papers has John written", context) == True
    
    def test_requires_new_tools_identifies_conversational_queries(self, orchestrator):
        """Test that _requires_new_tools correctly identifies conversational queries."""
        context = ConversationContext(session_id="test", messages=[], cached_results={})
        
        # Conversational queries
        assert orchestrator._requires_new_tools("hello", context) == False
        assert orchestrator._requires_new_tools("hi there", context) == False
        assert orchestrator._requires_new_tools("how are you", context) == False
        assert orchestrator._requires_new_tools("what can you do", context) == False
        assert orchestrator._requires_new_tools("help", context) == False
        assert orchestrator._requires_new_tools("thanks", context) == False
        assert orchestrator._requires_new_tools("goodbye", context) == False
    
    def test_has_relevant_cached_results_finds_matches(self, orchestrator):
        """Test that _has_relevant_cached_results finds relevant cached results."""
        context = ConversationContext(
            session_id="test",
            messages=[],
            cached_results={
                "cache1": {
                    "query": "find publications by John Smith",
                    "result": {"data": "some result"}
                }
            }
        )
        
        # Very similar query should find cached result (same length, 4/5 words match = 80%)
        assert orchestrator._has_relevant_cached_results("find publications by John Smith", context) == True
        
        # Different query should not find cached result
        assert orchestrator._has_relevant_cached_results("search for machine learning", context) == False
    
    def test_has_relevant_cached_results_handles_empty_cache(self, orchestrator):
        """Test that _has_relevant_cached_results handles empty cache."""
        context = ConversationContext(session_id="test", messages=[], cached_results={})
        
        assert orchestrator._has_relevant_cached_results("any query", context) == False
    
    def test_get_or_create_context_creates_new_context(self, orchestrator):
        """Test that _get_or_create_context creates new context for new sessions."""
        session_id = "new_session"
        
        context = orchestrator._get_or_create_context(session_id)
        
        assert context.session_id == session_id
        assert len(context.messages) == 0
        assert len(context.cached_results) == 0
        assert context.summary == ""
    
    def test_get_or_create_context_returns_existing_context(self, orchestrator):
        """Test that _get_or_create_context returns existing context for existing sessions."""
        session_id = "existing_session"
        
        # Create context first
        context1 = orchestrator._get_or_create_context(session_id)
        context1.messages.append({"role": "user", "content": "test"})
        
        # Get context again
        context2 = orchestrator._get_or_create_context(session_id)
        
        assert context1 is context2
        assert len(context2.messages) == 1
    
    def test_format_tool_response_handles_success(self, orchestrator):
        """Test that _format_tool_response formats successful results."""
        result = ExecutionResult(
            plan_id="test",
            success=True,
            results={
                "step1": ToolResult(
                    success=True,
                    data=["result1", "result2"],
                    metadata={"tool_name": "search_publications"}
                )
            },
            errors={},
            execution_time=0.1,
            steps_completed=1,
            steps_total=1
        )
        
        response = orchestrator._format_tool_response(result)
        
        assert "Found 2 results" in response
        assert response is not None
        assert len(response) > 0
    
    def test_format_tool_response_handles_failure(self, orchestrator):
        """Test that _format_tool_response handles failed results."""
        result = ExecutionResult(
            plan_id="test",
            success=False,
            results={},
            errors={"step1": "Tool failed"},
            execution_time=0.1,
            steps_completed=0,
            steps_total=1
        )
        
        response = orchestrator._format_tool_response(result)
        
        assert "error" in response.lower()
        assert "try again" in response.lower()
    
    def test_format_tool_response_handles_no_results(self, orchestrator):
        """Test that _format_tool_response handles empty results."""
        result = ExecutionResult(
            plan_id="test",
            success=True,
            results={},
            errors={},
            execution_time=0.1,
            steps_completed=1,
            steps_total=1
        )
        
        response = orchestrator._format_tool_response(result)
        
        assert "couldn't find" in response.lower() or "no results" in response.lower()
    
    def test_extract_sources_from_results(self, orchestrator):
        """Test that _extract_sources extracts sources from execution results."""
        result = ExecutionResult(
            plan_id="test",
            success=True,
            results={
                "step1": ToolResult(
                    success=True,
                    data=["result1"],
                    metadata={"tool_name": "search_publications", "execution_time": 0.1}
                ),
                "step2": ToolResult(
                    success=True,
                    data={"stat": "value"},
                    metadata={"tool_name": "get_statistics", "execution_time": 0.2}
                )
            },
            errors={},
            execution_time=0.3,
            steps_completed=2,
            steps_total=2
        )
        
        sources = orchestrator._extract_sources(result)
        
        assert len(sources) == 2
        assert sources[0]["step_id"] == "step1"
        assert sources[0]["tool_name"] == "search_publications"
        assert sources[0]["execution_time"] == 0.1
        assert sources[1]["step_id"] == "step2"
        assert sources[1]["tool_name"] == "get_statistics"
        assert sources[1]["execution_time"] == 0.2
    
    def test_extract_sources_handles_empty_results(self, orchestrator):
        """Test that _extract_sources handles empty results."""
        result = ExecutionResult(
            plan_id="test",
            success=True,
            results={},
            errors={},
            execution_time=0.1,
            steps_completed=0,
            steps_total=1
        )
        
        sources = orchestrator._extract_sources(result)
        
        assert len(sources) == 0
        assert sources == []
    
    @pytest.mark.asyncio
    async def test_orchestrator_handles_executor_failure(self, orchestrator):
        """Test that orchestrator handles executor failures gracefully."""
        # Configure executor to fail
        orchestrator.executor.execute_plan = AsyncMock(return_value=ExecutionResult(
            plan_id="test_plan",
            success=False,
            results={},
            errors={"step1": "Tool execution failed"},
            execution_time=0.1,
            steps_completed=0,
            steps_total=1
        ))
        
        query = "find publications by John Smith"
        session_id = "test_session"
        
        response = await orchestrator.process_query(query, session_id)
        
        assert isinstance(response, AgentResponse)
        assert response.session_id == session_id
        assert response.confidence < 0.5
        assert "error" in response.response.lower()
        assert response.metadata["success"] == False
    
    @pytest.mark.asyncio
    async def test_orchestrator_caches_tool_results(self, orchestrator):
        """Test that orchestrator caches tool execution results."""
        query = "find publications by John Smith"
        session_id = "test_session"
        
        response = await orchestrator.process_query(query, session_id)
        
        # Check that result was cached
        context = orchestrator._get_or_create_context(session_id)
        assert len(context.cached_results) == 1
        
        # Check cached result structure
        cached_result = list(context.cached_results.values())[0]
        assert cached_result["query"] == query
        assert "result" in cached_result
        assert "timestamp" in cached_result
    
    @pytest.mark.asyncio
    async def test_orchestrator_handles_different_sessions(self, orchestrator):
        """Test that orchestrator handles different sessions independently."""
        query = "find publications by John Smith"
        session1 = "session1"
        session2 = "session2"
        
        response1 = await orchestrator.process_query(query, session1)
        response2 = await orchestrator.process_query(query, session2)
        
        assert response1.session_id == session1
        assert response2.session_id == session2
        
        # Check that contexts are separate
        context1 = orchestrator._get_or_create_context(session1)
        context2 = orchestrator._get_or_create_context(session2)
        
        assert context1 is not context2
        assert len(context1.messages) == 1
        assert len(context2.messages) == 1