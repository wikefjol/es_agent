"""Tests for API routes."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, Mock, patch
import json
from datetime import datetime

from api.main import app

class TestChatRoutes:
    """Test cases for chat API routes."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_orchestrator(self):
        """Mock orchestrator for testing."""
        mock = Mock()
        mock.process_query = AsyncMock(return_value={
            "response": "Test response",
            "sources": [
                {
                    "type": "publication",
                    "title": "Test Publication",
                    "url": "https://example.com",
                    "metadata": {"year": 2023}
                }
            ],
            "execution_plan": {
                "id": "test-plan-123",
                "steps": [
                    {"id": "step1", "tool_name": "search_publications", "parameters": {"query": "test"}}
                ]
            },
            "confidence": 0.85
        })
        return mock
    
    def test_chat_endpoint_requires_query(self, client):
        """Test that chat endpoint requires a query parameter."""
        response = client.post("/api/chat", json={})
        assert response.status_code == 422  # Validation error
        
        response = client.post("/api/chat", json={"query": ""})
        assert response.status_code == 422  # Empty query should fail validation
    
    @patch('src.core.orchestrator.OrchestratorAgent')
    def test_chat_endpoint_processes_query_successfully(self, mock_orchestrator_class, client):
        """Test successful query processing."""
        # Setup mock
        mock_orchestrator = Mock()
        mock_orchestrator.process_query = AsyncMock(return_value={
            "response": "Found 5 publications about machine learning",
            "sources": [
                {
                    "type": "publication",
                    "title": "Machine Learning Advances",
                    "url": "https://example.com/ml",
                    "metadata": {"year": 2023, "authors": ["John Doe"]}
                }
            ],
            "execution_plan": {
                "id": "plan-456",
                "steps": [
                    {"id": "step1", "tool_name": "search_publications", "parameters": {"query": "machine learning"}}
                ]
            },
            "confidence": 0.92
        })
        mock_orchestrator_class.return_value = mock_orchestrator
        
        # Make request
        response = client.post("/api/chat", json={
            "query": "Find machine learning publications",
            "session_id": "test-session-123"
        })
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "Found 5 publications about machine learning"
        assert data["session_id"] == "test-session-123"
        assert data["confidence"] == 0.92
        assert len(data["sources"]) == 1
        assert data["sources"][0]["title"] == "Machine Learning Advances"
        assert data["execution_plan"]["id"] == "plan-456"
        assert "timestamp" in data
        
        # Verify orchestrator was called correctly
        mock_orchestrator.process_query.assert_called_once_with(
            query="Find machine learning publications",
            session_id="test-session-123"
        )
    
    @patch('src.core.orchestrator.OrchestratorAgent')
    def test_chat_endpoint_generates_session_id_if_not_provided(self, mock_orchestrator_class, client):
        """Test that session ID is generated if not provided."""
        # Setup mock
        mock_orchestrator = Mock()
        mock_orchestrator.process_query = AsyncMock(return_value={
            "response": "Test response",
            "sources": [],
            "confidence": 0.5
        })
        mock_orchestrator_class.return_value = mock_orchestrator
        
        # Make request without session_id
        response = client.post("/api/chat", json={
            "query": "Test query"
        })
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert len(data["session_id"]) > 0  # Should have generated a session ID
        
        # Verify orchestrator was called with generated session_id
        mock_orchestrator.process_query.assert_called_once()
        call_args = mock_orchestrator.process_query.call_args
        assert call_args[1]["query"] == "Test query"
        assert len(call_args[1]["session_id"]) > 0
    
    @patch('src.core.orchestrator.OrchestratorAgent')
    def test_chat_endpoint_handles_orchestrator_errors(self, mock_orchestrator_class, client):
        """Test error handling when orchestrator fails."""
        # Setup mock to raise an exception
        mock_orchestrator = Mock()
        mock_orchestrator.process_query = AsyncMock(side_effect=Exception("Orchestrator error"))
        mock_orchestrator_class.return_value = mock_orchestrator
        
        # Make request
        response = client.post("/api/chat", json={
            "query": "Test query"
        })
        
        # Verify error response
        assert response.status_code == 500
        data = response.json()
        assert "Error processing query" in data["detail"]
        assert "Orchestrator error" in data["detail"]
    
    @patch('src.core.context_manager.ContextManager')
    def test_get_session_endpoint(self, mock_context_manager_class, client):
        """Test get session endpoint."""
        # Setup mock
        mock_context_manager = Mock()
        mock_context_manager.get_session_summary = AsyncMock(return_value={
            "queries": 5,
            "last_activity": "2023-12-01T10:00:00Z",
            "tools_used": ["search_publications", "get_field_statistics"]
        })
        mock_context_manager_class.return_value = mock_context_manager
        
        # Make request
        response = client.get("/api/sessions/test-session-123")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session-123"
        assert data["data"]["queries"] == 5
        assert "timestamp" in data
        
        # Verify context manager was called
        mock_context_manager.get_session_summary.assert_called_once_with("test-session-123")
    
    @patch('src.core.context_manager.ContextManager')
    def test_get_session_endpoint_handles_not_found(self, mock_context_manager_class, client):
        """Test get session endpoint when session doesn't exist."""
        # Setup mock to raise an exception
        mock_context_manager = Mock()
        mock_context_manager.get_session_summary = AsyncMock(side_effect=Exception("Session not found"))
        mock_context_manager_class.return_value = mock_context_manager
        
        # Make request
        response = client.get("/api/sessions/nonexistent-session")
        
        # Verify error response
        assert response.status_code == 404
        data = response.json()
        assert "Session not found" in data["detail"]
    
    @patch('src.core.context_manager.ContextManager')
    def test_delete_session_endpoint(self, mock_context_manager_class, client):
        """Test delete session endpoint."""
        # Setup mock
        mock_context_manager = Mock()
        mock_context_manager.clear_session = AsyncMock()
        mock_context_manager_class.return_value = mock_context_manager
        
        # Make request
        response = client.delete("/api/sessions/test-session-123")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "test-session-123 deleted successfully" in data["message"]
        assert "timestamp" in data
        
        # Verify context manager was called
        mock_context_manager.clear_session.assert_called_once_with("test-session-123")
    
    @patch('src.core.context_manager.ContextManager')
    def test_delete_session_endpoint_handles_errors(self, mock_context_manager_class, client):
        """Test delete session endpoint error handling."""
        # Setup mock to raise an exception
        mock_context_manager = Mock()
        mock_context_manager.clear_session = AsyncMock(side_effect=Exception("Delete error"))
        mock_context_manager_class.return_value = mock_context_manager
        
        # Make request
        response = client.delete("/api/sessions/test-session-123")
        
        # Verify error response
        assert response.status_code == 500
        data = response.json()
        assert "Error deleting session" in data["detail"]
        assert "Delete error" in data["detail"]

