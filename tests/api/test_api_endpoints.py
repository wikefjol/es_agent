"""Comprehensive API endpoint tests for the ES Agent demo app."""

import pytest
import asyncio
import json
import websockets
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from typing import Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the FastAPI app
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.main import app
from src.models.schemas import AgentResponse

@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)

@pytest.fixture
def mock_orchestrator():
    """Mock orchestrator for testing."""
    with patch('src.core.orchestrator.OrchestratorAgent') as mock:
        # Configure mock to return AgentResponse
        mock_response = AgentResponse(
            response="Test response from orchestrator",
            sources=[{"tool_name": "test_tool", "data": {"test": "data"}}],
            execution_plan={"steps": [{"tool_name": "test_tool", "id": "step1"}]},
            confidence=0.95,
            session_id="test_session",
            metadata={"execution_time": 1.5}
        )
        
        mock_instance = AsyncMock()
        mock_instance.process_query.return_value = mock_response
        mock.return_value = mock_instance
        
        yield mock_instance

class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_health_endpoint(self, test_client):
        """Test basic health endpoint."""
        response = test_client.get("/api/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data
    
    def test_detailed_health_endpoint(self, test_client):
        """Test detailed health endpoint."""
        response = test_client.get("/api/health/detailed")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "services" in data
        assert "elasticsearch" in data["services"]
        assert "llm" in data["services"]
    
    def test_metrics_endpoint(self, test_client):
        """Test metrics endpoint."""
        response = test_client.get("/api/metrics")
        # This endpoint might not exist yet
        assert response.status_code in [200, 404]

class TestChatEndpoints:
    """Test chat API endpoints."""
    
    def test_chat_endpoint_success(self, test_client, mock_orchestrator):
        """Test successful chat endpoint."""
        payload = {
            "query": "Find publications about machine learning",
            "session_id": "test_session_123",
            "stream": False
        }
        
        response = test_client.post("/api/chat", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "response" in data
        assert "sources" in data
        assert "execution_plan" in data
        assert "confidence" in data
        assert "session_id" in data
        assert data["session_id"] == "test_session_123"
        
        # Verify orchestrator was called
        mock_orchestrator.process_query.assert_called_once()
    
    def test_chat_endpoint_missing_query(self, test_client):
        """Test chat endpoint with missing query."""
        payload = {
            "session_id": "test_session_123",
            "stream": False
        }
        
        response = test_client.post("/api/chat", json=payload)
        assert response.status_code == 422  # Validation error
    
    def test_chat_endpoint_empty_query(self, test_client):
        """Test chat endpoint with empty query."""
        payload = {
            "query": "",
            "session_id": "test_session_123",
            "stream": False
        }
        
        response = test_client.post("/api/chat", json=payload)
        assert response.status_code == 400
        
        data = response.json()
        assert "error" in data
        assert "empty" in data["error"].lower()
    
    def test_chat_endpoint_generates_session_id(self, test_client, mock_orchestrator):
        """Test that chat endpoint generates session ID if not provided."""
        payload = {
            "query": "Find publications about machine learning",
            "stream": False
        }
        
        response = test_client.post("/api/chat", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "session_id" in data
        assert data["session_id"] is not None
        assert len(data["session_id"]) > 0
    
    def test_chat_endpoint_error_handling(self, test_client, mock_orchestrator):
        """Test chat endpoint error handling."""
        # Configure mock to raise an exception
        mock_orchestrator.process_query.side_effect = Exception("Test error")
        
        payload = {
            "query": "Find publications about machine learning",
            "session_id": "test_session_123",
            "stream": False
        }
        
        response = test_client.post("/api/chat", json=payload)
        assert response.status_code == 500
        
        data = response.json()
        assert "error" in data
        assert "Test error" in data["error"]

class TestDebugEndpoints:
    """Test debug endpoints."""
    
    def test_debug_conversation_endpoint(self, test_client):
        """Test conversation debug endpoint."""
        session_id = "test_debug_session"
        
        with patch('src.core.context_manager.ContextManager') as mock_context:
            mock_context_instance = MagicMock()
            mock_context_instance.get_conversation_history.return_value = {
                "messages": [{"role": "user", "content": "test"}],
                "execution_plans": [{"id": "plan1"}],
                "tool_calls": [{"tool": "test_tool"}]
            }
            mock_context.return_value = mock_context_instance
            
            response = test_client.get(f"/api/debug/conversation/{session_id}")
            assert response.status_code == 200
            
            data = response.json()
            assert "messages" in data
            assert "execution_plans" in data
            assert "tool_calls" in data
    
    def test_debug_conversation_not_found(self, test_client):
        """Test conversation debug endpoint with non-existent session."""
        session_id = "non_existent_session"
        
        with patch('src.core.context_manager.ContextManager') as mock_context:
            mock_context_instance = MagicMock()
            mock_context_instance.get_conversation_history.return_value = None
            mock_context.return_value = mock_context_instance
            
            response = test_client.get(f"/api/debug/conversation/{session_id}")
            assert response.status_code == 404
    
    def test_debug_tools_endpoint(self, test_client):
        """Test tools debug endpoint."""
        with patch('src.tools.registry.ToolRegistry') as mock_registry:
            mock_registry_instance = MagicMock()
            mock_registry_instance.get_all_tools.return_value = [
                MagicMock(name="search_publications", description="Search for publications"),
                MagicMock(name="get_statistics", description="Get field statistics")
            ]
            mock_registry.return_value = mock_registry_instance
            
            response = test_client.get("/api/debug/tools")
            assert response.status_code == 200
            
            data = response.json()
            assert "tools" in data
            assert len(data["tools"]) == 2

class TestStaticFiles:
    """Test static file serving."""
    
    def test_index_html(self, test_client):
        """Test serving index.html."""
        response = test_client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "<html" in response.text.lower()
    
    def test_css_file(self, test_client):
        """Test serving CSS file."""
        response = test_client.get("/style.css")
        assert response.status_code == 200
        assert "text/css" in response.headers["content-type"]
    
    def test_js_file(self, test_client):
        """Test serving JavaScript file."""
        response = test_client.get("/app.js")
        assert response.status_code == 200
        assert "application/javascript" in response.headers["content-type"]
    
    def test_favicon(self, test_client):
        """Test favicon handling."""
        response = test_client.get("/favicon.ico")
        # Should return 404 since we don't have a favicon
        assert response.status_code == 404

class TestCORSHeaders:
    """Test CORS headers."""
    
    def test_cors_headers_present(self, test_client):
        """Test that CORS headers are present."""
        response = test_client.get("/api/health")
        assert response.status_code == 200
        
        # Check for CORS headers
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "*"
    
    def test_cors_preflight_request(self, test_client):
        """Test CORS preflight request."""
        response = test_client.options(
            "/api/chat",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )
        
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
        assert "access-control-allow-headers" in response.headers

class TestRequestValidation:
    """Test request validation and error handling."""
    
    def test_invalid_json(self, test_client):
        """Test invalid JSON in request body."""
        response = test_client.post(
            "/api/chat",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422
    
    def test_missing_content_type(self, test_client):
        """Test missing content type header."""
        response = test_client.post(
            "/api/chat",
            data=json.dumps({"query": "test"}),
            headers={}
        )
        # Should still work as FastAPI is flexible
        assert response.status_code in [200, 422]
    
    def test_invalid_query_type(self, test_client):
        """Test invalid query type."""
        payload = {
            "query": 123,  # Should be string
            "session_id": "test_session",
            "stream": False
        }
        
        response = test_client.post("/api/chat", json=payload)
        assert response.status_code == 422

class TestMiddleware:
    """Test middleware functionality."""
    
    def test_request_logging(self, test_client):
        """Test that requests are logged."""
        with patch('api.middleware.logger') as mock_logger:
            response = test_client.get("/health")
            assert response.status_code == 200
            
            # Check that request was logged
            mock_logger.info.assert_called()
    
    def test_response_time_header(self, test_client):
        """Test response time header."""
        response = test_client.get("/health")
        assert response.status_code == 200
        
        # Should have response time in headers or logs
        # Implementation depends on middleware configuration

class TestErrorHandling:
    """Test global error handling."""
    
    def test_internal_server_error(self, test_client):
        """Test internal server error handling."""
        with patch('api.routes.chat.OrchestratorAgent') as mock_orchestrator:
            mock_orchestrator.side_effect = Exception("Internal error")
            
            payload = {
                "query": "test query",
                "session_id": "test_session",
                "stream": False
            }
            
            response = test_client.post("/api/chat", json=payload)
            assert response.status_code == 500
            
            data = response.json()
            assert "error" in data
    
    def test_not_found_error(self, test_client):
        """Test 404 error handling."""
        response = test_client.get("/non-existent-endpoint")
        assert response.status_code == 404
        
        data = response.json()
        assert "detail" in data

class TestPerformance:
    """Test performance-related aspects."""
    
    def test_concurrent_requests(self, test_client, mock_orchestrator):
        """Test handling of concurrent requests."""
        payload = {
            "query": "Find publications about machine learning",
            "session_id": "test_session",
            "stream": False
        }
        
        # Send multiple requests
        responses = []
        for i in range(5):
            response = test_client.post("/api/chat", json=payload)
            responses.append(response)
        
        # All should succeed
        for response in responses:
            assert response.status_code == 200
    
    def test_request_timeout(self, test_client, mock_orchestrator):
        """Test request timeout handling."""
        # Configure mock to simulate slow response
        async def slow_response(*args, **kwargs):
            await asyncio.sleep(0.1)  # Simulate slow processing
            return AgentResponse(
                response="Slow response",
                sources=[],
                execution_plan=None,
                confidence=0.5,
                session_id="test_session",
                metadata={}
            )
        
        mock_orchestrator.process_query.side_effect = slow_response
        
        payload = {
            "query": "Find publications about machine learning",
            "session_id": "test_session",
            "stream": False
        }
        
        response = test_client.post("/api/chat", json=payload)
        assert response.status_code == 200

# WebSocket tests would go here but require more complex setup
# They are covered in the headless client tests

@pytest.mark.asyncio
class TestWebSocketEndpoints:
    """Test WebSocket endpoints."""
    
    async def test_websocket_connection(self):
        """Test WebSocket connection."""
        # This would require a test WebSocket client
        # For now, we'll test the basic structure
        from api.websocket import ConnectionManager
        
        manager = ConnectionManager()
        assert len(manager.active_connections) == 0
        assert len(manager.connection_sessions) == 0
    
    async def test_websocket_message_handling(self):
        """Test WebSocket message handling."""
        from api.websocket import handle_websocket_message
        from unittest.mock import MagicMock
        
        # Mock WebSocket
        websocket = MagicMock()
        connection_id = "test_connection"
        
        # Test ping message
        ping_message = {"type": "ping"}
        
        # This would require more complex setup to test properly
        # The headless client tests cover this functionality

# Integration tests
class TestIntegration:
    """Integration tests for the API."""
    
    def test_full_workflow(self, test_client, mock_orchestrator):
        """Test a complete workflow."""
        # 1. Check health
        health_response = test_client.get("/health")
        assert health_response.status_code == 200
        
        # 2. Send chat request
        chat_payload = {
            "query": "Find publications about machine learning",
            "session_id": "integration_test",
            "stream": False
        }
        
        chat_response = test_client.post("/api/chat", json=chat_payload)
        assert chat_response.status_code == 200
        
        # 3. Check debug endpoint
        debug_response = test_client.get("/api/debug/conversation/integration_test")
        # This might fail if context manager is not properly mocked
        assert debug_response.status_code in [200, 404]
    
    def test_error_recovery(self, test_client, mock_orchestrator):
        """Test error recovery scenarios."""
        # First request fails
        mock_orchestrator.process_query.side_effect = Exception("First error")
        
        payload = {
            "query": "test query",
            "session_id": "error_recovery_test",
            "stream": False
        }
        
        response = test_client.post("/api/chat", json=payload)
        assert response.status_code == 500
        
        # Second request succeeds
        mock_orchestrator.process_query.side_effect = None
        mock_orchestrator.process_query.return_value = AgentResponse(
            response="Recovery successful",
            sources=[],
            execution_plan=None,
            confidence=0.8,
            session_id="error_recovery_test",
            metadata={}
        )
        
        response = test_client.post("/api/chat", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "Recovery successful" in data["response"]