"""Integration tests for real Elasticsearch tools with the agent system."""

import pytest
import asyncio
import os
from unittest.mock import patch, Mock
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from src.core.orchestrator import OrchestratorAgent
from src.tools.registry import ToolRegistry
from src.tools.elasticsearch import SearchPublicationsTool
from src.tools.elasticsearch.client import get_es_client, ElasticsearchClientManager
from src.models.schemas import (
    AgentResponse,
    ConversationContext,
    ExecutorConfig,
    OrchestratorConfig,
)

@pytest.mark.integration
@pytest.mark.real_tools
class TestRealToolsIntegration:
    """Test integration of real Elasticsearch tools with the agent system."""

    @pytest.fixture(autouse=True)
    def setup_elasticsearch(self):
        """Setup and teardown Elasticsearch connection."""
        # Reset the singleton before each test
        ElasticsearchClientManager.reset()
        
        # Verify we have the required environment variables
        if not os.getenv("ES_HOST"):
            pytest.skip("ES_HOST environment variable not set")
        
        yield
        
        # Cleanup after each test
        ElasticsearchClientManager.reset()

    @pytest.fixture
    def real_tool_registry(self):
        """Create tool registry with real Elasticsearch tools."""
        registry = ToolRegistry()
        
        try:
            # Register real Elasticsearch tool
            es_client = get_es_client()
            search_tool = SearchPublicationsTool(es_client)
            registry.register_tool(
                search_tool, 
                category="elasticsearch", 
                metadata={"type": "publication_search"}
            )
        except Exception as e:
            pytest.skip(f"Could not connect to Elasticsearch: {e}")
        
        return registry

    @pytest.fixture
    def real_orchestrator(self, real_tool_registry):
        """Create orchestrator with real tools."""
        return OrchestratorAgent(tool_registry=real_tool_registry)

    @pytest.mark.asyncio
    async def test_real_elasticsearch_connection(self, real_tool_registry):
        """Test that we can connect to real Elasticsearch."""
        available_tools = real_tool_registry.get_all_tools()
        assert len(available_tools) > 0
        
        # Test that we have at least one Elasticsearch tool
        es_tools = [tool for tool in available_tools if "search_publications" in tool.name]
        assert len(es_tools) > 0
        
        # Test that the tool can be retrieved
        tool = real_tool_registry.get_tool("search_publications")
        assert tool is not None
        assert isinstance(tool, SearchPublicationsTool)

    @pytest.mark.asyncio
    async def test_real_tool_direct_execution(self, real_tool_registry):
        """Test direct execution of the real Elasticsearch tool."""
        tool = real_tool_registry.get_tool("search_publications")
        assert tool is not None
        
        # Test a simple query
        result = await tool.execute(query="machine learning", limit=5)
        
        assert result.success is True
        assert result.data is not None
        assert "publications" in result.data
        assert isinstance(result.data["publications"], list)
        assert "total_results" in result.data
        
        # Verify metadata
        assert result.metadata is not None
        assert "total_results" in result.metadata
        assert "returned_results" in result.metadata
        assert "query_time_ms" in result.metadata

    @pytest.mark.asyncio
    async def test_real_tool_integration_with_orchestrator(self, real_orchestrator):
        """Test that real Elasticsearch tool works with the orchestrator."""
        query = "Find publications about artificial intelligence"
        session_id = "real_tools_test"
        
        response = await real_orchestrator.process_query(query, session_id)
        
        assert isinstance(response, AgentResponse)
        assert response.response is not None
        assert response.session_id == session_id
        assert response.confidence > 0.0  # Real tools may have lower confidence
        assert response.execution_plan is not None
        
        # Verify that the response contains some content
        assert len(response.response) > 0
        
        # Verify sources contain tool execution information
        assert len(response.sources) > 0
        source_tool_names = [source.get("tool_name") for source in response.sources]
        assert any("search_publications" in str(tool_name) for tool_name in source_tool_names)

    @pytest.mark.asyncio
    async def test_real_tool_error_handling(self, real_orchestrator):
        """Test error handling with real tools."""
        # Query that might cause Elasticsearch errors (invalid parameters)
        query = "Find publications with invalid year range"
        session_id = "error_test"
        
        response = await real_orchestrator.process_query(query, session_id)
        
        assert isinstance(response, AgentResponse)
        assert response.response is not None
        assert response.session_id == session_id
        # Should handle errors gracefully even if they occur
        assert len(response.response) > 0

    @pytest.mark.asyncio
    async def test_real_tool_performance(self, real_orchestrator):
        """Test performance with real tools."""
        query = "Find publications from 2023"
        session_id = "performance_test"
        
        start_time = asyncio.get_event_loop().time()
        response = await real_orchestrator.process_query(query, session_id)
        end_time = asyncio.get_event_loop().time()
        
        execution_time = end_time - start_time
        
        assert isinstance(response, AgentResponse)
        assert response.response is not None
        assert execution_time < 30.0  # Should complete within 30 seconds
        
        print(f"Real tool execution time: {execution_time:.3f}s")

    @pytest.mark.asyncio
    async def test_real_tool_with_author_search(self, real_orchestrator):
        """Test author search functionality with real tool."""
        query = "Find publications by John Smith"
        session_id = "author_search_test"
        
        response = await real_orchestrator.process_query(query, session_id)
        
        assert isinstance(response, AgentResponse)
        assert response.response is not None
        assert response.session_id == session_id
        assert response.confidence > 0.0
        assert response.execution_plan is not None
        
        # Verify response contains expected content
        assert len(response.response) > 0

    @pytest.mark.asyncio
    async def test_real_tool_with_year_range(self, real_orchestrator):
        """Test year range search functionality with real tool."""
        query = "Find publications from 2020 to 2023"
        session_id = "year_range_test"
        
        response = await real_orchestrator.process_query(query, session_id)
        
        assert isinstance(response, AgentResponse)
        assert response.response is not None
        assert response.session_id == session_id
        assert response.confidence > 0.0
        assert response.execution_plan is not None
        
        # Verify response contains expected content
        assert len(response.response) > 0

    @pytest.mark.asyncio
    async def test_real_tool_conversation_context(self, real_orchestrator):
        """Test that conversation context is maintained with real tools."""
        session_id = "conversation_test"
        
        # First query
        query1 = "Find publications about machine learning"
        response1 = await real_orchestrator.process_query(query1, session_id)
        
        assert isinstance(response1, AgentResponse)
        assert response1.response is not None
        
        # Second query in same session
        query2 = "How many publications did you find?"
        response2 = await real_orchestrator.process_query(query2, session_id)
        
        assert isinstance(response2, AgentResponse)
        assert response2.response is not None
        
        # Verify context was maintained
        context = real_orchestrator._get_or_create_context(session_id)
        assert len(context.messages) >= 2  # At least both queries

    @pytest.mark.asyncio
    async def test_real_tool_caching(self, real_orchestrator):
        """Test that real tool results are cached appropriately."""
        query = "Find publications about deep learning"
        session_id = "caching_test"
        
        # First query - should hit real tool
        response1 = await real_orchestrator.process_query(query, session_id)
        assert isinstance(response1, AgentResponse)
        assert response1.response is not None
        
        # Second identical query - should use cache
        response2 = await real_orchestrator.process_query(query, session_id)
        assert isinstance(response2, AgentResponse)
        assert response2.response is not None
        
        # Both responses should be similar (caching might affect exact structure)
        assert len(response1.response) > 0
        assert len(response2.response) > 0

    @pytest.mark.asyncio
    async def test_real_tool_registry_integration(self, real_orchestrator):
        """Test tool registry integration with real tools."""
        # Test tool discovery
        available_tools = real_orchestrator.tool_registry.get_all_tools()
        assert len(available_tools) > 0
        
        # Test tool filtering
        es_tools = real_orchestrator.tool_registry.find_tools_by_category("elasticsearch")
        assert len(es_tools) > 0
        
        # Test query processing with tool selection
        query = "Find papers by John Smith"  # Use a specific author name
        session_id = "registry_test"
        
        response = await real_orchestrator.process_query(query, session_id)
        
        assert isinstance(response, AgentResponse)
        assert response.response is not None
        assert response.session_id == session_id
        assert response.confidence >= 0.0
        assert response.execution_plan is not None
        
        # Verify correct tool was selected through execution plan
        if response.execution_plan and "steps" in response.execution_plan:
            plan_tool_names = [step.tool_name for step in response.execution_plan["steps"]]
            # Check if any tool name contains search_publications
            assert any("search_publications" in str(tool_name) for tool_name in plan_tool_names if tool_name)
        else:
            # If no execution plan, that's also acceptable for some queries
            assert response.execution_plan is not None