class TestHealthRoutes:
    """Test cases for health check routes."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_basic_health_check(self, client):
        """Test basic health check endpoint."""
        response = client.get("/api/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"
        assert "timestamp" in data
    
    @patch('src.tools.elasticsearch.client.ElasticsearchClient')
    @patch('src.utils.llm_factory.LLMFactory')
    def test_detailed_health_check_all_healthy(self, mock_llm_factory, mock_es_client_class, client):
        """Test detailed health check when all services are healthy."""
        # Setup mocks
        mock_es_client = Mock()
        mock_es_client.health_check = AsyncMock()
        mock_es_client_class.return_value = mock_es_client
        
        mock_llm_factory.create_orchestrator_llm = Mock()
        
        # Make request
        response = client.get("/api/health/detailed")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["services"]["elasticsearch"]["status"] == "healthy"
        assert data["services"]["llm"]["status"] == "healthy"
        assert data["services"]["redis"]["status"] == "not_configured"
    
    @patch('src.tools.elasticsearch.client.ElasticsearchClient')
    @patch('src.utils.llm_factory.LLMFactory')
    def test_detailed_health_check_with_failures(self, mock_llm_factory, mock_es_client_class, client):
        """Test detailed health check when some services fail."""
        # Setup mocks - ES fails
        mock_es_client = Mock()
        mock_es_client.health_check = AsyncMock(side_effect=Exception("ES connection failed"))
        mock_es_client_class.return_value = mock_es_client
        
        # LLM succeeds
        mock_llm_factory.create_orchestrator_llm = Mock()
        
        # Make request
        response = client.get("/api/health/detailed")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"  # Should be degraded due to ES failure
        assert data["services"]["elasticsearch"]["status"] == "unhealthy"
        assert "ES connection failed" in data["services"]["elasticsearch"]["error"]
        assert data["services"]["llm"]["status"] == "healthy"

class TestDebugRoutes:
    """Test cases for debug routes."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @patch('src.core.context_manager.ContextManager')
    def test_export_conversation(self, mock_context_manager_class, client):
        """Test conversation export endpoint."""
        # Setup mock
        mock_context_manager = Mock()
        mock_context_manager.get_conversation_history = AsyncMock(return_value=[
            {"role": "user", "content": "Test query", "timestamp": "2023-12-01T10:00:00Z"},
            {"role": "assistant", "content": "Test response", "timestamp": "2023-12-01T10:00:05Z"}
        ])
        mock_context_manager.get_execution_plans = AsyncMock(return_value=[
            {"id": "plan-123", "steps": [{"tool_name": "search_publications"}]}
        ])
        mock_context_manager.get_tool_calls = AsyncMock(return_value=[
            {"tool": "search_publications", "parameters": {"query": "test"}, "result": {"success": True}}
        ])
        mock_context_manager_class.return_value = mock_context_manager
        
        # Make request
        response = client.get("/api/debug/conversation/test-session-123")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session-123"
        assert len(data["conversation"]) == 2
        assert len(data["execution_plans"]) == 1
        assert len(data["tool_calls"]) == 1
        assert "performance_metrics" in data
        assert "exported_at" in data
    
    @patch('src.core.context_manager.ContextManager')
    def test_export_conversation_not_found(self, mock_context_manager_class, client):
        """Test conversation export when session doesn't exist."""
        # Setup mock to raise an exception
        mock_context_manager = Mock()
        mock_context_manager.get_conversation_history = AsyncMock(side_effect=Exception("Session not found"))
        mock_context_manager_class.return_value = mock_context_manager
        
        # Make request
        response = client.get("/api/debug/conversation/nonexistent-session")
        
        # Verify error response
        assert response.status_code == 404
        data = response.json()
        assert "Session not found" in data["detail"]
    
    def test_system_info_endpoint(self, client):
        """Test system info endpoint."""
        response = client.get("/api/debug/system_info")
        
        assert response.status_code == 200
        data = response.json()
        assert "python_version" in data
        assert "platform" in data
        assert "architecture" in data
        assert "timestamp" in data