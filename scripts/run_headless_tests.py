#!/usr/bin/env python3
"""
Script to run headless tests against the ES Agent demo app.
This allows testing the app functionality without manual browser interaction.
"""

import asyncio
import json
import sys
import argparse
from pathlib import Path
from typing import Dict, Any
import logging

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.api.test_headless_client import HeadlessTestClient, HeadlessTestSuite

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def run_quick_test(host: str = "localhost", port: int = 8000) -> Dict[str, Any]:
    """Run a quick test to verify the app is working."""
    try:
        async with HeadlessTestClient(host, port) as client:
            # Test health endpoint
            health = await client.test_health_endpoint()
            if health["status"] != 200:
                return {"success": False, "error": f"Health check failed: {health['status']}"}
            
            # Test a simple query
            responses = await client.send_query("Find publications about machine learning")
            
            if not responses:
                return {"success": False, "error": "No responses received"}
            
            result = client.get_result_message()
            if not result:
                return {"success": False, "error": "No result message received"}
            
            return {
                "success": True,
                "response_count": len(responses),
                "duration": client.get_total_duration(),
                "has_result": result is not None,
                "result_preview": result.data.get("response", "")[:100] if result else ""
            }
    except Exception as e:
        return {"success": False, "error": str(e)}

async def run_full_test_suite(host: str = "localhost", port: int = 8000) -> Dict[str, Any]:
    """Run the full test suite."""
    try:
        async with HeadlessTestClient(host, port) as client:
            # Set up progress handler for visibility
            def on_progress(response):
                print(f"  Progress: {response.data.get('message', 'N/A')}")
            
            client.on_progress = on_progress
            
            # Run full test suite
            test_suite = HeadlessTestSuite(client)
            results = await test_suite.run_all_tests()
            
            return results
    except Exception as e:
        return {"success": False, "error": str(e)}

async def run_specific_test(test_name: str, host: str = "localhost", port: int = 8000) -> Dict[str, Any]:
    """Run a specific test."""
    try:
        async with HeadlessTestClient(host, port) as client:
            test_suite = HeadlessTestSuite(client)
            
            # Map test names to methods
            test_methods = {
                "health": test_suite.test_health_endpoints,
                "simple": test_suite.test_simple_query,
                "author": test_suite.test_author_search,
                "complex": test_suite.test_complex_query,
                "error": test_suite.test_error_handling,
                "websocket": test_suite.test_websocket_communication,
                "rest": test_suite.test_rest_api,
                "session": test_suite.test_session_management,
                "progress": test_suite.test_progress_updates,
                "concurrent": test_suite.test_concurrent_queries
            }
            
            if test_name not in test_methods:
                return {"success": False, "error": f"Unknown test: {test_name}"}
            
            test_method = test_methods[test_name]
            result = await test_method()
            
            return {"success": True, "test_result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def interactive_test_session(host: str = "localhost", port: int = 8000):
    """Run an interactive test session."""
    print("🚀 Starting interactive test session...")
    print(f"Server: {host}:{port}")
    print("Type 'quit' to exit\n")
    
    try:
        async with HeadlessTestClient(host, port) as client:
            # Set up progress handler
            def on_progress(response):
                print(f"  💡 Progress: {response.data.get('message', 'N/A')}")
            
            def on_result(response):
                print(f"  ✅ Result: {response.data.get('response', '')[:200]}...")
            
            def on_error(response):
                print(f"  ❌ Error: {response.data.get('message', 'N/A')}")
            
            client.on_progress = on_progress
            client.on_result = on_result
            client.on_error = on_error
            
            # Connect to WebSocket
            session_id = await client.connect_websocket("interactive_session")
            print(f"Connected to session: {session_id}\n")
            
            while True:
                try:
                    query = input("Enter your query (or 'quit' to exit): ")
                    if query.lower() in ['quit', 'exit', 'q']:
                        break
                    
                    if not query.strip():
                        continue
                    
                    print(f"\n🔍 Sending query: {query}")
                    responses = await client.send_query(query)
                    
                    print(f"📊 Received {len(responses)} responses in {client.get_total_duration():.2f}s")
                    
                    # Show summary
                    progress_count = len(client.get_progress_messages())
                    result = client.get_result_message()
                    errors = client.get_error_messages()
                    
                    print(f"   Progress messages: {progress_count}")
                    print(f"   Result: {'✅' if result else '❌'}")
                    print(f"   Errors: {len(errors)}")
                    print()
                    
                except KeyboardInterrupt:
                    print("\n👋 Goodbye!")
                    break
                except Exception as e:
                    print(f"❌ Error: {e}")
                    continue
    
    except Exception as e:
        print(f"Failed to start interactive session: {e}")

def print_results(results: Dict[str, Any], detailed: bool = False):
    """Print test results in a formatted way."""
    if not results.get("success", True):
        print(f"❌ Test failed: {results.get('error', 'Unknown error')}")
        return
    
    if "total_tests" in results:
        # Full test suite results
        print(f"📊 Test Results: {results['passed']}/{results['total_tests']} passed")
        
        if results['failed'] > 0:
            print(f"❌ {results['failed']} tests failed")
            
        if results.get('errors'):
            print("🚨 Errors:")
            for error in results['errors']:
                print(f"   - {error}")
        
        if detailed and results.get('test_results'):
            print("\n📋 Detailed Results:")
            for test_result in results['test_results']:
                name = test_result.get('test_name', 'Unknown')
                passed = test_result.get('passed', False)
                status = "✅" if passed else "❌"
                
                print(f"   {status} {name}")
                
                if not passed and 'error' in test_result:
                    print(f"      Error: {test_result['error']}")
                elif detailed and passed:
                    # Show some details for passed tests
                    if 'duration' in test_result:
                        print(f"      Duration: {test_result['duration']:.2f}s")
                    if 'response_count' in test_result:
                        print(f"      Responses: {test_result['response_count']}")
    else:
        # Single test result
        print(f"✅ Test completed successfully")
        for key, value in results.items():
            if key != "success":
                print(f"   {key}: {value}")

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run headless tests for ES Agent demo app")
    parser.add_argument("--host", default="localhost", help="Server host (default: localhost)")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--mode", choices=["quick", "full", "interactive", "test"], default="quick",
                      help="Test mode (default: quick)")
    parser.add_argument("--test", help="Run specific test (use with --mode test)")
    parser.add_argument("--detailed", action="store_true", help="Show detailed results")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    
    args = parser.parse_args()
    
    print(f"🤖 ES Agent Headless Test Runner")
    print(f"Target: {args.host}:{args.port}")
    print(f"Mode: {args.mode}\n")
    
    try:
        if args.mode == "quick":
            print("🚀 Running quick test...")
            results = await run_quick_test(args.host, args.port)
            
        elif args.mode == "full":
            print("🚀 Running full test suite...")
            results = await run_full_test_suite(args.host, args.port)
            
        elif args.mode == "interactive":
            await interactive_test_session(args.host, args.port)
            return
            
        elif args.mode == "test":
            if not args.test:
                print("❌ --test argument required with --mode test")
                return
            print(f"🚀 Running specific test: {args.test}")
            results = await run_specific_test(args.test, args.host, args.port)
            
        else:
            print("❌ Invalid mode")
            return
        
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print_results(results, args.detailed)
            
    except KeyboardInterrupt:
        print("\n👋 Test interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))

if __name__ == "__main__":
    asyncio.run(main())