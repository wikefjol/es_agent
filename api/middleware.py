"""Middleware configuration for FastAPI application."""

import logging
import time
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import os
from typing import Callable

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_middleware(app: FastAPI) -> None:
    """Setup all middleware for the FastAPI application."""
    
    # CORS middleware
    setup_cors_middleware(app)
    
    # Request logging middleware
    setup_logging_middleware(app)
    
    # Trusted host middleware for production
    setup_trusted_host_middleware(app)

def setup_cors_middleware(app: FastAPI) -> None:
    """Configure CORS middleware based on environment."""
    
    # Get allowed origins from environment
    origins = os.getenv("CORS_ORIGINS", "*").split(",")
    
    # In production, be more restrictive
    if os.getenv("ENVIRONMENT") == "production":
        origins = [origin.strip() for origin in origins if origin.strip() != "*"]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    
    logger.info(f"CORS configured for origins: {origins}")

def setup_logging_middleware(app: FastAPI) -> None:
    """Setup request logging middleware."""
    
    @app.middleware("http")
    async def log_requests(request: Request, call_next: Callable) -> Response:
        """Log all HTTP requests with timing."""
        start_time = time.time()
        
        # Log request
        logger.info(f"Request: {request.method} {request.url}")
        
        # Process request
        response = await call_next(request)
        
        # Log response with timing
        process_time = time.time() - start_time
        logger.info(
            f"Response: {response.status_code} "
            f"({process_time:.3f}s) "
            f"{request.method} {request.url}"
        )
        
        # Add timing header
        response.headers["X-Process-Time"] = str(process_time)
        
        return response

def setup_trusted_host_middleware(app: FastAPI) -> None:
    """Setup trusted host middleware for production."""
    
    # Only enable in production
    if os.getenv("ENVIRONMENT") == "production":
        allowed_hosts = os.getenv("ALLOWED_HOSTS", "").split(",")
        if allowed_hosts and allowed_hosts[0]:  # Not empty
            app.add_middleware(
                TrustedHostMiddleware, 
                allowed_hosts=[host.strip() for host in allowed_hosts]
            )
            logger.info(f"Trusted host middleware enabled for: {allowed_hosts}")