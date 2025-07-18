"""Factory functions for creating properly configured agent components."""

import os
import logging
from typing import Optional, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
from src.core.orchestrator import OrchestratorAgent
from src.core.planner import PlanningAgent
from src.core.executor import Executor
from src.core.context_manager import ContextManager
from src.tools.registry import ToolRegistry
from src.tools.base import BaseTool
from src.tools.elasticsearch.publications import SearchPublicationsTool
from src.tools.elasticsearch.client import get_es_client
from src.tools.mock_tools import create_mock_tools
from src.models.schemas import ExecutorConfig

logger = logging.getLogger(__name__)


def create_tool_registry(use_mock_tools: bool = False) -> ToolRegistry:
    """Create and populate a tool registry with available tools.
    
    Args:
        use_mock_tools: If True, use mock tools instead of real ones
        
    Returns:
        Configured ToolRegistry instance
    """
    registry = ToolRegistry()
    
    if use_mock_tools:
        # Use mock tools for testing/development
        mock_tools = create_mock_tools()
        for tool in mock_tools:
            registry.register_tool(tool, category="mock", metadata={"mock": True})
        logger.info(f"Registered {len(mock_tools)} mock tools")
    else:
        # Use real tools for production
        try:
            # Register Elasticsearch publication search tool
            es_client = get_es_client()
            search_tool = SearchPublicationsTool(es_client)
            registry.register_tool(
                search_tool, 
                category="elasticsearch", 
                metadata={"type": "publication_search", "real": True}
            )
            logger.info("Registered real Elasticsearch tools")
        except Exception as e:
            logger.warning(f"Failed to register real tools, falling back to mock tools: {e}")
            # Fall back to mock tools if real tools fail
            mock_tools = create_mock_tools()
            for tool in mock_tools:
                registry.register_tool(tool, category="mock", metadata={"mock": True})
            logger.info(f"Registered {len(mock_tools)} mock tools as fallback")
    
    return registry


def create_orchestrator(
    use_mock_tools: bool = None,
    tool_registry: Optional[ToolRegistry] = None,
    planner: Optional[PlanningAgent] = None,
    executor: Optional[Executor] = None,
    context_manager: Optional[ContextManager] = None,
) -> OrchestratorAgent:
    """Create a fully configured OrchestratorAgent.
    
    Args:
        use_mock_tools: If True, use mock tools. If None, auto-detect based on environment
        tool_registry: Optional pre-configured tool registry
        planner: Optional pre-configured planner
        executor: Optional pre-configured executor
        context_manager: Optional pre-configured context manager
        
    Returns:
        Configured OrchestratorAgent instance
    """
    # Auto-detect tool mode if not specified
    if use_mock_tools is None:
        # Use mock tools if in demo/test environment or if ES credentials are missing
        environment = os.getenv("ENVIRONMENT", "production")
        es_host = os.getenv("ES_HOST")
        use_mock_tools = (
            environment in ["demo", "test"] or 
            not es_host or 
            es_host == "localhost"
        )
    
    # Create tool registry if not provided
    if tool_registry is None:
        tool_registry = create_tool_registry(use_mock_tools=use_mock_tools)
    
    # Create other components with defaults
    if planner is None:
        planner = PlanningAgent()
    
    if executor is None:
        executor = Executor(ExecutorConfig())
    
    if context_manager is None:
        context_manager = ContextManager()
    
    # Create orchestrator
    orchestrator = OrchestratorAgent(
        planner=planner,
        executor=executor,
        tool_registry=tool_registry,
        context_manager=context_manager,
    )
    
    # Log configuration
    available_tools = tool_registry.get_all_tools()
    logger.info(f"Created orchestrator with {len(available_tools)} tools:")
    for tool in available_tools:
        logger.info(f"  - {tool.name}: {tool.description}")
    
    return orchestrator


def get_configured_orchestrator() -> OrchestratorAgent:
    """Get a singleton configured orchestrator instance.
    
    This function provides a cached orchestrator instance that's properly
    configured with tools based on the current environment.
    
    Returns:
        Configured OrchestratorAgent instance
    """
    if not hasattr(get_configured_orchestrator, "_instance"):
        get_configured_orchestrator._instance = create_orchestrator()
    
    return get_configured_orchestrator._instance


def reset_orchestrator():
    """Reset the cached orchestrator instance. Useful for testing."""
    if hasattr(get_configured_orchestrator, "_instance"):
        del get_configured_orchestrator._instance