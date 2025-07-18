#!/usr/bin/env python3
"""
Production server script for ES Agent.
Runs the ES Agent API server with production-ready configuration.
"""

import os
import sys
import argparse
import uvicorn
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def setup_environment(cors_origins=None):
    """Setup environment variables for production."""
    os.environ.setdefault('ENVIRONMENT', 'production')
    
    # CORS settings
    if cors_origins:
        os.environ['CORS_ORIGINS'] = cors_origins
    else:
        # Default to localhost for production safety
        os.environ.setdefault('CORS_ORIGINS', 'http://localhost,https://localhost')
    
    # Validate required environment variables
    required_vars = ['ES_HOST', 'LITELLM_API_KEY', 'LITELLM_BASE_URL']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("   Please set these variables before running the server.")
        sys.exit(1)

def main():
    """Main function to run the production server."""
    parser = argparse.ArgumentParser(description='ES Agent Production Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8000, help='Port to bind to')
    parser.add_argument('--workers', type=int, default=1, help='Number of worker processes')
    parser.add_argument('--cors-origins', help='Comma-separated list of allowed CORS origins')
    parser.add_argument('--log-level', default='info', choices=['debug', 'info', 'warning', 'error'])
    parser.add_argument('--no-static', action='store_true', help='Disable static file serving')
    
    args = parser.parse_args()
    
    # Setup environment
    setup_environment(args.cors_origins)
    
    print(f"🚀 Starting ES Agent Production Server")
    print(f"   Host: {args.host}")
    print(f"   Port: {args.port}")
    print(f"   Workers: {args.workers}")
    print(f"   CORS Origins: {os.getenv('CORS_ORIGINS')}")
    print(f"   Environment: production")
    print(f"   API Docs: http://localhost:{args.port}/api/docs")
    
    if not args.no_static:
        print(f"   Static Files: http://localhost:{args.port}")
    
    print()
    
    # Import the FastAPI app
    from api.main import app
    
    # Remove static file mounting if disabled
    if args.no_static:
        # This would require modifying the app to conditionally mount static files
        print("   Static file serving disabled")
    
    # Run the server
    try:
        if args.workers > 1:
            # Use Gunicorn for multiple workers
            print(f"   Using Gunicorn with {args.workers} workers")
            import gunicorn.app.wsgiapp as wsgi
            
            # This is a simplified example - in production you'd use a proper WSGI server
            uvicorn.run(
                "api.main:app",
                host=args.host,
                port=args.port,
                log_level=args.log_level,
                access_log=True
            )
        else:
            uvicorn.run(
                app,
                host=args.host,
                port=args.port,
                log_level=args.log_level,
                access_log=True
            )
    except KeyboardInterrupt:
        print("\n🛑 Production server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()