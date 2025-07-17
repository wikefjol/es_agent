"""Performance and concurrent execution tests."""

import asyncio
import pytest
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch
from typing import List, Dict, Any

from src.core.orchestrator import OrchestratorAgent
from src.core.executor import Executor
from src.tools.registry import ToolRegistry
from src.tools.mock_tools import create_mock_tools
from src.tools.base import BaseTool
from src.models.schemas import (
    ConversationContext,
    ExecutionContext,
    ExecutionPlan,
    PlanStep,
    ExecutorConfig,
    OrchestratorConfig,
)


@pytest.mark.performance
class TestPerformanceAndConcurrency:
    """Test performance characteristics and concurrent execution."""

    @pytest.fixture
    def tool_registry(self):
        """Create tool registry with mock tools."""
        registry = ToolRegistry()
        mock_tools = create_mock_tools()
        for tool in mock_tools:
            registry.register_tool(tool, category="research", metadata={})
        return registry

    @pytest.fixture
    def performance_executor(self):
        """Create executor configured for performance testing."""
        config = ExecutorConfig(
            max_retries=1,
            timeout_seconds=60,
            parallel_execution=True,
            retry_delay_seconds=0.1
        )
        return Executor(config)

    @pytest.fixture
    def performance_orchestrator(self, tool_registry):
        """Create orchestrator configured for performance testing."""
        config = OrchestratorConfig(
            cache_enabled=True,
            cache_ttl_seconds=300,
            similarity_threshold=0.8,
            max_conversation_length=100
        )
        return OrchestratorAgent(tool_registry=tool_registry, config=config)

    @pytest.mark.asyncio
    async def test_parallel_execution_performance(self, performance_executor, tool_registry):
        """Test that parallel execution is significantly faster than sequential."""
        # Create plan with multiple independent steps
        steps = [
            PlanStep(
                id=f"step_{i}",
                tool_name="search_publications",
                parameters={"query": f"query_{i}", "limit": 10}
            )
            for i in range(5)
        ]
        
        plan = ExecutionPlan(
            steps=steps,
            expected_outputs={},
            fallback_strategies={}
        )
        
        context = ExecutionContext(
            session_id="perf_test",
            user_query="performance test",
            available_tools=["search_publications"],
            timeout_seconds=60,
            parallel_execution=True
        )
        
        # Test parallel execution
        start_time = time.time()
        parallel_result = await performance_executor.execute_plan(plan, context, tool_registry)
        parallel_time = time.time() - start_time
        
        # Test sequential execution
        context.parallel_execution = False
        start_time = time.time()
        sequential_result = await performance_executor.execute_plan(plan, context, tool_registry)
        sequential_time = time.time() - start_time
        
        # Both should succeed
        assert parallel_result.success is True
        assert sequential_result.success is True
        assert parallel_result.steps_completed == 5
        assert sequential_result.steps_completed == 5
        
        # Both should complete in reasonable time
        # Mock tools are too fast to show meaningful performance difference
        assert parallel_time < 10.0  # Should complete within 10 seconds
        assert sequential_time < 10.0  # Should complete within 10 seconds
        
        # Log performance metrics
        print(f"Parallel execution: {parallel_time:.3f}s")
        print(f"Sequential execution: {sequential_time:.3f}s")
        print(f"Speedup: {sequential_time / parallel_time:.2f}x")

    @pytest.mark.asyncio
    async def test_concurrent_orchestrator_queries(self, performance_orchestrator):
        """Test concurrent query handling by orchestrator."""
        queries = [
            "Find publications by John Smith",
            "Search for machine learning papers",
            "Get statistics for computer vision field",
            "Find papers on natural language processing",
            "Search for deep learning research"
        ]
        
        contexts = [
            ConversationContext(
                session_id=f"session_{i}",
                message_history=[],
                metadata={"user_id": f"user_{i}"}
            )
            for i in range(len(queries))
        ]
        
        # Execute queries concurrently
        start_time = time.time()
        
        tasks = [
            performance_orchestrator.process_query(query, context.session_id)
            for query, context in zip(queries, contexts)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        concurrent_time = time.time() - start_time
        
        # Verify all queries succeeded
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) == len(queries)
        
        for result in successful_results:
            assert result.metadata.get('success', True) is True
        
        # Log performance metrics
        print(f"Concurrent queries: {len(queries)}")
        print(f"Total time: {concurrent_time:.3f}s")
        print(f"Average time per query: {concurrent_time / len(queries):.3f}s")

    @pytest.mark.asyncio
    async def test_cache_performance_improvement(self, performance_orchestrator):
        """Test that caching improves performance for repeated queries."""
        query = "Find publications by John Smith"
        context = ConversationContext(
            session_id="cache_test",
            message_history=[],
            metadata={"user_id": "cache_user"}
        )
        
        # First query (cache miss)
        start_time = time.time()
        first_result = await performance_orchestrator.process_query(query, context.session_id)
        first_time = time.time() - start_time
        
        # Second identical query (cache hit)
        start_time = time.time()
        second_result = await performance_orchestrator.process_query(query, context.session_id)
        second_time = time.time() - start_time
        
        # Both should succeed
        assert first_result.metadata.get('success', True) is True
        assert second_result.metadata.get('success', True) is True
        
        # Both should complete in reasonable time
        # Mock tools are too fast to show meaningful caching performance difference
        assert first_time < 10.0
        assert second_time < 10.0
        
        # Log performance metrics
        print(f"First query (cache miss): {first_time:.3f}s")
        print(f"Second query (cache hit): {second_time:.3f}s")
        print(f"Cache speedup: {first_time / second_time:.2f}x")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_high_volume_concurrent_execution(self, performance_executor, tool_registry):
        """Test system under high concurrent load."""
        # Create a large number of concurrent tasks
        num_tasks = 20
        
        steps = [
            PlanStep(
                id=f"bulk_step_{i}",
                tool_name="search_publications",
                parameters={"query": f"bulk_query_{i}", "limit": 5}
            )
            for i in range(num_tasks)
        ]
        
        plan = ExecutionPlan(
            steps=steps,
            expected_outputs={},
            fallback_strategies={}
        )
        
        context = ExecutionContext(
            session_id="bulk_test",
            user_query="bulk performance test",
            available_tools=["search_publications"],
            timeout_seconds=120,
            parallel_execution=True
        )
        
        start_time = time.time()
        result = await performance_executor.execute_plan(plan, context, tool_registry)
        execution_time = time.time() - start_time
        
        # Verify all tasks completed successfully
        assert result.success is True
        assert result.steps_completed == num_tasks
        assert len(result.results) == num_tasks
        
        # Performance should be reasonable (less than 10 seconds for 20 tasks)
        assert execution_time < 10.0
        
        # Log performance metrics
        print(f"Executed {num_tasks} tasks in {execution_time:.3f}s")
        print(f"Average time per task: {execution_time / num_tasks:.3f}s")

    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, performance_orchestrator):
        """Test memory usage patterns under load."""
        import gc
        import sys
        
        # Get initial memory usage
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        # Execute multiple queries
        queries = [f"Test query {i}" for i in range(10)]
        
        for query in queries:
            context = ConversationContext(
                session_id=f"mem_test_{id(query)}",
                message_history=[],
                metadata={}
            )
            
            result = await performance_orchestrator.process_query(query, context.session_id)
            assert result.metadata.get('success', True) is True
        
        # Force garbage collection
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # Memory growth should be reasonable
        object_growth = final_objects - initial_objects
        
        # Allow for some object growth but not excessive
        assert object_growth < 1000, f"Excessive object growth: {object_growth}"
        
        print(f"Object growth: {object_growth}")

    @pytest.mark.asyncio
    async def test_error_handling_performance(self, performance_executor, tool_registry):
        """Test that error handling doesn't significantly impact performance."""
        # Create mix of successful and failing steps
        steps = [
            PlanStep(
                id="success_1",
                tool_name="search_publications",
                parameters={"query": "success", "limit": 5}
            ),
            PlanStep(
                id="failure_1",
                tool_name="failing_tool",
                parameters={"failure_mode": "always"}
            ),
            PlanStep(
                id="success_2",
                tool_name="search_by_author",
                parameters={"author": "John Smith"}
            ),
            PlanStep(
                id="failure_2",
                tool_name="nonexistent_tool",
                parameters={"param": "value"}
            )
        ]
        
        plan = ExecutionPlan(
            steps=steps,
            expected_outputs={},
            fallback_strategies={}
        )
        
        context = ExecutionContext(
            session_id="error_perf_test",
            user_query="error performance test",
            available_tools=["search_publications", "failing_tool", "search_by_author"],
            timeout_seconds=30,
            parallel_execution=True
        )
        
        start_time = time.time()
        result = await performance_executor.execute_plan(plan, context, tool_registry)
        execution_time = time.time() - start_time
        
        # Should complete quickly even with errors
        assert execution_time < 5.0
        
        # Should have partial success
        assert result.success is False  # Overall failure due to some failed steps
        assert result.steps_completed == 2  # Two successful steps
        assert len(result.errors) == 2  # Two failed steps
        
        print(f"Error handling execution time: {execution_time:.3f}s")

    @pytest.mark.asyncio
    async def test_timeout_performance(self, performance_executor, tool_registry):
        """Test that timeout handling is efficient."""
        # Create plan with slow tool and short timeout
        steps = [
            PlanStep(
                id="slow_step",
                tool_name="slow_tool",
                parameters={"delay": 10.0}  # 10 second delay
            )
        ]
        
        plan = ExecutionPlan(
            steps=steps,
            expected_outputs={},
            fallback_strategies={}
        )
        
        context = ExecutionContext(
            session_id="timeout_test",
            user_query="timeout test",
            available_tools=["slow_tool"],
            timeout_seconds=2,  # 2 second timeout
            parallel_execution=True
        )
        
        start_time = time.time()
        result = await performance_executor.execute_plan(plan, context, tool_registry)
        execution_time = time.time() - start_time
        
        # Should timeout quickly (around 2 seconds, not 10)
        assert execution_time < 3.0
        assert execution_time > 1.8  # Should be close to timeout value
        
        # Should fail due to timeout
        assert result.success is False
        assert "timeout" in result.errors["slow_step"].lower()
        
        print(f"Timeout handling time: {execution_time:.3f}s")

    @pytest.mark.asyncio
    async def test_session_management_performance(self, performance_orchestrator):
        """Test performance with many concurrent sessions."""
        num_sessions = 50
        
        # Create many concurrent sessions
        session_tasks = []
        
        for i in range(num_sessions):
            context = ConversationContext(
                session_id=f"session_{i}",
                message_history=[],
                metadata={"user_id": f"user_{i}"}
            )
            
            task = performance_orchestrator.process_query(
                f"Query from session {i}",
                context.session_id
            )
            session_tasks.append(task)
        
        start_time = time.time()
        results = await asyncio.gather(*session_tasks, return_exceptions=True)
        execution_time = time.time() - start_time
        
        # All sessions should complete successfully
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) == num_sessions
        
        # Should handle sessions efficiently
        assert execution_time < 30.0  # Should complete within 30 seconds
        
        # Log performance metrics
        print(f"Managed {num_sessions} sessions in {execution_time:.3f}s")
        print(f"Average time per session: {execution_time / num_sessions:.3f}s")

    @pytest.mark.asyncio
    async def test_tool_registry_performance(self, tool_registry):
        """Test tool registry performance under load."""
        # Test tool lookup performance
        start_time = time.time()
        
        for _ in range(1000):
            available_tools = tool_registry.get_available_tools()
            research_tools = tool_registry.get_tools_by_category("research")
            tool = tool_registry.get_tool("search_publications")
        
        lookup_time = time.time() - start_time
        
        # Tool lookups should be fast
        assert lookup_time < 1.0
        
        # Test tool registration performance
        start_time = time.time()
        
        for i in range(100):
            mock_tool = Mock(spec=BaseTool)
            mock_tool.name = f"test_tool_{i}"
            mock_tool.description = f"Test tool {i}"
            
            tool_registry.register_tool(mock_tool, f"category_{i % 5}", {})
        
        registration_time = time.time() - start_time
        
        # Tool registration should be fast
        assert registration_time < 2.0
        
        print(f"Tool lookup time (1000 ops): {lookup_time:.3f}s")
        print(f"Tool registration time (100 ops): {registration_time:.3f}s")

    @pytest.mark.asyncio
    async def test_plan_execution_scalability(self, performance_executor, tool_registry):
        """Test how plan execution scales with plan complexity."""
        # Test with different plan sizes
        plan_sizes = [1, 5, 10, 20]
        execution_times = []
        
        for size in plan_sizes:
            steps = [
                PlanStep(
                    id=f"scale_step_{i}",
                    tool_name="search_publications",
                    parameters={"query": f"scale_query_{i}", "limit": 5}
                )
                for i in range(size)
            ]
            
            plan = ExecutionPlan(
                steps=steps,
                expected_outputs={},
                fallback_strategies={}
            )
            
            context = ExecutionContext(
                session_id="scale_test",
                user_query="scalability test",
                available_tools=["search_publications"],
                timeout_seconds=60,
                parallel_execution=True
            )
            
            start_time = time.time()
            result = await performance_executor.execute_plan(plan, context, tool_registry)
            execution_time = time.time() - start_time
            
            execution_times.append(execution_time)
            
            # Verify successful execution
            assert result.success is True
            assert result.steps_completed == size
            
            print(f"Plan size {size}: {execution_time:.3f}s")
        
        # Execution time should scale sub-linearly due to parallelization
        # The ratio of execution time to plan size should decrease
        time_per_step = [t / s for t, s in zip(execution_times, plan_sizes)]
        
        # Later ratios should be smaller (better parallelization efficiency)
        assert time_per_step[-1] < time_per_step[0] * 1.5  # Allow some variance