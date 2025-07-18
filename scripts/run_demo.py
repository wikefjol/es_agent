#!/usr/bin/env python3
"""
Demo server script for ES Agent.
Runs a local development server with the built-in demo interface.
"""

import os
import sys
import argparse
import uvicorn
from pathlib import Path
from dotenv import load_dotenv

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def setup_environment():
    """Setup environment variables for demo mode."""
    # Load environment variables from .env file first
    load_dotenv()
    
    os.environ.setdefault('CORS_ORIGINS', '*')
    os.environ.setdefault('ENVIRONMENT', 'production')  # Use production to enable real tools
    
    # Check if we have real Elasticsearch settings from .env
    if os.getenv('ES_HOST') and os.getenv('ES_USER') and os.getenv('ES_PASS'):
        print("✅ Using real Elasticsearch tools from .env file")
        print(f"   ES_HOST: {os.getenv('ES_HOST')}")
        print(f"   ES_USER: {os.getenv('ES_USER')}")
    else:
        print("Warning: ES_HOST, ES_USER, or ES_PASS not set in .env. Will use mock tools for demo.")
        os.environ.setdefault('ES_HOST', 'localhost')
        os.environ.setdefault('ES_PORT', '9200')
        os.environ.setdefault('ES_USE_SSL', 'false')
        os.environ.setdefault('ES_VERIFY_CERTS', 'false')
    
    # LLM settings (user must provide these)
    if not os.getenv('LITELLM_API_KEY'):
        print("Warning: LITELLM_API_KEY not set. LLM functionality will be limited.")
    if not os.getenv('LITELLM_BASE_URL'):
        print("Warning: LITELLM_BASE_URL not set. LLM functionality will be limited.")

def main():
    """Main function to run the demo server."""
    parser = argparse.ArgumentParser(description='ES Agent Demo Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8000, help='Port to bind to')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload for development')
    parser.add_argument('--log-level', default='info', choices=['debug', 'info', 'warning', 'error'])
    
    args = parser.parse_args()
    
    # Setup environment
    setup_environment()
    
    print(f"🚀 Starting ES Agent Demo Server")
    print(f"   Host: {args.host}")
    print(f"   Port: {args.port}")
    print(f"   Environment: demo")
    print(f"   Demo URL: http://localhost:{args.port}")
    print(f"   API Docs: http://localhost:{args.port}/api/docs")
    print()
    
    # Import the FastAPI app
    from api.main import app
    
    # Run the server
    try:
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level=args.log_level,
            access_log=True
        )
    except KeyboardInterrupt:
        print("\n🛑 Demo server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()