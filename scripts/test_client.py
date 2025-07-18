#!/usr/bin/env python3
"""
CLI test client for ES Agent system.
Allows programmatic testing of the API without browser interface.
"""

import sys
import asyncio
import json
import argparse
from pathlib import Path
from typing import Dict, Any, Optional
import httpx
import websockets
from datetime import datetime

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class ESAgentTestClient:
    """Test client for ES Agent API."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session_id = None
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def test_health(self) -> Dict[str, Any]:
        """Test health endpoint."""
        print("🔍 Testing health endpoint...")
        try:
            response = await self.client.get(f"{self.base_url}/api/health")
            response.raise_for_status()
            result = response.json()
            print(f"✅ Health check passed: {result['status']}")
            return result
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            raise
    
    async def test_detailed_health(self) -> Dict[str, Any]:
        """Test detailed health endpoint."""
        print("🔍 Testing detailed health endpoint...")
        try:
            response = await self.client.get(f"{self.base_url}/api/health/detailed")
            response.raise_for_status()
            result = response.json()
            print(f"✅ Detailed health check passed: {result['status']}")
            for service, status in result['services'].items():
                print(f"   {service}: {status['status']}")
            return result
        except Exception as e:
            print(f"❌ Detailed health check failed: {e}")
            raise
    
    async def test_chat_rest(self, query: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Test chat endpoint via REST."""
        print(f"🔍 Testing REST chat with query: '{query}'")
        try:
            request_data = {"query": query}
            if session_id:
                request_data["session_id"] = session_id
            
            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            result = response.json()
            
            print(f"✅ REST chat successful")
            print(f"   Response: {result['response'][:100]}...")
            print(f"   Session ID: {result['session_id']}")
            print(f"   Sources: {len(result['sources'])} sources")
            print(f"   Confidence: {result['confidence']}")
            
            # Store session ID for future use
            self.session_id = result['session_id']
            
            return result
        except Exception as e:
            print(f"❌ REST chat failed: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"   Response: {e.response.text}")
            raise
    
    async def test_chat_websocket(self, query: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Test chat endpoint via WebSocket."""
        print(f"🔍 Testing WebSocket chat with query: '{query}'")
        
        # Use existing session ID or generate new one
        if not session_id:
            session_id = self.session_id or f"test_session_{datetime.now().timestamp()}"
        
        ws_url = f"ws://localhost:8000/api/ws?session_id={session_id}"
        
        try:
            async with websockets.connect(ws_url) as websocket:
                print("✅ WebSocket connected")
                
                # Send query
                query_message = {
                    "type": "query",
                    "data": {
                        "query": query,
                        "session_id": session_id
                    }
                }
                await websocket.send(json.dumps(query_message))
                print(f"📤 Query sent: {query}")
                
                # Collect all messages
                messages = []
                final_result = None
                
                try:
                    while True:
                        message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                        data = json.loads(message)
                        messages.append(data)
                        
                        if data['type'] == 'progress':
                            print(f"📊 Progress: {data['message']}")
                            if 'step' in data:
                                print(f"   Step: {data['step']}/{data['total_steps']}")
                        elif data['type'] == 'result':
                            print(f"✅ Final result received")
                            final_result = data['data']
                            break
                        elif data['type'] == 'error':
                            print(f"❌ Error: {data['message']}")
                            raise Exception(f"WebSocket error: {data['message']}")
                        else:
                            print(f"📝 Message: {data['type']}")
                
                except asyncio.TimeoutError:
                    print("⏰ WebSocket timeout - no response received")
                    raise
                
                if final_result:
                    print(f"✅ WebSocket chat successful")
                    print(f"   Response: {final_result['response'][:100]}...")
                    print(f"   Sources: {len(final_result.get('sources', []))} sources")
                    print(f"   Total messages: {len(messages)}")
                    return final_result
                else:
                    raise Exception("No final result received")
                    
        except Exception as e:
            print(f"❌ WebSocket chat failed: {e}")
            raise
    
    async def test_session_management(self) -> Dict[str, Any]:
        """Test session management endpoints."""
        if not self.session_id:
            print("⚠️  No session ID available, creating one with a test query...")
            await self.test_chat_rest("test query for session")
        
        print(f"🔍 Testing session management for session: {self.session_id}")
        
        try:
            # Test get session
            response = await self.client.get(f"{self.base_url}/api/sessions/{self.session_id}")
            response.raise_for_status()
            session_data = response.json()
            
            print(f"✅ Session retrieved successfully")
            print(f"   Session ID: {session_data['session_id']}")
            print(f"   Data: {session_data['data']}")
            
            return session_data
        except Exception as e:
            print(f"❌ Session management failed: {e}")
            raise
    
    async def test_debug_endpoints(self) -> Dict[str, Any]:
        """Test debug endpoints."""
        if not self.session_id:
            print("⚠️  No session ID available, creating one with a test query...")
            await self.test_chat_rest("test query for debug")
        
        print(f"🔍 Testing debug endpoints for session: {self.session_id}")
        
        try:
            # Test conversation export
            response = await self.client.get(f"{self.base_url}/api/debug/conversation/{self.session_id}")
            response.raise_for_status()
            debug_data = response.json()
            
            print(f"✅ Debug conversation export successful")
            print(f"   Session ID: {debug_data['session_id']}")
            print(f"   Conversation entries: {len(debug_data['conversation'])}")
            print(f"   Tool calls: {len(debug_data['tool_calls'])}")
            print(f"   Performance metrics: {debug_data['performance_metrics']}")
            
            return debug_data
        except Exception as e:
            print(f"❌ Debug endpoints failed: {e}")
            raise
    
    async def test_error_scenarios(self):
        """Test various error scenarios."""
        print("🔍 Testing error scenarios...")
        
        # Test empty query
        try:
            print("   Testing empty query...")
            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json={"query": ""},
                headers={"Content-Type": "application/json"}
            )
            if response.status_code != 422:
                print(f"⚠️  Expected 422 for empty query, got {response.status_code}")
            else:
                print("✅ Empty query properly rejected")
        except Exception as e:
            print(f"✅ Empty query properly rejected: {e}")
        
        # Test malformed JSON
        try:
            print("   Testing malformed request...")
            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json={"invalid": "request"},
                headers={"Content-Type": "application/json"}
            )
            if response.status_code != 422:
                print(f"⚠️  Expected 422 for malformed request, got {response.status_code}")
            else:
                print("✅ Malformed request properly rejected")
        except Exception as e:
            print(f"✅ Malformed request properly rejected: {e}")
        
        # Test non-existent session
        try:
            print("   Testing non-existent session...")
            response = await self.client.get(f"{self.base_url}/api/sessions/nonexistent")
            if response.status_code != 404:
                print(f"⚠️  Expected 404 for non-existent session, got {response.status_code}")
            else:
                print("✅ Non-existent session properly handled")
        except Exception as e:
            print(f"✅ Non-existent session properly handled: {e}")

async def main():
    """Main function to run the test client."""
    parser = argparse.ArgumentParser(description='ES Agent Test Client')
    parser.add_argument('--base-url', default='http://localhost:8000', help='Base URL for the API')
    parser.add_argument('--query', help='Test query to send')
    parser.add_argument('--websocket', action='store_true', help='Test WebSocket instead of REST')
    parser.add_argument('--full-test', action='store_true', help='Run full test suite')
    
    args = parser.parse_args()
    
    print(f"🚀 ES Agent Test Client")
    print(f"   Base URL: {args.base_url}")
    print(f"   Time: {datetime.now().isoformat()}")
    print()
    
    async with ESAgentTestClient(args.base_url) as client:
        try:
            if args.full_test:
                print("🔍 Running full test suite...")
                await client.test_health()
                await client.test_detailed_health()
                await client.test_chat_rest("Find publications about machine learning")
                await client.test_chat_websocket("What are the top research topics in AI?")
                await client.test_session_management()
                await client.test_debug_endpoints()
                await client.test_error_scenarios()
                print("\n✅ All tests completed successfully!")
                
            elif args.query:
                if args.websocket:
                    await client.test_chat_websocket(args.query)
                else:
                    await client.test_chat_rest(args.query)
            else:
                # Default: quick health check and simple query
                await client.test_health()
                await client.test_chat_rest("Find publications about machine learning")
                
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())