"""Orchestrator agent that coordinates planning and execution."""

import re
import time
import uuid
from typing import Dict, Any, List, Optional
from src.core.planner import PlanningAgent
from src.core.executor import Executor
from src.core.context_manager import ContextManager
from src.tools.registry import ToolRegistry
from src.models.schemas import (
    AgentResponse,
    ConversationContext,
    ExecutionContext,
    ExecutorConfig,
)


class OrchestratorAgent:
    """Main orchestrator that routes queries and manages conversation flow."""

    def __init__(
        self,
        planner: Optional[PlanningAgent] = None,
        executor: Optional[Executor] = None,
        tool_registry: Optional[ToolRegistry] = None,
        context_manager: Optional[ContextManager] = None,
        config: Optional[Any] = None,
    ):
        """Initialize the orchestrator agent.

        Args:
            planner: Planning agent instance
            executor: Executor instance
            tool_registry: Tool registry instance
            context_manager: Context manager instance
            config: Configuration object (optional)
        """
        self.planner = planner or PlanningAgent()
        self.executor = executor or Executor(ExecutorConfig())
        self.tool_registry = tool_registry or ToolRegistry()
        self.context_manager = context_manager or ContextManager()
        self._conversation_contexts: Dict[str, ConversationContext] = {}

        # Query patterns that require tools
        self._tool_requiring_patterns = [
            r"find\s+publications?",
            r"search\s+(for|about)",
            r"show\s+me",
            r"get\s+statistics",
            r"how\s+many",
            r"publications?\s+by",
            r"papers?\s+by",
            r"research\s+on",
            r"about\s+([A-Za-z\s]+)",
            r"topics?\s+in",
            r"main\s+topics?",
            r"trends?\s+in",
        ]

        # Simple conversational patterns
        self._conversational_patterns = [
            r"\b(hello|hi|hey)\b",
            r"\bhow\s+are\s+you\b",
            r"\bwhat\s+can\s+you\s+do\b",
            r"\bhelp\b",
            r"\b(thanks?|thank\s+you)\b",
            r"\b(goodbye|bye)\b",
        ]

    async def process_query(self, query: str, session_id: str) -> AgentResponse:
        """Process a user query and return a response.

        Args:
            query: User query string
            session_id: Session identifier

        Returns:
            AgentResponse with response and metadata
        """
        # Get or create conversation context
        context = self._get_or_create_context(session_id)
        context.messages.append({"role": "user", "content": query})

        # Check if query requires tools
        if self._requires_new_tools(query, context):
            return await self._handle_tool_query(query, session_id, context)
        else:
            return await self._handle_conversational_query(query, session_id, context)

    def _requires_new_tools(self, query: str, context: ConversationContext) -> bool:
        """Determine if query requires new tool execution.

        Args:
            query: User query
            context: Conversation context

        Returns:
            True if tools are needed, False otherwise
        """
        query_lower = query.lower()

        # Check if it's a simple conversational query
        for pattern in self._conversational_patterns:
            if re.search(pattern, query_lower):
                return False

        # Check if we have cached results for similar queries
        if self._has_relevant_cached_results(query, context):
            return False

        # Check if query matches tool-requiring patterns
        for pattern in self._tool_requiring_patterns:
            if re.search(pattern, query_lower):
                return True

        # Default to requiring tools for complex queries
        return len(query.split()) > 3

    def _has_relevant_cached_results(
        self, query: str, context: ConversationContext
    ) -> bool:
        """Check if we have relevant cached results for the query.

        Args:
            query: User query
            context: Conversation context

        Returns:
            True if relevant cached results exist
        """
        # Use context manager to find relevant results
        relevant_results = self.context_manager.find_relevant_results(
            session_id=context.session_id, query=query, similarity_threshold=0.8
        )

        if len(relevant_results) > 0:
            return True

        # Fallback to old cached_results for backward compatibility
        query_words = set(query.lower().split())

        for cache_key, cached_result in context.cached_results.items():
            if isinstance(cached_result, dict) and "query" in cached_result:
                cached_words = set(cached_result["query"].lower().split())
                # If more than 70% of words overlap, consider it relevant
                if len(query_words) > 0:
                    overlap = len(query_words & cached_words) / len(query_words)
                    if overlap > 0.7:
                        return True

        return False

    async def _handle_tool_query(
        self, query: str, session_id: str, context: ConversationContext
    ) -> AgentResponse:
        """Handle queries that require tool execution.

        Args:
            query: User query
            session_id: Session identifier
            context: Conversation context

        Returns:
            AgentResponse with tool execution results
        """
        # Get available tools
        available_tools = self.tool_registry.get_all_tools()

        # Create execution plan
        try:
            plan = self.planner.create_plan(
                query=query,
                available_tools=available_tools,
                context=(
                    context.model_dump() if hasattr(context, "model_dump") else None
                ),
            )
        except Exception as e:
            # Handle planner errors gracefully
            return AgentResponse(
                response=f"I encountered an error while planning your request: {str(e)}",
                sources=[],
                execution_plan=None,
                confidence=0.1,
                session_id=session_id,
                metadata={
                    "success": False,
                    "error_type": "planner_error",
                    "error_message": str(e),
                },
            )

        # Create execution context
        exec_context = ExecutionContext(
            session_id=session_id,
            user_query=query,
            available_tools=[tool.name for tool in available_tools],
            timeout_seconds=30,
            parallel_execution=True,
            max_retries=3,
        )

        # Execute the plan
        result = await self.executor.execute_plan(
            plan=plan, context=exec_context, tool_registry=self.tool_registry
        )

        # Cache results using context manager
        cache_key = self.context_manager.store_result(
            session_id=session_id,
            tool_name="orchestrator_query",
            parameters={"query": query},
            result=result,
            metadata={"timestamp": time.time()},
        )

        # Also store in conversation context for backward compatibility
        context.cached_results[cache_key] = {
            "query": query,
            "result": result,
            "timestamp": time.time(),
        }

        # Format response
        response_text = self._format_tool_response(result)

        return AgentResponse(
            response=response_text,
            sources=self._extract_sources(result),
            execution_plan=plan.__dict__ if hasattr(plan, "__dict__") else None,
            confidence=0.8 if result.success else 0.3,
            session_id=session_id,
            metadata={
                "execution_time": result.execution_time,
                "steps_completed": result.steps_completed,
                "steps_total": result.steps_total,
                "success": result.success,
            },
        )

    async def _handle_conversational_query(
        self, query: str, session_id: str, context: ConversationContext
    ) -> AgentResponse:
        """Handle simple conversational queries.

        Args:
            query: User query
            session_id: Session identifier
            context: Conversation context

        Returns:
            AgentResponse with conversational response
        """
        query_lower = query.lower()

        # Simple response patterns
        if re.search(r"hello|hi|hey", query_lower):
            response = "Hello! I'm here to help you search for publications and research data. What would you like to find?"
        elif re.search(r"what\s+can\s+you\s+do", query_lower):
            response = "I can help you search for publications, find papers by specific authors, get research statistics, and analyze publication trends. Just ask me what you're looking for!"
        elif re.search(r"help", query_lower):
            response = "I can help you with:\n- Finding publications by author\n- Searching for papers on specific topics\n- Getting publication statistics\n- Analyzing research trends\n\nJust tell me what you're looking for!"
        elif re.search(r"thanks?|thank\s+you", query_lower):
            response = "You're welcome! Is there anything else I can help you with?"
        elif re.search(r"goodbye|bye", query_lower):
            response = "Goodbye! Feel free to come back anytime if you need help with research queries."
        else:
            response = "I'm here to help with research queries. Could you please specify what publications or research data you're looking for?"

        return AgentResponse(
            response=response,
            sources=[],
            execution_plan=None,
            confidence=0.9,
            session_id=session_id,
            metadata={"type": "conversational"},
        )

    def _get_or_create_context(self, session_id: str) -> ConversationContext:
        """Get or create conversation context for session.

        Args:
            session_id: Session identifier

        Returns:
            ConversationContext for the session
        """
        if session_id not in self._conversation_contexts:
            self._conversation_contexts[session_id] = ConversationContext(
                session_id=session_id,
                messages=[],
                cached_results={},
                summary="",
                metadata={},
            )
        return self._conversation_contexts[session_id]

    def _format_tool_response(self, result) -> str:
        """Format tool execution results into a readable response.

        Args:
            result: ExecutionResult from tool execution

        Returns:
            Formatted response string
        """
        if not result.success:
            return "I encountered an error while processing your request. Please try again or rephrase your query."

        if not result.results:
            return "I couldn't find any results for your query. Please try a different search term."

        # Format results based on available data
        response_parts = []
        for step_id, step_result in result.results.items():
            if hasattr(step_result, "data") and step_result.data:
                if isinstance(step_result.data, list):
                    response_parts.append(f"Found {len(step_result.data)} results.")
                elif isinstance(step_result.data, dict):
                    # Handle structured data from tools
                    if "publications" in step_result.data:
                        publications = step_result.data["publications"]
                        response_parts.append(
                            f"Found {len(publications)} publications."
                        )
                    elif "total_publications" in step_result.data:
                        total = step_result.data["total_publications"]
                        response_parts.append(f"Found {total} total publications.")
                    else:
                        response_parts.append(
                            f"Retrieved information: {step_result.data}"
                        )
                else:
                    response_parts.append(f"Result: {step_result.data}")

        return (
            "\n".join(response_parts)
            if response_parts
            else "Processing completed successfully."
        )

    def _extract_sources(self, result) -> List[Dict[str, Any]]:
        """Extract sources from execution results.

        Args:
            result: ExecutionResult from tool execution

        Returns:
            List of source dictionaries
        """
        sources = []
        for step_id, step_result in result.results.items():
            if hasattr(step_result, "metadata") and step_result.metadata:
                sources.append(
                    {
                        "step_id": step_id,
                        "tool_name": step_result.metadata.get(
                            "tool_name", step_result.metadata.get("tool", "unknown")
                        ),
                        "execution_time": step_result.metadata.get("execution_time", 0),
                    }
                )
        return sources