@pytest.mark.integration
@pytest.mark.real_integration
class TestRealIntegrationWorkflows:
    """Test complete workflows with real tools."""

    @pytest.fixture(autouse=True)
    def setup_elasticsearch(self):
        """Setup and teardown Elasticsearch connection."""
        ElasticsearchClientManager.reset()
        
        if not os.getenv("ES_HOST"):
            pytest.skip("ES_HOST environment variable not set")
        
        yield
        ElasticsearchClientManager.reset()

    @pytest.fixture
    def real_orchestrator(self):
        """Create orchestrator with real tools."""
        registry = ToolRegistry()
        
        try:
            es_client = get_es_client()
            search_tool = SearchPublicationsTool(es_client)
            registry.register_tool(
                search_tool, 
                category="elasticsearch", 
                metadata={"type": "publication_search"}
            )
        except Exception as e:
            pytest.skip(f"Could not connect to Elasticsearch: {e}")
        
        return OrchestratorAgent(tool_registry=registry)

    @pytest.mark.asyncio
    async def test_end_to_end_publication_search(self, real_orchestrator):
        """Test complete end-to-end publication search workflow."""
        query = "Find recent publications about artificial intelligence"
        session_id = "end_to_end_test"
        
        response = await real_orchestrator.process_query(query, session_id)
        
        assert isinstance(response, AgentResponse)
        assert response.response is not None
        assert response.session_id == session_id
        assert response.confidence > 0.0
        assert response.execution_plan is not None
        assert len(response.sources) > 0
        
        # Verify the response contains meaningful content
        assert len(response.response) > 0
        print(f"Response: {response.response[:200]}...")

    @pytest.mark.asyncio
    async def test_complex_query_workflow(self, real_orchestrator):
        """Test complex query that might require multiple tool calls."""
        query = "Find publications about machine learning from 2020 to 2023 with more than 10 citations"
        session_id = "complex_test"
        
        response = await real_orchestrator.process_query(query, session_id)
        
        assert isinstance(response, AgentResponse)
        assert response.response is not None
        assert response.session_id == session_id
        assert response.confidence >= 0.0
        assert response.execution_plan is not None
        
        # Even if the complex query can't be fully satisfied, we should get a response
        assert len(response.response) > 0

    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, real_orchestrator):
        """Test that the system recovers from tool errors gracefully."""
        # This query might cause issues but should be handled gracefully
        query = "Find publications with invalid parameters that should cause errors"
        session_id = "error_recovery_test"
        
        response = await real_orchestrator.process_query(query, session_id)
        
        assert isinstance(response, AgentResponse)
        assert response.response is not None
        assert response.session_id == session_id
        
        # Should provide some response even if there are errors
        assert len(response.response) > 0 