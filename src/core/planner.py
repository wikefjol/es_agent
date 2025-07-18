"""Planning agent for creating and adapting execution plans."""

import re
import uuid
import asyncio
from typing import List, Dict, Any, Optional
from src.tools.base import BaseTool, ToolResult
from src.utils.llm_query_parser import LLMQueryParser, QueryIntent
from src.models.schemas import (
    ExecutionPlan,
    PlanStep,
    PlanStepStatus,
    Condition,
    FallbackStrategy,
    OutputSchema,
)


class PlanningAgent:
    """Agent responsible for creating and adapting execution plans."""

    def __init__(self, config: Optional[Any] = None):
        """Initialize the planning agent.

        Args:
            config: Configuration object (optional)
        """
        self.query_parser = LLMQueryParser()
        self._query_patterns = {
            "author_search": [
                r"publications?\s+by\s+([A-Za-z\s]+)",
                r"papers?\s+by\s+([A-Za-z\s]+)",
                r"works?\s+by\s+([A-Za-z\s]+)",
                r"find\s+([A-Za-z\s]+)'s\s+publications?",
                r"search\s+author\s+([A-Za-z\s]+)",
            ],
            "topic_search": [
                r"publications?\s+about\s+([A-Za-z\s]+)",
                r"papers?\s+on\s+([A-Za-z\s]+)",
                r"research\s+on\s+([A-Za-z\s]+)",
                r"find\s+([A-Za-z\s]+)\s+publications?",
                r"search\s+([A-Za-z\s]+)",
            ],
            "statistics": [
                r"how\s+many\s+publications?",
                r"statistics\s+about",
                r"field\s+statistics",
                r"trends?\s+in",
                r"main\s+topics?",
            ],
            "conditional": [
                r"if\s+.*\s+then",
                r"when\s+.*\s+do",
                r"if\s+.*\s+more\s+than\s+(\d+)",
                r"if\s+.*\s+has\s+(\d+)",
            ],
        }

    async def create_plan(
        self, query: str, available_tools: List[BaseTool], context: Optional[Any] = None
    ) -> ExecutionPlan:
        """Create an execution plan for the given query.

        Args:
            query: The user query
            available_tools: List of available tools
            context: Optional context from previous interactions

        Returns:
            ExecutionPlan with steps and configuration
        """
        if not available_tools:
            return ExecutionPlan(
                steps=[],
                expected_outputs={},
                fallback_strategies={},
                metadata={"error": "No tools available"},
            )

        # Parse query to understand intent
        query_analysis = await self._analyze_query(query, context)

        # Create steps based on analysis
        steps = self._create_steps(query_analysis, available_tools)

        # Add dependencies
        self._add_dependencies(steps, query_analysis)

        # Create expected outputs
        expected_outputs = self._create_expected_outputs(steps, query_analysis)

        # Create fallback strategies
        fallback_strategies = self._create_fallback_strategies(steps)

        # Add metadata
        metadata = {
            "query": query,
            "intent": query_analysis.get("intent", "search"),
            "parallel_groups": self._identify_parallel_groups(steps),
        }

        if query_analysis.get("ambiguous"):
            metadata["clarification"] = "Query is ambiguous, using general search"

        return ExecutionPlan(
            steps=steps,
            expected_outputs=expected_outputs,
            fallback_strategies=fallback_strategies,
            metadata=metadata,
        )

    def adapt_plan(
        self,
        original_plan: ExecutionPlan,
        execution_results: List[ToolResult],
        failure_point: int,
    ) -> ExecutionPlan:
        """Adapt plan after tool failure.

        Args:
            original_plan: The original execution plan
            execution_results: Results from executed steps
            failure_point: Index of the failed step

        Returns:
            Adapted ExecutionPlan
        """
        adapted_steps = []

        # Keep successful steps before failure point
        for i in range(failure_point):
            if i < len(original_plan.steps):
                step = original_plan.steps[i]
                step.status = PlanStepStatus.COMPLETED
                if i < len(execution_results):
                    step.result = execution_results[i].data
                adapted_steps.append(step)

        # Handle the failed step
        if failure_point < len(original_plan.steps):
            failed_step = original_plan.steps[failure_point]
            fallback_strategy = original_plan.fallback_strategies.get(
                failed_step.tool_name,
                FallbackStrategy(strategy_type="retry"),  # Default to retry
            )

            if fallback_strategy.strategy_type == "retry":
                # Retry the same step
                retry_step = self._create_retry_step(failed_step)
                adapted_steps.append(retry_step)
            elif fallback_strategy.strategy_type == "alternate_tool":
                # Use alternate tool
                alternate_step = self._create_alternate_step(
                    failed_step, fallback_strategy
                )
                adapted_steps.append(alternate_step)
            # Skip strategy means don't add the step

        # Add remaining steps after failure point
        for i in range(failure_point + 1, len(original_plan.steps)):
            step = original_plan.steps[i]
            # Update dependencies to account for failed step
            step.dependencies = [
                dep
                for dep in step.dependencies
                if dep
                != (
                    original_plan.steps[failure_point].id
                    if failure_point < len(original_plan.steps)
                    else ""
                )
            ]
            adapted_steps.append(step)

        # Keep successful steps after failure point that were already executed
        for i in range(len(execution_results)):
            if i > failure_point and execution_results[i].success:
                if i < len(original_plan.steps):
                    step = original_plan.steps[i]
                    step.status = PlanStepStatus.COMPLETED
                    step.result = execution_results[i].data

        return ExecutionPlan(
            steps=adapted_steps,
            expected_outputs=original_plan.expected_outputs,
            fallback_strategies=original_plan.fallback_strategies,
            metadata={
                **original_plan.metadata,
                "adapted": True,
                "failure_point": failure_point,
                "adaptation_reason": "tool_failure",
            },
        )

    async def _analyze_query(self, query: str, context: Optional[Any]) -> Dict[str, Any]:
        """Analyze the query to understand intent and extract parameters."""
        # Use the enhanced query parser
        parsed = await self.query_parser.parse(query)
        
        analysis = {
            "intent": "search",
            "parameters": {},
            "ambiguous": False,
            "conditional": False,
            "query": query,
            "parsed": parsed,
        }
        
        # Map QueryIntent to planning intent
        if parsed["intent"] == QueryIntent.AUTHOR_SEARCH:
            analysis["intent"] = "author_search"
            if parsed["entities"]["authors"]:
                analysis["parameters"]["author"] = parsed["entities"]["authors"][0]
        elif parsed["intent"] == QueryIntent.COUNT:
            analysis["intent"] = "count"
            if parsed["entities"]["authors"]:
                analysis["parameters"]["author"] = parsed["entities"]["authors"][0]
        elif parsed["intent"] == QueryIntent.TOPIC_SEARCH:
            analysis["intent"] = "topic_search"
            if parsed["entities"]["topics"]:
                analysis["parameters"]["topic"] = parsed["entities"]["topics"][0]
            elif parsed["entities"]["keywords"]:
                analysis["parameters"]["topic"] = " ".join(parsed["entities"]["keywords"])
        
        # Add year filtering if years were extracted
        if parsed["entities"]["years"]:
            analysis["parameters"]["years"] = parsed["entities"]["years"]
            
        # Use fallback to original pattern matching if parser didn't find anything
        query_lower = query.lower()
        if not analysis["parameters"] and analysis["intent"] == "search":
            # Check for author search
            for pattern in self._query_patterns["author_search"]:
                match = re.search(pattern, query_lower)
                if match:
                    analysis["intent"] = "author_search"
                    analysis["parameters"]["author"] = match.group(1).strip()
                    break

        # Check for topic search
        if analysis["intent"] == "search":
            for pattern in self._query_patterns["topic_search"]:
                match = re.search(pattern, query_lower)
                if match:
                    analysis["intent"] = "topic_search"
                    analysis["parameters"]["topic"] = match.group(1).strip()
                    break

        # Check for statistics request
        for pattern in self._query_patterns["statistics"]:
            if re.search(pattern, query_lower):
                analysis["statistics"] = True
                break

        # Also check for explicit statistics keywords in complex queries
        if any(
            keyword in query_lower
            for keyword in ["statistics", "stats", "field", "trends", "analysis"]
        ):
            analysis["statistics"] = True

        # Check for conditional logic
        for pattern in self._query_patterns["conditional"]:
            match = re.search(pattern, query_lower)
            if match:
                analysis["conditional"] = True
                if match.groups():
                    analysis["condition_value"] = match.group(1)
                break

        # Check for context usage
        if context and hasattr(context, "get_previous_results"):
            prev_results = context.get_previous_results()
            if prev_results and "same author" in query_lower:
                analysis["intent"] = "author_search"
                analysis["parameters"]["author"] = prev_results[0].get("author", "")

        # Check for ambiguous queries
        ambiguous_terms = ["stuff", "things", "something", "anything"]
        if any(term in query_lower for term in ambiguous_terms):
            analysis["ambiguous"] = True

        return analysis

    def _create_steps(
        self, query_analysis: Dict[str, Any], available_tools: List[BaseTool]
    ) -> List[PlanStep]:
        """Create execution steps based on query analysis."""
        steps = []
        tool_map = {tool.name: tool for tool in available_tools}

        # Primary search step
        if query_analysis["intent"] == "author_search":
            if "search_by_author" in tool_map:
                step = PlanStep(
                    id=str(uuid.uuid4()),
                    tool_name="search_by_author",
                    parameters={
                        "author": query_analysis["parameters"].get("author", ""),
                        "fuzzy_match": True,
                    },
                )
                steps.append(step)
            elif "search_publications" in tool_map:
                # Use search_publications for author search if search_by_author is not available
                step = PlanStep(
                    id=str(uuid.uuid4()),
                    tool_name="search_publications",
                    parameters={
                        "author_name": query_analysis["parameters"].get("author", ""),
                        "limit": 10,
                    },
                )
                steps.append(step)

        elif query_analysis["intent"] == "topic_search":
            if "search_publications" in tool_map:
                step = PlanStep(
                    id=str(uuid.uuid4()),
                    tool_name="search_publications",
                    parameters={
                        "topic": query_analysis["parameters"].get("topic", ""),
                        "limit": 10,
                    },
                )
                steps.append(step)

        else:  # General search
            if "search_publications" in tool_map:
                step = PlanStep(
                    id=str(uuid.uuid4()),
                    tool_name="search_publications",
                    parameters={"query": query_analysis.get("query", ""), "limit": 10},
                )
                steps.append(step)

        # Add statistics step if requested
        if query_analysis.get("statistics") and "get_field_statistics" in tool_map:
            stats_step = PlanStep(
                id=str(uuid.uuid4()),
                tool_name="get_field_statistics",
                parameters={
                    "field": query_analysis["parameters"].get(
                        "topic", "machine learning"
                    ),
                    "include_trends": True,
                },
            )

            # Add condition if conditional query
            if query_analysis.get("conditional"):
                condition_value = query_analysis.get("condition_value", "5")
                stats_step.condition = Condition(
                    field="total_publications",
                    operator="gt",
                    value=int(condition_value),
                )

            steps.append(stats_step)

        return steps

    def _add_dependencies(
        self, steps: List[PlanStep], query_analysis: Dict[str, Any]
    ) -> None:
        """Add dependencies between steps."""
        if len(steps) <= 1:
            return

        # If we have both author search and statistics, stats depends on author
        author_steps = [step for step in steps if step.tool_name == "search_by_author"]
        stats_steps = [
            step for step in steps if step.tool_name == "get_field_statistics"
        ]

        if author_steps and stats_steps:
            for stats_step in stats_steps:
                stats_step.dependencies.append(author_steps[0].id)

        # For complex queries with multiple steps, create dependencies
        query_lower = query_analysis.get("query", "").lower()
        if "how many" in query_lower and "topics" in query_lower:
            # If asking about count and topics, stats should depend on search
            search_steps = [
                step
                for step in steps
                if step.tool_name in ["search_publications", "search_by_author"]
            ]
            if search_steps and stats_steps:
                for stats_step in stats_steps:
                    if search_steps[0].id not in stats_step.dependencies:
                        stats_step.dependencies.append(search_steps[0].id)

    def _create_expected_outputs(
        self, steps: List[PlanStep], query_analysis: Dict[str, Any]
    ) -> Dict[str, OutputSchema]:
        """Create expected output schemas."""
        outputs = {}

        for step in steps:
            if step.tool_name == "search_publications":
                outputs[step.id] = OutputSchema(
                    type="json",
                    fields={
                        "publications": "list",
                        "total_found": "integer",
                        "query_info": "object",
                    },
                    required=["publications", "total_found"],
                )

            elif step.tool_name == "search_by_author":
                outputs[step.id] = OutputSchema(
                    type="json",
                    fields={
                        "name": "string",
                        "publications": "list",
                        "total_publications": "integer",
                        "main_topics": "list",
                    },
                    required=["name", "publications"],
                )

            elif step.tool_name == "get_field_statistics":
                outputs[step.id] = OutputSchema(
                    type="json",
                    fields={
                        "total_publications": "integer",
                        "yearly_trend": "object",
                        "top_journals": "list",
                        "related_topics": "list",
                    },
                    required=["total_publications"],
                )

        return outputs

    def _create_fallback_strategies(
        self, steps: List[PlanStep]
    ) -> Dict[str, FallbackStrategy]:
        """Create fallback strategies for tools."""
        strategies = {}

        for step in steps:
            if step.tool_name == "search_publications":
                strategies[step.tool_name] = FallbackStrategy(
                    strategy_type="retry", max_retries=3, retry_delay=2
                )

            elif step.tool_name == "search_by_author":
                strategies[step.tool_name] = FallbackStrategy(
                    strategy_type="alternate_tool",
                    max_retries=2,
                    alternate_tool="search_publications",
                )

            elif step.tool_name == "get_field_statistics":
                strategies[step.tool_name] = FallbackStrategy(
                    strategy_type="skip", max_retries=1
                )

        return strategies

    def _identify_parallel_groups(self, steps: List[PlanStep]) -> List[List[str]]:
        """Identify groups of steps that can run in parallel."""
        parallel_groups = []

        # Steps with no dependencies can run in parallel
        independent_steps = [step.id for step in steps if not step.dependencies]
        if len(independent_steps) > 1:
            parallel_groups.append(independent_steps)

        return parallel_groups

    def _create_retry_step(self, failed_step: PlanStep) -> PlanStep:
        """Create a retry step for a failed step."""
        return PlanStep(
            id=str(uuid.uuid4()),
            tool_name=failed_step.tool_name,
            parameters=failed_step.parameters.copy(),
            dependencies=failed_step.dependencies.copy(),
            condition=failed_step.condition,
        )

    def _create_alternate_step(
        self, failed_step: PlanStep, fallback_strategy: FallbackStrategy
    ) -> PlanStep:
        """Create an alternate step using fallback strategy."""
        alternate_tool = fallback_strategy.alternate_tool
        if not alternate_tool:
            return failed_step

        # Adapt parameters for alternate tool
        adapted_params = failed_step.parameters.copy()
        if (
            failed_step.tool_name == "search_by_author"
            and alternate_tool == "search_publications"
        ):
            # Convert author search to general publication search
            if "author" in adapted_params:
                adapted_params["query"] = f"author:{adapted_params.pop('author')}"

        return PlanStep(
            id=str(uuid.uuid4()),
            tool_name=alternate_tool,
            parameters=adapted_params,
            dependencies=failed_step.dependencies.copy(),
            condition=failed_step.condition,
        )


# Alias for backward compatibility
QueryPlanner = PlanningAgent
