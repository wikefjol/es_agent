#!/usr/bin/env python3
"""
Simple test runner for testing the ES Agent app functionality.
This script can be used to quickly verify that the app is working correctly.
"""

import sys
import subprocess
import time
import signal
import os
from pathlib import Path

def start_demo_server():
    """Start the demo server."""
    script_path = Path(__file__).parent / "run_demo.py"
    
    print("🚀 Starting demo server...")
    process = subprocess.Popen(
        [sys.executable, str(script_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        preexec_fn=os.setsid if os.name != 'nt' else None
    )
    
    # Wait for server to start
    time.sleep(5)
    
    return process

def run_headless_tests():
    """Run the headless tests."""
    script_path = Path(__file__).parent / "run_headless_tests.py"
    
    print("🤖 Running headless tests...")
    result = subprocess.run(
        [sys.executable, str(script_path), "--mode", "full", "--detailed"],
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    if result.stderr:
        print("Errors:", result.stderr)
    
    return result.returncode == 0

def run_api_tests():
    """Run the API tests with pytest."""
    test_path = Path(__file__).parent.parent / "tests" / "api"
    
    print("🧪 Running API tests...")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(test_path), "-v"],
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    if result.stderr:
        print("Errors:", result.stderr)
    
    return result.returncode == 0

def main():
    """Main test runner."""
    print("🔧 ES Agent Test Runner")
    print("=" * 50)
    
    # Start demo server
    server_process = None
    try:
        server_process = start_demo_server()
        
        # Run tests
        print("\n📝 Running API unit tests...")
        api_tests_passed = run_api_tests()
        
        print("\n🌐 Running headless integration tests...")
        headless_tests_passed = run_headless_tests()
        
        # Summary
        print("\n" + "=" * 50)
        print("📊 Test Summary:")
        print(f"   API Tests: {'✅ PASSED' if api_tests_passed else '❌ FAILED'}")
        print(f"   Headless Tests: {'✅ PASSED' if headless_tests_passed else '❌ FAILED'}")
        
        if api_tests_passed and headless_tests_passed:
            print("\n🎉 All tests passed! The app is working correctly.")
            return 0
        else:
            print("\n💥 Some tests failed. Please check the output above.")
            return 1
            
    except KeyboardInterrupt:
        print("\n👋 Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Error running tests: {e}")
        return 1
    finally:
        # Clean up server
        if server_process:
            print("\n🛑 Stopping demo server...")
            if os.name != 'nt':
                os.killpg(os.getpgid(server_process.pid), signal.SIGTERM)
            else:
                server_process.terminate()
            server_process.wait()

if __name__ == "__main__":
    sys.exit(main())