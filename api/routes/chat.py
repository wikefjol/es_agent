"""Chat API endpoints."""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import json
from datetime import datetime
from uuid import uuid4

from ..websocket import manager, handle_websocket_message

router = APIRouter()

class ChatRequest(BaseModel):
    """Chat request model."""
    query: str = Field(..., min_length=1, description="The query string cannot be empty")
    session_id: Optional[str] = None
    stream: bool = False

class ChatResponse(BaseModel):
    """Chat response model."""
    response: str
    sources: List[Dict[str, Any]]
    execution_plan: Optional[Dict[str, Any]] = None
    confidence: float
    session_id: str
    timestamp: str

class Source(BaseModel):
    """Source information model."""
    type: str
    title: str
    url: Optional[str] = None
    metadata: Dict[str, Any] = {}

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a chat query and return response."""
    
    try:
        # Generate session ID if not provided
        session_id = request.session_id or str(uuid4())
        
        # Import here to avoid circular imports
        from src.core.factory import get_configured_orchestrator
        
        # Process query
        orchestrator = get_configured_orchestrator()
        result = await orchestrator.process_query(
            query=request.query,
            session_id=session_id
        )
        
        # Format response
        response = ChatResponse(
            response=result.response,
            sources=result.sources,
            execution_plan=result.execution_plan,
            confidence=result.confidence,
            session_id=session_id,
            timestamp=datetime.utcnow().isoformat()
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, session_id: str = None):
    """WebSocket endpoint for real-time chat."""
    
    if not session_id:
        session_id = str(uuid4())
    
    connection_id = await manager.connect(websocket, session_id)
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle message
            await handle_websocket_message(websocket, connection_id, message)
            
    except WebSocketDisconnect:
        manager.disconnect(connection_id)
    except Exception as e:
        # Send error and disconnect
        await manager.send_personal_message({
            "type": "error",
            "message": f"WebSocket error: {str(e)}",
            "recoverable": False
        }, connection_id)
        manager.disconnect(connection_id)

@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session information."""
    
    try:
        from src.core.context_manager import ContextManager
        
        context_manager = ContextManager()
        session_data = await context_manager.get_session_summary(session_id)
        
        return {
            "session_id": session_id,
            "data": session_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Session not found: {str(e)}")

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    
    try:
        from src.core.context_manager import ContextManager
        
        context_manager = ContextManager()
        await context_manager.clear_session(session_id)
        
        return {
            "message": f"Session {session_id} deleted successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting session: {str(e)}")