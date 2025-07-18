"""FastAPI application for ES Agent system."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from pathlib import Path

from .routes import chat, health, debug
from .middleware import setup_middleware

# Create FastAPI app
app = FastAPI(
    title="ES Agent API",
    description="Adaptive Plan-and-Execute Agent System for Academic Research",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

@app.on_event("startup")
async def startup_event():
    """Reset orchestrator on startup to pick up environment variables."""
    from src.core.factory import reset_orchestrator
    reset_orchestrator()
    print("✅ Orchestrator reset on startup to pick up environment variables")

# Setup middleware
setup_middleware(app)

# Include routers
app.include_router(chat.router, prefix="/api")
app.include_router(health.router, prefix="/api")
app.include_router(debug.router, prefix="/api")

# Mount static files for demo interface
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/", StaticFiles(directory=static_path, html=True), name="static")

@app.get("/")
async def root():
    """Root endpoint that serves the demo interface."""
    return {"message": "ES Agent API is running", "docs": "/api/docs"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)