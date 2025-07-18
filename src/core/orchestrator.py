"""Orchestrator agent that coordinates planning and execution."""

import re
import time
import uuid
from typing import Dict, Any, List, Optional
from src.core.planner import PlanningAgent
from src.core.executor import Executor
from src.core.context_manager import ContextManager
from src.tools.registry import ToolRegistry
from src.utils.result_formatter import ResultFormatter
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
        self.result_formatter = ResultFormatter()
        self._conversation_contexts: Dict[str, ConversationContext] = {}

        # Query patterns that require tools
        self._tool_requiring_patterns = [
            r"find\s+publications?",
            r"search\s+(for|about)",
            r"how\s+many\s+(papers?|publications?|articles?)",  # Count queries
            r"(papers?|publications?|articles?)\s+(has|have)\s+.+\s+(published|written)",  # Author count
            r"show\s+me\s+(publications|papers|research)",
            r"get\s+statistics",
            r"how\s+many",
            r"publications?\s+by",
            r"papers?\s+by",
            r"research\s+on\s+\w+",  # More specific: "research on topic"
            r"topics?\s+in",
            r"main\s+topics?",
            r"trends?\s+in",
        ]

        # Conversational patterns (expanded)
        self._conversational_patterns = [
            r"\b(hello|hi|hey)\b",
            r"\bhow\s+are\s+you\b",
            r"\bwhat\s+can\s+you\s+do\b",
            r"\bhelp\b",
            r"\b(thanks?|thank\s+you)\b",
            r"\b(goodbye|bye)\b",
            r"what\s+do\s+you\s+think\s+about",
            r"tell\s+me\s+about",
            r"how\s+do\s+you\s+feel",
            r"what\s+is\s+your\s+opinion",
            r"do\s+you\s+like",
            r"what\s+are\s+your\s+thoughts",
            r"what\s+is\s+it\s+like",  # Philosophical questions
            r"what\s+does\s+it\s+mean",
            r"can\s+you\s+explain",
            r"why\s+is",
            r"how\s+does\s+.+\s+work",  # General knowledge
            r"what\s+is\s+the\s+meaning",
            r"is\s+it\s+true\s+that",
        ]

    async def process_query(self, query: str, session_id: str, progress_callback: Optional[Any] = None) -> AgentResponse:
        """Process a user query and return a response.

        Args:
            query: User query string
            session_id: Session identifier
            progress_callback: Optional callback for progress updates

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

        # Default to conversational unless it's clearly a research query
        # Check for research keywords
        research_keywords = ["publication", "paper", "research", "study", "journal", "conference", "author", "citation", "article"]
        has_research_keywords = any(keyword in query_lower for keyword in research_keywords)
        
        # If query has research keywords but is asking a general question, it's still conversational
        general_question_patterns = [
            r"what\s+is\s+a\s+(publication|paper|research|study)",
            r"what\s+does\s+.+\s+mean",
            r"can\s+you\s+explain",
            r"tell\s+me\s+about\s+(publication|paper|research|study)",
        ]
        
        is_general_question = any(re.search(pattern, query_lower) for pattern in general_question_patterns)
        
        # Require tools only if it has research keywords AND is not a general question
        return has_research_keywords and not is_general_question

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
            plan = await self.planner.create_plan(
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

        # Format response using LLM
        try:
            response_text = await self._format_tool_response_with_llm(query, result)
        except Exception as e:
            print(f"LLM formatting failed, using fallback: {e}")
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
        """Handle conversational queries using LLM.

        Args:
            query: User query
            session_id: Session identifier
            context: Conversation context

        Returns:
            AgentResponse with LLM-generated conversational response
        """
        try:
            # Use LLM to generate natural conversational response
            from src.utils.llm_factory import LLMFactory
            
            llm = LLMFactory.create_orchestrator_llm()
            
            # Build conversation context for the LLM
            conversation_history = ""
            if context.messages:
                # Include last few messages for context
                recent_messages = context.messages[-4:]  # Last 4 messages
                for msg in recent_messages:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    conversation_history += f"{role}: {content}\n"
            
            # Create prompt for conversational response
            prompt = f"""You are a helpful academic research assistant. You have access to a database of 356K academic publications and can search through them when needed.

The user asked: "{query}"

{f"Recent conversation context:\n{conversation_history}" if conversation_history else ""}

This is a conversational query that doesn't require searching through publications right now. 
Respond naturally, helpfully, and conversationally. If appropriate, you can mention that you have access to academic publications and can search for specific research topics if they'd like.

Keep your response friendly, engaging, and focused on being helpful. Don't be overly formal or robotic."""
            
            from langchain_core.messages import HumanMessage
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            response = response.content
            
            return AgentResponse(
                response=response,
                sources=[],
                execution_plan=None,
                confidence=0.9,
                session_id=session_id,
                metadata={"type": "conversational"},
            )
            
        except Exception as e:
            # Better fallback responses based on query type
            error_msg = str(e)
            
            # Provide more conversational fallback responses
            if any(greeting in query.lower() for greeting in ["hi", "hello", "hey", "good morning", "good afternoon"]):
                fallback_response = "Hello! I'm your academic research assistant. I can help you search through a database of over 350,000 academic publications. Try asking me something like 'Find papers about machine learning' or 'Show me research by specific authors'."
            elif any(question in query.lower() for question in ["how are you", "what can you do", "help"]):
                fallback_response = "I'm doing well, thank you! I'm designed to help with academic research. I can search for publications, analyze research trends, and answer questions about scholarly work. What would you like to explore?"
            elif "thank" in query.lower():
                fallback_response = "You're welcome! Feel free to ask me about any academic research topics you're interested in."
            else:
                fallback_response = "I'm here to help with your research needs! I can search through academic publications, find papers by specific authors, or help you explore research topics. What would you like to know about?"
            
            return AgentResponse(
                response=fallback_response,
                sources=[],
                execution_plan=None,
                confidence=0.7,
                session_id=session_id,
                metadata={"type": "conversational", "llm_error": error_msg, "fallback_used": True},
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

    async def _format_tool_response_with_llm(self, query: str, result) -> str:
        """Format tool execution results using LLM for better presentation.
        
        Args:
            query: Original user query
            result: ExecutionResult from tool execution
            
        Returns:
            LLM-formatted response string
        """
        if not result.success:
            return "I encountered an error while processing your request. Please try again or rephrase your query."

        if not result.results:
            return "I couldn't find any results for your query. Please try a different search term."

        # Extract sources for formatting
        sources = self._extract_sources(result)
        
        # Get execution plan if available
        execution_plan = getattr(result, 'execution_plan', None)
        
        # Use the result formatter
        formatted_response = await self.result_formatter.format_search_results(
            query=query,
            sources=sources,
            execution_plan=execution_plan
        )
        
        return formatted_response

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
            source = {
                "step_id": step_id,
                "tool_name": getattr(step_result, "tool_name", "unknown"),
                "execution_time": getattr(step_result, "execution_time", 0),
            }
            
            # Extract the actual data from the step result
            if hasattr(step_result, "data") and step_result.data:
                source["type"] = "search_result"
                source["publications"] = step_result.data
            elif hasattr(step_result, "result") and step_result.result:
                source["type"] = "search_result"
                source["publications"] = step_result.result
            else:
                source["type"] = "metadata_only"
                
            sources.append(source)
        return sources
