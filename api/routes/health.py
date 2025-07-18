"""Health check endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import asyncio
import os

router = APIRouter()

class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    version: str
    timestamp: str

class DetailedHealthResponse(BaseModel):
    """Detailed health check response model."""
    status: str
    version: str
    timestamp: str
    services: Dict[str, Any]

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Basic health check endpoint."""
    from datetime import datetime
    
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat()
    )

@router.get("/health/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check():
    """Detailed health check including service dependencies."""
    from datetime import datetime
    
    services = {}
    
    # Check Elasticsearch connection
    try:
        # Import here to avoid circular imports
        from src.tools.elasticsearch.client import ElasticsearchClient
        
        es_client = ElasticsearchClient()
        await es_client.health_check()
        services["elasticsearch"] = {"status": "healthy", "connection": "ok"}
    except Exception as e:
        services["elasticsearch"] = {"status": "unhealthy", "error": str(e)}
    
    # Check Redis connection (if configured)
    redis_status = "not_configured"
    if os.getenv("REDIS_URL"):
        try:
            # Add Redis health check when implemented
            redis_status = "healthy"
        except Exception as e:
            redis_status = f"unhealthy: {str(e)}"
    
    services["redis"] = {"status": redis_status}
    
    # Check LLM availability
    try:
        from src.utils.llm_factory import LLMFactory
        
        # Quick test of LLM availability
        llm = LLMFactory.create_orchestrator_llm()
        services["llm"] = {"status": "healthy", "model": "configured"}
    except Exception as e:
        services["llm"] = {"status": "unhealthy", "error": str(e)}
    
    # Overall status
    overall_status = "healthy"
    if any(service.get("status") == "unhealthy" for service in services.values()):
        overall_status = "degraded"
    
    return DetailedHealthResponse(
        status=overall_status,
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat(),
        services=services
    )