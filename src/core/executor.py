"""Executor for running execution plans with async support and error handling."""

import asyncio
import time
from typing import Dict, Any, List, Optional
from src.tools.base import BaseTool, ToolResult
from src.tools.registry import ToolRegistry
from src.models.schemas import (
    ExecutionPlan,
    PlanStep,
    PlanStepStatus,
    ExecutionResult,
    ExecutionContext,
    ExecutorConfig,
    Condition,
    FallbackStrategy,
)


class Executor:
    """Executor for running execution plans with retry logic and error handling."""

    def __init__(self, config: ExecutorConfig):
        """Initialize the executor with configuration.

        Args:
            config: Configuration for the executor
        """
        self.config = config

    async def execute_plan(
        self,
        plan: ExecutionPlan,
        context: ExecutionContext,
        tool_registry: ToolRegistry,
    ) -> ExecutionResult:
        """Execute a complete execution plan.

        Args:
            plan: The execution plan to run
            context: Execution context
            tool_registry: Registry of available tools

        Returns:
            ExecutionResult with results and errors
        """
        start_time = time.time()
        results = {}
        errors = {}
        executed_steps = set()

        # Handle empty plan
        if not plan.steps:
            return ExecutionResult(
                plan_id=context.session_id,
                success=True,
                results={},
                errors={},
                execution_time=time.time() - start_time,
                steps_completed=0,
                steps_total=0,
            )

        # Execute steps respecting dependencies
        steps_to_execute = plan.steps.copy()

        while steps_to_execute:
            # Find steps that can be executed (dependencies satisfied)
            ready_steps = []
            for step in steps_to_execute:
                if all(dep_id in executed_steps for dep_id in step.dependencies):
                    ready_steps.append(step)

            if not ready_steps:
                # No steps ready - check for circular dependencies
                remaining_step_ids = [step.id for step in steps_to_execute]
                for step in steps_to_execute:
                    errors[step.id] = (
                        f"Circular dependency detected or dependency not satisfied: {step.dependencies}"
                    )
                break

            # Execute ready steps
            if self.config.parallel_execution and len(ready_steps) > 1:
                # Execute in parallel
                tasks = []
                for step in ready_steps:
                    task = asyncio.create_task(
                        self._execute_step_with_retry(
                            step, results, tool_registry, plan.fallback_strategies
                        )
                    )
                    tasks.append((step, task))

                # Wait for all tasks to complete
                for step, task in tasks:
                    try:
                        result = await asyncio.wait_for(
                            task, timeout=context.timeout_seconds
                        )
                        if result.success:
                            results[step.id] = result.data
                            executed_steps.add(step.id)
                        elif result.metadata.get("skipped"):
                            # Step was skipped due to condition - count as success but don't include in results
                            results[step.id] = result.data  # Will be None
                            executed_steps.add(step.id)
                        else:
                            errors[step.id] = result.error or "Unknown error"
                    except asyncio.TimeoutError:
                        errors[step.id] = (
                            f"Step timed out after {context.timeout_seconds} seconds"
                        )
                    except Exception as e:
                        errors[step.id] = f"Unexpected error: {str(e)}"
            else:
                # Execute sequentially
                for step in ready_steps:
                    try:
                        result = await asyncio.wait_for(
                            self._execute_step_with_retry(
                                step, results, tool_registry, plan.fallback_strategies
                            ),
                            timeout=context.timeout_seconds,
                        )
                        if result.success:
                            results[step.id] = result.data
                            executed_steps.add(step.id)
                        elif result.metadata.get("skipped"):
                            # Step was skipped due to condition - count as success but don't include in results
                            results[step.id] = result.data  # Will be None
                            executed_steps.add(step.id)
                        else:
                            errors[step.id] = result.error or "Unknown error"
                    except asyncio.TimeoutError:
                        errors[step.id] = (
                            f"Step timed out after {context.timeout_seconds} seconds"
                        )
                    except Exception as e:
                        errors[step.id] = f"Unexpected error: {str(e)}"

            # Remove executed steps from the queue
            steps_to_execute = [
                step for step in steps_to_execute if step not in ready_steps
            ]

        # Calculate final results
        execution_time = time.time() - start_time
        steps_completed = len(executed_steps)
        steps_total = len(plan.steps)
        success = steps_completed == steps_total and len(errors) == 0

        return ExecutionResult(
            plan_id=context.session_id,
            success=success,
            results=results,
            errors=errors,
            execution_time=execution_time,
            steps_completed=steps_completed,
            steps_total=steps_total,
        )

    async def execute_step(
        self,
        step: PlanStep,
        previous_results: Dict[str, Any],
        tool_registry: ToolRegistry,
    ) -> ToolResult:
        """Execute a single step.

        Args:
            step: The step to execute
            previous_results: Results from previous steps
            tool_registry: Registry of available tools

        Returns:
            ToolResult from the step execution
        """
        # Get the tool
        tool = tool_registry.get_tool(step.tool_name)
        if not tool:
            return ToolResult(
                success=False,
                data=None,
                error=f"Tool '{step.tool_name}' not found",
                metadata={"step_id": step.id},
            )

        # Check condition if present
        if step.condition:
            try:
                if not self._evaluate_condition(step.condition, previous_results):
                    return ToolResult(
                        success=True,
                        data=None,
                        error=None,
                        metadata={
                            "step_id": step.id,
                            "skipped": True,
                            "reason": "condition_not_met",
                        },
                    )
            except Exception as e:
                return ToolResult(
                    success=True,
                    data=None,
                    error=None,
                    metadata={
                        "step_id": step.id,
                        "skipped": True,
                        "reason": f"condition_error: {str(e)}",
                    },
                )

        # Execute the tool
        try:
            result = await tool.execute(**step.parameters)
            result.metadata["step_id"] = step.id
            return result
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Tool execution failed: {str(e)}",
                metadata={"step_id": step.id},
            )

    async def _execute_step_with_retry(
        self,
        step: PlanStep,
        previous_results: Dict[str, Any],
        tool_registry: ToolRegistry,
        fallback_strategies: Dict[str, FallbackStrategy],
    ) -> ToolResult:
        """Execute a step with retry logic.

        Args:
            step: The step to execute
            previous_results: Results from previous steps
            tool_registry: Registry of available tools
            fallback_strategies: Fallback strategies for tools

        Returns:
            ToolResult from the step execution
        """
        fallback_strategy = fallback_strategies.get(
            step.tool_name,
            FallbackStrategy(
                strategy_type="retry", max_retries=self.config.max_retries
            ),
        )

        max_retries = min(fallback_strategy.max_retries, self.config.max_retries)
        retry_delay = fallback_strategy.retry_delay

        for attempt in range(max_retries + 1):
            result = await self.execute_step(step, previous_results, tool_registry)

            if result.success or result.metadata.get("skipped"):
                return result

            # If this is the last attempt, return the error
            if attempt == max_retries:
                return result

            # Wait before retry
            if retry_delay > 0:
                await asyncio.sleep(retry_delay)

        # This should not be reached, but just in case
        return ToolResult(
            success=False,
            data=None,
            error="Max retries exceeded",
            metadata={"step_id": step.id},
        )

    def _evaluate_condition(
        self, condition: Condition, previous_results: Dict[str, Any]
    ) -> bool:
        """Evaluate a condition against previous results.

        Args:
            condition: The condition to evaluate
            previous_results: Results from previous steps

        Returns:
            True if condition is met, False otherwise
        """
        # Find the value to compare in previous results
        value = None
        for result in previous_results.values():
            if isinstance(result, dict) and condition.field in result:
                value = result[condition.field]
                break

        if value is None:
            # Field not found in results
            raise ValueError(f"Field '{condition.field}' not found in previous results")

        # Evaluate the condition
        if condition.operator == "gt":
            return value > condition.value
        elif condition.operator == "gte":
            return value >= condition.value
        elif condition.operator == "lt":
            return value < condition.value
        elif condition.operator == "lte":
            return value <= condition.value
        elif condition.operator == "eq":
            return value == condition.value
        elif condition.operator == "ne":
            return value != condition.value
        elif condition.operator == "in":
            return value in condition.value
        elif condition.operator == "not_in":
            return value not in condition.value
        elif condition.operator == "contains":
            return condition.value in value
        else:
            raise ValueError(f"Unknown operator: {condition.operator}")

    def _create_dependency_graph(self, steps: List[PlanStep]) -> Dict[str, List[str]]:
        """Create a dependency graph from steps.

        Args:
            steps: List of plan steps

        Returns:
            Dictionary mapping step IDs to their dependencies
        """
        graph = {}
        for step in steps:
            graph[step.id] = step.dependencies.copy()
        return graph

    def _topological_sort(self, graph: Dict[str, List[str]]) -> List[str]:
        """Perform topological sort on the dependency graph.

        Args:
            graph: Dependency graph

        Returns:
            List of step IDs in execution order
        """
        # Simple topological sort using Kahn's algorithm
        in_degree = {node: 0 for node in graph}
        for node in graph:
            for dependency in graph[node]:
                if dependency in in_degree:
                    in_degree[dependency] += 1

        queue = [node for node in in_degree if in_degree[node] == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)

            for neighbor in graph:
                if node in graph[neighbor]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)

        return result
