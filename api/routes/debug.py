"""Debug and development endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import json
from datetime import datetime

router = APIRouter()

class ConversationExport(BaseModel):
    """Model for conversation export."""
    session_id: str
    conversation: List[Dict[str, Any]]
    execution_plans: List[Dict[str, Any]]
    tool_calls: List[Dict[str, Any]]
    performance_metrics: Dict[str, Any]
    exported_at: str

@router.get("/debug/conversation/{session_id}", response_model=ConversationExport)
async def export_conversation(session_id: str):
    """Export conversation data for debugging."""
    
    try:
        # Import here to avoid circular imports
        from src.core.context_manager import ContextManager
        
        context_manager = ContextManager()
        
        # Get conversation data
        conversation_data = await context_manager.get_conversation_history(session_id)
        execution_plans = await context_manager.get_execution_plans(session_id)
        tool_calls = await context_manager.get_tool_calls(session_id)
        
        # Basic performance metrics
        performance_metrics = {
            "total_queries": len(conversation_data),
            "total_tool_calls": len(tool_calls),
            "avg_response_time": 0.0,  # Calculate from actual data
            "cache_hits": 0,  # Get from context manager
            "cache_misses": 0,  # Get from context manager
        }
        
        return ConversationExport(
            session_id=session_id,
            conversation=conversation_data,
            execution_plans=execution_plans,
            tool_calls=tool_calls,
            performance_metrics=performance_metrics,
            exported_at=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Session not found: {str(e)}")

@router.get("/debug/sessions")
async def list_active_sessions():
    """List all active sessions for debugging."""
    
    try:
        from src.core.context_manager import ContextManager
        
        context_manager = ContextManager()
        sessions = await context_manager.list_active_sessions()
        
        return {
            "active_sessions": sessions,
            "total_count": len(sessions),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing sessions: {str(e)}")

@router.post("/debug/clear_session/{session_id}")
async def clear_session(session_id: str):
    """Clear a specific session for debugging."""
    
    try:
        from src.core.context_manager import ContextManager
        
        context_manager = ContextManager()
        await context_manager.clear_session(session_id)
        
        return {
            "message": f"Session {session_id} cleared successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing session: {str(e)}")

@router.get("/debug/system_info")
async def get_system_info():
    """Get system information for debugging."""
    
    import sys
    import platform
    
    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "architecture": platform.architecture(),
        "processor": platform.processor(),
        "timestamp": datetime.utcnow().isoformat()
    }