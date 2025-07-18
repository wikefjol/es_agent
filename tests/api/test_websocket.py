"""Tests for WebSocket functionality - Fixed version."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, Mock, patch
import json
from datetime import datetime
import asyncio

from api.main import app
from api.websocket import ConnectionManager, ProgressCallback, manager

class TestConnectionManager:
    """Test cases for WebSocket connection manager."""
    
    @pytest.fixture
    def connection_manager(self):
        """Create a fresh connection manager for testing."""
        return ConnectionManager()
    
    @pytest.fixture
    def mock_websocket(self):
        """Create mock WebSocket for testing."""
        mock = Mock()
        mock.accept = AsyncMock()
        mock.send_text = AsyncMock()
        return mock
    
    @pytest.mark.asyncio
    async def test_connection_manager_connects_websocket(self, connection_manager, mock_websocket):
        """Test that connection manager accepts and tracks WebSocket connections."""
        # Connect websocket
        connection_id = await connection_manager.connect(mock_websocket, "test-session-123")
        
        # Verify connection was established
        assert connection_id in connection_manager.active_connections
        assert connection_manager.connection_sessions[connection_id] == "test-session-123"
        mock_websocket.accept.assert_called_once()
    
    def test_connection_manager_disconnects_websocket(self, connection_manager, mock_websocket):
        """Test that connection manager properly disconnects WebSocket."""
        # Add connection manually
        connection_id = "test-connection-123"
        connection_manager.active_connections[connection_id] = mock_websocket
        connection_manager.connection_sessions[connection_id] = "test-session-123"
        
        # Disconnect
        connection_manager.disconnect(connection_id)
        
        # Verify connection was removed
        assert connection_id not in connection_manager.active_connections
        assert connection_id not in connection_manager.connection_sessions
    
    @pytest.mark.asyncio
    async def test_connection_manager_sends_personal_message(self, connection_manager, mock_websocket):
        """Test sending message to specific connection."""
        # Setup connection
        connection_id = "test-connection-123"
        connection_manager.active_connections[connection_id] = mock_websocket
        
        # Send message
        test_message = {"type": "test", "data": "hello"}
        await connection_manager.send_personal_message(test_message, connection_id)
        
        # Verify message was sent
        mock_websocket.send_text.assert_called_once_with(json.dumps(test_message))

class TestProgressCallback:
    """Test cases for progress callback functionality."""
    
    @pytest.fixture
    def mock_manager(self):
        """Mock the global manager for testing."""
        mock = Mock()
        mock.send_personal_message = AsyncMock()
        return mock
    
    @pytest.fixture
    def progress_callback(self):
        """Create progress callback."""
        return ProgressCallback("test-connection-123")
    
    @pytest.mark.asyncio
    async def test_progress_callback_on_plan_created(self, progress_callback, mock_manager):
        """Test progress callback when plan is created."""
        # Create test plan
        test_plan = {
            "id": "plan-123",
            "steps": [
                {"id": "step1", "tool_name": "search_publications"},
                {"id": "step2", "tool_name": "get_field_statistics"}
            ]
        }
        
        # Patch the manager
        with patch('api.websocket.manager', mock_manager):
            # Call callback
            await progress_callback.on_plan_created(test_plan)
        
        # Verify progress message was sent
        mock_manager.send_personal_message.assert_called_once()
        call_args = mock_manager.send_personal_message.call_args
        message = call_args[0][0]
        connection_id = call_args[0][1]
        
        assert message["type"] == "progress"
        assert message["message"] == "Execution plan created with 2 steps"
        assert message["step"] == 0
        assert message["total_steps"] == 2
        assert connection_id == "test-connection-123"
    
    @pytest.mark.asyncio
    async def test_progress_callback_on_step_start(self, progress_callback, mock_manager):
        """Test progress callback when step starts."""
        # Set up callback with plan
        progress_callback.total_steps = 3
        
        # Create test step
        test_step = {
            "id": "step1",
            "tool_name": "search_publications",
            "parameters": {"query": "machine learning", "limit": 10}
        }
        
        # Patch the manager
        with patch('api.websocket.manager', mock_manager):
            # Call callback
            await progress_callback.on_step_start(test_step)
        
        # Verify progress message was sent
        mock_manager.send_personal_message.assert_called_once()
        call_args = mock_manager.send_personal_message.call_args
        message = call_args[0][0]
        
        assert message["type"] == "progress"
        assert message["message"] == "Running search_publications..."
        assert message["step"] == 1
        assert message["total_steps"] == 3
        assert message["details"]["tool"] == "search_publications"
        assert message["details"]["parameters"]["query"] == "machine learning"
    
    @pytest.mark.asyncio
    async def test_progress_callback_on_execution_complete(self, progress_callback, mock_manager):
        """Test progress callback when execution completes."""
        # Create test result
        test_result = {
            "response": "Found 15 publications about machine learning",
            "sources": [{"title": "ML Paper 1", "type": "publication"}],
            "confidence": 0.92
        }
        
        # Patch the manager
        with patch('api.websocket.manager', mock_manager):
            # Call callback
            await progress_callback.on_execution_complete(test_result)
        
        # Verify result message was sent
        mock_manager.send_personal_message.assert_called_once()
        call_args = mock_manager.send_personal_message.call_args
        message = call_args[0][0]
        
        assert message["type"] == "result"
        assert message["data"] == test_result
        assert "timestamp" in message

class TestWebSocketHandlers:
    """Test cases for WebSocket message handlers."""
    
    @pytest.fixture
    def mock_websocket(self):
        """Create mock WebSocket for testing."""
        mock = Mock()
        mock.send_text = AsyncMock()
        return mock
    
    @pytest.fixture
    def mock_orchestrator(self):
        """Create mock orchestrator for testing."""
        mock = Mock()
        mock.process_query = AsyncMock(return_value={
            "response": "Test response",
            "sources": [],
            "confidence": 0.8
        })
        return mock
    
    @pytest.mark.asyncio
    async def test_websocket_query_message_processing(self, mock_websocket, mock_orchestrator):
        """Test processing of query messages via WebSocket."""
        from api.websocket import handle_query_message
        
        # Create test message
        test_message = {
            "type": "query",
            "data": {
                "query": "Find machine learning papers",
                "session_id": "test-session-123"
            }
        }
        
        # Mock the orchestrator
        with patch('src.core.orchestrator.OrchestratorAgent', return_value=mock_orchestrator):
            # Handle message
            await handle_query_message(mock_websocket, "conn-123", test_message)
        
        # Verify orchestrator was called
        mock_orchestrator.process_query.assert_called_once()
        call_args = mock_orchestrator.process_query.call_args
        assert call_args[1]["query"] == "Find machine learning papers"
        assert call_args[1]["session_id"] == "test-session-123"
        assert "progress_callback" in call_args[1]
    
    @pytest.mark.asyncio
    async def test_websocket_ping_message(self, mock_websocket):
        """Test handling of ping messages."""
        from api.websocket import handle_ping_message
        
        # Mock the manager
        with patch('api.websocket.manager') as mock_manager:
            mock_manager.send_personal_message = AsyncMock()
            
            # Handle ping
            await handle_ping_message(mock_websocket, "conn-123")
        
        # Verify pong message was sent
        mock_manager.send_personal_message.assert_called_once()
        call_args = mock_manager.send_personal_message.call_args
        message = call_args[0][0]
        
        assert message["type"] == "pong"
        assert "timestamp" in message

class TestWebSocketIntegration:
    """Integration tests for WebSocket functionality."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_websocket_endpoint_connection(self, client):
        """Test basic WebSocket connection."""
        with client.websocket_connect("/api/ws?session_id=test-session-123") as websocket:
            # Send ping
            websocket.send_json({"type": "ping"})
            
            # Receive pong
            data = websocket.receive_json()
            assert data["type"] == "pong"
            assert "timestamp" in data
    
    def test_websocket_invalid_message_type(self, client):
        """Test WebSocket with invalid message type."""
        with client.websocket_connect("/api/ws?session_id=test-session-123") as websocket:
            # Send invalid message type
            websocket.send_json({"type": "invalid_type"})
            
            # Receive error
            data = websocket.receive_json()
            assert data["type"] == "error"
            assert "Unknown message type" in data["message"]
            assert data["recoverable"] is True