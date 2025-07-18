"""Headless testing client for the ES Agent demo app."""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import websockets
import aiohttp
import pytest
from unittest.mock import AsyncMock, patch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TestMessage:
    """Test message for WebSocket communication."""
    type: str
    data: Dict[str, Any]
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp
        }

@dataclass
class TestResponse:
    """Response from the agent system."""
    type: str
    data: Dict[str, Any]
    timestamp: str
    duration: float = 0.0
    
    def is_progress(self) -> bool:
        return self.type == "progress"
    
    def is_result(self) -> bool:
        return self.type == "result"
    
    def is_error(self) -> bool:
        return self.type == "error"

class HeadlessTestClient:
    """Headless test client for the ES Agent demo app."""
    
    def __init__(self, host: str = "localhost", port: int = 8000):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.ws_url = f"ws://{host}:{port}/api/ws"
        self.session = None
        self.websocket = None
        self.responses: List[TestResponse] = []
        self.session_id = None
        
        # Callback handlers
        self.on_progress: Optional[Callable[[TestResponse], None]] = None
        self.on_result: Optional[Callable[[TestResponse], None]] = None
        self.on_error: Optional[Callable[[TestResponse], None]] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
    
    async def connect(self):
        """Connect to the demo server."""
        # Create HTTP session
        self.session = aiohttp.ClientSession()
        
        # Test server health
        try:
            async with self.session.get(f"{self.base_url}/api/health") as response:
                if response.status != 200:
                    raise ConnectionError(f"Server health check failed: {response.status}")
        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from the demo server."""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        
        if self.session:
            await self.session.close()
            self.session = None
    
    async def connect_websocket(self, session_id: str = None) -> str:
        """Connect to WebSocket endpoint."""
        if session_id is None:
            session_id = f"test_session_{int(datetime.utcnow().timestamp())}"
        
        self.session_id = session_id
        ws_url = f"{self.ws_url}?session_id={session_id}"
        
        try:
            self.websocket = await websockets.connect(ws_url)
            logger.info(f"WebSocket connected to {ws_url}")
            return session_id
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            raise
    
    async def send_query(self, query: str, session_id: str = None) -> List[TestResponse]:
        """Send a query and collect all responses."""
        if not self.websocket:
            session_id = await self.connect_websocket(session_id)
        
        # Clear previous responses
        self.responses.clear()
        
        # Send query message
        message = TestMessage(
            type="query",
            data={"query": query, "session_id": session_id or self.session_id}
        )
        
        await self.websocket.send(json.dumps(message.to_dict()))
        logger.info(f"Sent query: {query}")
        
        # Collect responses
        responses = []
        start_time = datetime.utcnow()
        
        try:
            while True:
                response_data = await asyncio.wait_for(
                    self.websocket.recv(), 
                    timeout=30.0
                )
                
                response_dict = json.loads(response_data)
                response = TestResponse(
                    type=response_dict.get("type"),
                    data=response_dict.get("data", {}),
                    timestamp=response_dict.get("timestamp"),
                    duration=(datetime.utcnow() - start_time).total_seconds()
                )
                
                responses.append(response)
                self.responses.append(response)
                
                # Call handlers
                if response.is_progress() and self.on_progress:
                    self.on_progress(response)
                elif response.is_result() and self.on_result:
                    self.on_result(response)
                elif response.is_error() and self.on_error:
                    self.on_error(response)
                
                logger.info(f"Received {response.type}: {response.data.get('message', 'N/A')}")
                
                # Stop on final result or error
                if response.is_result() or (response.is_error() and not response.data.get("recoverable", False)):
                    break
                    
        except asyncio.TimeoutError:
            logger.error("Query timeout - no response received")
            raise
        except Exception as e:
            logger.error(f"Error receiving response: {e}")
            raise
        
        return responses
    
    async def test_health_endpoint(self) -> Dict[str, Any]:
        """Test the health endpoint."""
        async with self.session.get(f"{self.base_url}/api/health") as response:
            return {
                "status": response.status,
                "data": await response.json()
            }
    
    async def test_detailed_health_endpoint(self) -> Dict[str, Any]:
        """Test the detailed health endpoint."""
        async with self.session.get(f"{self.base_url}/api/health/detailed") as response:
            return {
                "status": response.status,
                "data": await response.json()
            }
    
    async def test_chat_endpoint(self, query: str, session_id: str = None) -> Dict[str, Any]:
        """Test the REST chat endpoint."""
        if session_id is None:
            session_id = f"test_rest_session_{int(datetime.utcnow().timestamp())}"
        
        payload = {
            "query": query,
            "session_id": session_id,
            "stream": False
        }
        
        async with self.session.post(
            f"{self.base_url}/api/chat",
            json=payload
        ) as response:
            return {
                "status": response.status,
                "data": await response.json()
            }
    
    def get_progress_messages(self) -> List[TestResponse]:
        """Get all progress messages from the last query."""
        return [r for r in self.responses if r.is_progress()]
    
    def get_result_message(self) -> Optional[TestResponse]:
        """Get the result message from the last query."""
        results = [r for r in self.responses if r.is_result()]
        return results[0] if results else None
    
    def get_error_messages(self) -> List[TestResponse]:
        """Get all error messages from the last query."""
        return [r for r in self.responses if r.is_error()]
    
    def get_total_duration(self) -> float:
        """Get total duration of the last query."""
        if not self.responses:
            return 0.0
        return max(r.duration for r in self.responses)


class HeadlessTestSuite:
    """Comprehensive test suite for headless testing."""
    
    def __init__(self, client: HeadlessTestClient):
        self.client = client
        self.test_results: List[Dict[str, Any]] = []
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all headless tests."""
        results = {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "errors": [],
            "test_results": []
        }
        
        test_methods = [
            self.test_health_endpoints,
            self.test_simple_query,
            self.test_author_search,
            self.test_complex_query,
            self.test_error_handling,
            self.test_websocket_communication,
            self.test_rest_api,
            self.test_session_management,
            self.test_progress_updates,
            self.test_concurrent_queries
        ]
        
        for test_method in test_methods:
            try:
                logger.info(f"Running {test_method.__name__}...")
                test_result = await test_method()
                results["test_results"].append(test_result)
                results["total_tests"] += 1
                
                if test_result["passed"]:
                    results["passed"] += 1
                    logger.info(f"✓ {test_method.__name__} passed")
                else:
                    results["failed"] += 1
                    logger.error(f"✗ {test_method.__name__} failed: {test_result['error']}")
                    
            except Exception as e:
                results["total_tests"] += 1
                results["failed"] += 1
                results["errors"].append(f"{test_method.__name__}: {str(e)}")
                logger.error(f"✗ {test_method.__name__} error: {e}")
        
        return results
    
    async def test_health_endpoints(self) -> Dict[str, Any]:
        """Test health endpoints."""
        try:
            health_result = await self.client.test_health_endpoint()
            detailed_health_result = await self.client.test_detailed_health_endpoint()
            
            assert health_result["status"] == 200
            assert detailed_health_result["status"] == 200
            
            return {
                "test_name": "health_endpoints",
                "passed": True,
                "health_status": health_result["data"],
                "detailed_health_status": detailed_health_result["data"]
            }
        except Exception as e:
            return {
                "test_name": "health_endpoints",
                "passed": False,
                "error": str(e)
            }
    
    async def test_simple_query(self) -> Dict[str, Any]:
        """Test a simple query."""
        try:
            query = "Find publications about machine learning"
            responses = await self.client.send_query(query)
            
            # Verify we got responses
            assert len(responses) > 0
            
            # Verify we got a final result
            result = self.client.get_result_message()
            assert result is not None
            assert result.data.get("response") is not None
            
            return {
                "test_name": "simple_query",
                "passed": True,
                "query": query,
                "response_count": len(responses),
                "duration": self.client.get_total_duration(),
                "final_response": result.data.get("response", "")[:100]
            }
        except Exception as e:
            return {
                "test_name": "simple_query",
                "passed": False,
                "error": str(e)
            }
    
    async def test_author_search(self) -> Dict[str, Any]:
        """Test author search functionality."""
        try:
            query = "Find publications by John Smith"
            responses = await self.client.send_query(query)
            
            # Verify we got responses
            assert len(responses) > 0
            
            # Verify we got a final result
            result = self.client.get_result_message()
            assert result is not None
            
            return {
                "test_name": "author_search",
                "passed": True,
                "query": query,
                "response_count": len(responses),
                "duration": self.client.get_total_duration()
            }
        except Exception as e:
            return {
                "test_name": "author_search",
                "passed": False,
                "error": str(e)
            }
    
    async def test_complex_query(self) -> Dict[str, Any]:
        """Test a complex query that requires multiple tools."""
        try:
            query = "Find publications about artificial intelligence from 2020 to 2023 and summarize the main topics"
            responses = await self.client.send_query(query)
            
            # Verify we got responses
            assert len(responses) > 0
            
            # Verify we got progress updates
            progress_messages = self.client.get_progress_messages()
            assert len(progress_messages) > 0
            
            # Verify we got a final result
            result = self.client.get_result_message()
            assert result is not None
            
            return {
                "test_name": "complex_query",
                "passed": True,
                "query": query,
                "response_count": len(responses),
                "progress_count": len(progress_messages),
                "duration": self.client.get_total_duration()
            }
        except Exception as e:
            return {
                "test_name": "complex_query",
                "passed": False,
                "error": str(e)
            }
    
    async def test_error_handling(self) -> Dict[str, Any]:
        """Test error handling with invalid queries."""
        try:
            query = ""  # Empty query should trigger error
            responses = await self.client.send_query(query)
            
            # Verify we got an error response
            errors = self.client.get_error_messages()
            assert len(errors) > 0
            assert "required" in errors[0].data.get("message", "").lower()
            
            return {
                "test_name": "error_handling",
                "passed": True,
                "query": query,
                "error_count": len(errors),
                "error_message": errors[0].data.get("message", "")
            }
        except Exception as e:
            return {
                "test_name": "error_handling",
                "passed": False,
                "error": str(e)
            }
    
    async def test_websocket_communication(self) -> Dict[str, Any]:
        """Test WebSocket communication patterns."""
        try:
            # Test ping/pong
            ping_message = TestMessage(type="ping", data={})
            await self.client.websocket.send(json.dumps(ping_message.to_dict()))
            
            # Wait for pong
            response_data = await asyncio.wait_for(
                self.client.websocket.recv(), 
                timeout=5.0
            )
            response = json.loads(response_data)
            assert response["type"] == "pong"
            
            return {
                "test_name": "websocket_communication",
                "passed": True,
                "ping_pong": True
            }
        except Exception as e:
            return {
                "test_name": "websocket_communication",
                "passed": False,
                "error": str(e)
            }
    
    async def test_rest_api(self) -> Dict[str, Any]:
        """Test REST API endpoints."""
        try:
            query = "Find publications about deep learning"
            result = await self.client.test_chat_endpoint(query)
            
            assert result["status"] == 200
            assert "response" in result["data"]
            
            return {
                "test_name": "rest_api",
                "passed": True,
                "query": query,
                "response_status": result["status"],
                "has_response": "response" in result["data"]
            }
        except Exception as e:
            return {
                "test_name": "rest_api",
                "passed": False,
                "error": str(e)
            }
    
    async def test_session_management(self) -> Dict[str, Any]:
        """Test session management across multiple queries."""
        try:
            session_id = "test_session_management"
            
            # First query
            query1 = "Find publications about machine learning"
            responses1 = await self.client.send_query(query1, session_id)
            
            # Second query in same session
            query2 = "How many publications were found?"
            responses2 = await self.client.send_query(query2, session_id)
            
            # Verify both queries got responses
            assert len(responses1) > 0
            assert len(responses2) > 0
            
            return {
                "test_name": "session_management",
                "passed": True,
                "session_id": session_id,
                "query1_responses": len(responses1),
                "query2_responses": len(responses2)
            }
        except Exception as e:
            return {
                "test_name": "session_management",
                "passed": False,
                "error": str(e)
            }
    
    async def test_progress_updates(self) -> Dict[str, Any]:
        """Test progress update functionality."""
        try:
            query = "Find publications about neural networks and analyze the authors"
            responses = await self.client.send_query(query)
            
            # Verify we got progress updates
            progress_messages = self.client.get_progress_messages()
            assert len(progress_messages) > 0
            
            # Verify progress messages have required fields
            for progress in progress_messages:
                assert "message" in progress.data
                assert "step" in progress.data
                assert "total_steps" in progress.data
            
            return {
                "test_name": "progress_updates",
                "passed": True,
                "query": query,
                "progress_count": len(progress_messages),
                "progress_messages": [p.data.get("message", "") for p in progress_messages]
            }
        except Exception as e:
            return {
                "test_name": "progress_updates",
                "passed": False,
                "error": str(e)
            }
    
    async def test_concurrent_queries(self) -> Dict[str, Any]:
        """Test concurrent query handling."""
        try:
            # Create multiple client connections
            clients = []
            for i in range(3):
                client = HeadlessTestClient(self.client.host, self.client.port)
                await client.connect()
                await client.connect_websocket(f"concurrent_test_{i}")
                clients.append(client)
            
            # Send concurrent queries
            queries = [
                "Find publications about machine learning",
                "Find publications about deep learning",
                "Find publications about neural networks"
            ]
            
            tasks = []
            for i, client in enumerate(clients):
                task = asyncio.create_task(client.send_query(queries[i]))
                tasks.append(task)
            
            # Wait for all responses
            results = await asyncio.gather(*tasks)
            
            # Verify all queries got responses
            for i, responses in enumerate(results):
                assert len(responses) > 0
                result = next((r for r in responses if r.is_result()), None)
                assert result is not None
            
            # Cleanup
            for client in clients:
                await client.disconnect()
            
            return {
                "test_name": "concurrent_queries",
                "passed": True,
                "concurrent_count": len(clients),
                "all_responded": all(len(r) > 0 for r in results)
            }
        except Exception as e:
            return {
                "test_name": "concurrent_queries",
                "passed": False,
                "error": str(e)
            }


# Test fixtures and utilities
@pytest.fixture
async def headless_client():
    """Create a headless test client."""
    client = HeadlessTestClient()
    await client.connect()
    yield client
    await client.disconnect()

@pytest.fixture
async def test_suite(headless_client):
    """Create a test suite with the client."""
    return HeadlessTestSuite(headless_client)


# Example usage
async def main():
    """Example usage of the headless testing client."""
    async with HeadlessTestClient() as client:
        # Set up progress handler
        def on_progress(response: TestResponse):
            print(f"Progress: {response.data.get('message', 'N/A')}")
        
        client.on_progress = on_progress
        
        # Run a test query
        print("Testing simple query...")
        responses = await client.send_query("Find publications about machine learning")
        
        print(f"Received {len(responses)} responses")
        result = client.get_result_message()
        if result:
            print(f"Final result: {result.data.get('response', '')[:200]}...")
        
        # Run test suite
        print("\nRunning full test suite...")
        test_suite = HeadlessTestSuite(client)
        results = await test_suite.run_all_tests()
        
        print(f"Test Results: {results['passed']}/{results['total_tests']} passed")
        if results['errors']:
            print(f"Errors: {results['errors']}")


if __name__ == "__main__":
    asyncio.run(main())