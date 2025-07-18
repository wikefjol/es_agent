"""WebSocket handlers for real-time communication."""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Any, Optional, Union
import json
import asyncio
import logging
from datetime import datetime
from uuid import uuid4
from enum import Enum

logger = logging.getLogger(__name__)

def json_serializer(obj):
    """Custom JSON serializer for complex objects."""
    if isinstance(obj, Enum):
        return obj.value
    elif hasattr(obj, 'dict'):
        return obj.dict()
    elif hasattr(obj, '__dict__'):
        return obj.__dict__
    else:
        return str(obj)

class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_sessions: Dict[str, str] = {}  # connection_id -> session_id
    
    async def connect(self, websocket: WebSocket, session_id: str) -> str:
        """Accept a WebSocket connection and assign it a connection ID."""
        await websocket.accept()
        connection_id = str(uuid4())
        self.active_connections[connection_id] = websocket
        self.connection_sessions[connection_id] = session_id
        logger.info(f"WebSocket connected: {connection_id} for session {session_id}")
        return connection_id
    
    def disconnect(self, connection_id: str):
        """Remove a WebSocket connection."""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
            if connection_id in self.connection_sessions:
                del self.connection_sessions[connection_id]
            logger.info(f"WebSocket disconnected: {connection_id}")
    
    async def send_personal_message(self, message: Dict[str, Any], connection_id: str):
        """Send a message to a specific connection."""
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            try:
                await websocket.send_text(json.dumps(message, default=json_serializer))
            except Exception as e:
                logger.error(f"Error sending message to {connection_id}: {e}")
                self.disconnect(connection_id)
    
    async def send_to_session(self, message: Dict[str, Any], session_id: str):
        """Send a message to all connections for a session."""
        for connection_id, conn_session_id in self.connection_sessions.items():
            if conn_session_id == session_id:
                await self.send_personal_message(message, connection_id)
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all connections."""
        disconnected = []
        for connection_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(json.dumps(message, default=json_serializer))
            except Exception as e:
                logger.error(f"Error broadcasting to {connection_id}: {e}")
                disconnected.append(connection_id)
        
        # Clean up disconnected connections
        for connection_id in disconnected:
            self.disconnect(connection_id)

# Global connection manager
manager = ConnectionManager()

class ProgressCallback:
    """Callback handler for sending progress updates via WebSocket."""
    
    def __init__(self, connection_id: str):
        self.connection_id = connection_id
        self.step = 0
        self.total_steps = 0
    
    async def on_plan_created(self, plan: Dict[str, Any]):
        """Called when execution plan is created."""
        self.total_steps = len(plan.get("steps", []))
        await self.send_progress(
            "Execution plan created with {} steps".format(self.total_steps),
            details={"plan_id": plan.get("id"), "steps": self.total_steps}
        )
    
    async def on_step_start(self, step: Dict[str, Any]):
        """Called when a step starts executing."""
        self.step += 1
        tool_name = step.get("tool_name", "unknown")
        await self.send_progress(
            f"Running {tool_name}...",
            details={"step": self.step, "tool": tool_name, "parameters": step.get("parameters", {})}
        )
    
    async def on_step_complete(self, step: Dict[str, Any], result: Dict[str, Any]):
        """Called when a step completes."""
        tool_name = step.get("tool_name", "unknown")
        success = result.get("success", False)
        
        if success:
            await self.send_progress(
                f"✓ {tool_name} completed successfully",
                details={"step": self.step, "tool": tool_name, "result_summary": result.get("summary")}
            )
        else:
            await self.send_progress(
                f"✗ {tool_name} failed: {result.get('error', 'Unknown error')}",
                details={"step": self.step, "tool": tool_name, "error": result.get("error")}
            )
    
    async def on_execution_complete(self, final_result: Dict[str, Any]):
        """Called when execution is complete."""
        await self.send_result(final_result)
    
    async def on_error(self, error: str, recoverable: bool = False):
        """Called when an error occurs."""
        await self.send_error(error, recoverable)
    
    async def send_progress(self, message: str, details: Optional[Dict[str, Any]] = None):
        """Send a progress update."""
        await manager.send_personal_message({
            "type": "progress",
            "message": message,
            "step": self.step,
            "total_steps": self.total_steps,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details or {}
        }, self.connection_id)
    
    async def send_result(self, result: Any):
        """Send the final result."""
        from src.models.schemas import AgentResponse
        
        # Convert AgentResponse to dict if needed
        if isinstance(result, AgentResponse):
            result_data = result.dict()
        elif hasattr(result, 'dict'):
            result_data = result.dict()
        else:
            result_data = result
            
        await manager.send_personal_message({
            "type": "result",
            "data": result_data,
            "timestamp": datetime.utcnow().isoformat()
        }, self.connection_id)
    
    async def send_error(self, error: str, recoverable: bool = False):
        """Send an error message."""
        await manager.send_personal_message({
            "type": "error",
            "message": error,
            "recoverable": recoverable,
            "timestamp": datetime.utcnow().isoformat()
        }, self.connection_id)

async def handle_websocket_message(websocket: WebSocket, connection_id: str, message: Dict[str, Any]):
    """Handle incoming WebSocket messages."""
    
    message_type = message.get("type")
    
    if message_type == "query":
        await handle_query_message(websocket, connection_id, message)
    elif message_type == "ping":
        await handle_ping_message(websocket, connection_id)
    elif message_type == "cancel":
        await handle_cancel_message(websocket, connection_id, message)
    else:
        await manager.send_personal_message({
            "type": "error",
            "message": f"Unknown message type: {message_type}",
            "recoverable": True
        }, connection_id)

async def handle_query_message(websocket: WebSocket, connection_id: str, message: Dict[str, Any]):
    """Handle a query message."""
    
    try:
        data = message.get("data", {})
        query = data.get("query")
        session_id = data.get("session_id")
        
        if not query:
            await manager.send_personal_message({
                "type": "error",
                "message": "Query is required",
                "recoverable": True
            }, connection_id)
            return
        
        if not session_id:
            session_id = str(uuid4())
        
        # Create progress callback
        progress_callback = ProgressCallback(connection_id)
        
        # Import here to avoid circular imports
        from src.core.factory import get_configured_orchestrator
        
        # Process query with progress updates
        orchestrator = get_configured_orchestrator()
        result = await orchestrator.process_query(
            query=query,
            session_id=session_id,
            progress_callback=progress_callback
        )
        
        # Send final result
        await progress_callback.on_execution_complete(result)
        
    except Exception as e:
        logger.error(f"Error handling query message: {e}")
        await manager.send_personal_message({
            "type": "error",
            "message": f"Error processing query: {str(e)}",
            "recoverable": False
        }, connection_id)

async def handle_ping_message(websocket: WebSocket, connection_id: str):
    """Handle a ping message."""
    await manager.send_personal_message({
        "type": "pong",
        "timestamp": datetime.utcnow().isoformat()
    }, connection_id)

async def handle_cancel_message(websocket: WebSocket, connection_id: str, message: Dict[str, Any]):
    """Handle a cancel message."""
    # TODO: Implement query cancellation
    await manager.send_personal_message({
        "type": "cancelled",
        "message": "Query cancellation requested",
        "timestamp": datetime.utcnow().isoformat()
    }, connection_id)