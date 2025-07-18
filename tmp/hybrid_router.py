"""
Hybrid router that intelligently routes queries between fast-path and full workflows.

This module provides intelligent routing for queries, using query classification
to determine whether to use fast conversational responses or full research workflows.
"""

import time
from typing import Dict, List, Optional, Any, AsyncIterator
from datetime import datetime
import traceback

from .query_classifier import QueryClassifier, QueryClassification
from .fast_path_workflow import ConversationalWorkflow, FastPathResponse
from src.research_agent.core.workflow import ResearchAgent, run_research_query
from elasticsearch import Elasticsearch


class HybridRouter:
    """
    Intelligent router that chooses between fast-path and full workflow.
    
    This router uses query classification to determine the optimal processing
    path for each query, optimizing for both response time and quality.
    """
    
    def __init__(self, es_client: Optional[Elasticsearch] = None, 
                 index_name: str = "research-publications-static"):
        """
        Initialize the hybrid router.
        
        Args:
            es_client: Elasticsearch client instance
            index_name: Name of the publications index
        """
        self.es_client = es_client
        self.index_name = index_name
        
        # Initialize components
        self.query_classifier = QueryClassifier()
        self.conversational_workflow = ConversationalWorkflow()
        self.research_agent = None
        
        # Initialize research agent
        self._initialize_research_agent()
        
        # Performance tracking
        self.performance_stats = {
            "fast_path_count": 0,
            "full_workflow_count": 0,
            "escalation_count": 0,
            "avg_fast_path_time": 0.0,
            "avg_full_workflow_time": 0.0
        }
    
    def _initialize_research_agent(self):
        """Initialize the research agent for full workflow queries."""
        try:
            if self.es_client:
                self.research_agent = ResearchAgent(
                    es_client=self.es_client,
                    index_name=self.index_name,
                    recursion_limit=50
                )
        except Exception as e:
            print(f"Warning: Failed to initialize ResearchAgent: {str(e)}")
            self.research_agent = None
    
    def is_initialized(self) -> bool:
        """Check if the router is properly initialized."""
        return self.query_classifier is not None and self.conversational_workflow is not None
    
    def get_memory_summary(self) -> Dict[str, Any]:
        """Get a summary of the current conversation memory state."""
        if self.conversational_workflow:
            return self.conversational_workflow.get_memory_summary()
        return {"total_messages": 0, "user_messages": 0, "ai_messages": 0, "memory_buffer": None}
    
    def clear_memory(self):
        """Clear the conversation memory."""
        if self.conversational_workflow:
            self.conversational_workflow.clear_memory()
    
    def get_conversation_memory(self):
        """Get direct access to the conversation memory instance."""
        if self.conversational_workflow:
            return self.conversational_workflow.get_conversation_memory()
        return None
    
    def process_query(self, query: str, conversation_history: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Process a query using the optimal workflow path.
        
        Args:
            query: Natural language query
            conversation_history: Recent conversation history for context
            
        Returns:
            Dictionary containing result and metadata
        """
        start_time = time.time()
        
        try:
            # Classify the query
            classification = self.query_classifier.classify_query(query, conversation_history)
            
            # Determine processing path
            if self.should_use_fast_path(classification):
                return self._process_fast_path(query, conversation_history, classification, start_time)
            else:
                return self._process_full_workflow(query, conversation_history, classification, start_time)
                
        except Exception as e:
            return {
                'success': False,
                'error': f"Router error: {str(e)}",
                'response': None,
                'metadata': {
                    'workflow_type': 'error',
                    'error_details': str(e),
                    'traceback': traceback.format_exc()
                }
            }
    
    def should_use_fast_path(self, classification: QueryClassification) -> bool:
        """
        Determine if a query should use the fast path based on classification.
        
        Args:
            classification: Query classification result
            
        Returns:
            True if should use fast path, False for full workflow
        """
        return (
            classification.query_type == "conversational" and
            classification.confidence > 0.7 and
            not classification.needs_tools
        )
    
    def _process_fast_path(self, query: str, conversation_history: Optional[List[Dict]], 
                          classification: QueryClassification, start_time: float) -> Dict[str, Any]:
        """Process query using fast conversational path."""
        try:
            # Use fast path
            fast_response = self.conversational_workflow.process_query(query, conversation_history)
            
            # Update performance stats
            self.performance_stats["fast_path_count"] += 1
            self._update_avg_time("fast_path", fast_response.response_time)
            
            # Check if escalation is needed
            if fast_response.escalate:
                self.performance_stats["escalation_count"] += 1
                return self._escalate_to_full_workflow(query, conversation_history, fast_response)
            
            total_time = time.time() - start_time
            
            return {
                'success': True,
                'error': None,
                'response': fast_response.response,
                'metadata': {
                    'workflow_type': 'fast_path',
                    'response_time': fast_response.response_time,
                    'total_time': total_time,
                    'classification': classification.dict(),
                    'escalated': False,
                    'fast_path_metadata': fast_response.metadata
                }
            }
            
        except Exception as e:
            # Fallback to full workflow on error
            return self._process_full_workflow(query, conversation_history, classification, start_time)
    
    def _process_full_workflow(self, query: str, conversation_history: Optional[List[Dict]], 
                             classification: QueryClassification, start_time: float) -> Dict[str, Any]:
        """Process query using full research workflow."""
        if not self.research_agent:
            return {
                'success': False,
                'error': 'ResearchAgent not initialized',
                'response': None,
                'metadata': {'workflow_type': 'full_workflow_error'}
            }
        
        try:
            # Use full workflowtmp
            
            result = run_research_query(
                query,
                self.es_client,
                self.index_name,
                50,  # recursion_limit
                False  # stream
            )
            
            workflow_time = time.time() - start_time
            
            # Update performance stats
            self.performance_stats["full_workflow_count"] += 1
            self._update_avg_time("full_workflow", workflow_time)
            
            return {
                'success': True,
                'error': None,
                'response': result.get('response', 'No response generated'),
                'metadata': {
                    'workflow_type': 'full_workflow',
                    'response_time': workflow_time,
                    'classification': classification.dict(),
                    'plan': result.get('plan', []),
                    'past_steps': result.get('past_steps', []),
                    'total_results': result.get('total_results'),
                    'current_step': result.get('current_step', 0),
                    'session_id': result.get('session_id')
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'response': None,
                'metadata': {
                    'workflow_type': 'full_workflow_error',
                    'error_details': str(e),
                    'traceback': traceback.format_exc()
                }
            }
    
    def _escalate_to_full_workflow(self, query: str, conversation_history: Optional[List[Dict]], 
                                  fast_response: FastPathResponse) -> Dict[str, Any]:
        """Escalate from fast path to full workflow."""
        if not self.research_agent:
            return {
                'success': False,
                'error': 'Cannot escalate: ResearchAgent not initialized',
                'response': fast_response.response,
                'metadata': {
                    'workflow_type': 'escalation_error',
                    'escalation_reason': fast_response.escalation_reason
                }
            }
        
        try:
            # Run full workflow
            result = run_research_query(
                query,
                self.es_client,
                self.index_name,
                50,  # recursion_limit
                False  # stream
            )
            
            workflow_time = time.time() - fast_response.response_time
            
            # Update performance stats
            self.performance_stats["full_workflow_count"] += 1
            self._update_avg_time("full_workflow", workflow_time)
            
            return {
                'success': True,
                'error': None,
                'response': result.get('response', 'No response generated'),
                'metadata': {
                    'workflow_type': 'escalated',
                    'escalation_reason': fast_response.escalation_reason,
                    'fast_path_time': fast_response.response_time,
                    'full_workflow_time': workflow_time,
                    'plan': result.get('plan', []),
                    'past_steps': result.get('past_steps', []),
                    'total_results': result.get('total_results'),
                    'current_step': result.get('current_step', 0),
                    'session_id': result.get('session_id')
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'response': fast_response.response,
                'metadata': {
                    'workflow_type': 'escalation_error',
                    'escalation_reason': fast_response.escalation_reason,
                    'error_details': str(e),
                    'traceback': traceback.format_exc()
                }
            }
    
    async def stream_query(self, query: str, conversation_history: Optional[List[Dict]] = None) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream a query execution with real-time updates.
        
        Args:
            query: Natural language query
            conversation_history: Recent conversation history for context
            
        Yields:
            Dictionary containing streaming updates
        """
        start_time = time.time()
        
        try:
            # Classify the query
            classification = self.query_classifier.classify_query(query, conversation_history)
            
            # Yield classification info
            yield {
                'type': 'classification',
                'content': {
                    'query_type': classification.query_type,
                    'confidence': classification.confidence,
                    'reasoning': classification.reasoning,
                    'processing_message': self.query_classifier.get_processing_message(query, conversation_history)
                },
                'timestamp': datetime.now()
            }
            
            # Process based on classification
            if self.should_use_fast_path(classification):
                async for event in self._stream_fast_path(query, conversation_history, classification):
                    yield event
            else:
                async for event in self._stream_full_workflow(query, conversation_history, classification):
                    yield event
                    
        except Exception as e:
            yield {
                'type': 'error',
                'content': {
                    'error': str(e),
                    'traceback': traceback.format_exc()
                },
                'timestamp': datetime.now()
            }
    
    async def _stream_fast_path(self, query: str, conversation_history: Optional[List[Dict]], 
                               classification: QueryClassification) -> AsyncIterator[Dict[str, Any]]:
        """Stream fast path execution."""
        try:
            async for event in self.conversational_workflow.stream_query(query, conversation_history):
                # Check for escalation
                if event.get('type') == 'escalation':
                    self.performance_stats["escalation_count"] += 1
                    
                    # Yield escalation notice
                    yield event
                    
                    # Switch to full workflow
                    async for full_event in self._stream_full_workflow(query, conversation_history, classification):
                        yield full_event
                    return
                
                # Track fast path completion
                if event.get('type') == 'final':
                    self.performance_stats["fast_path_count"] += 1
                    content = event.get('content', {})
                    if isinstance(content, dict) and 'response_time' in content:
                        self._update_avg_time("fast_path", content['response_time'])
                
                yield event
                
        except Exception as e:
            yield {
                'type': 'error',
                'content': {
                    'error': f"Fast path error: {str(e)}",
                    'traceback': traceback.format_exc()
                },
                'timestamp': datetime.now()
            }
    
    async def _stream_full_workflow(self, query: str, conversation_history: Optional[List[Dict]], 
                                   classification: QueryClassification) -> AsyncIterator[Dict[str, Any]]:
        """Stream full workflow execution."""
        if not self.research_agent:
            yield {
                'type': 'error',
                'content': 'ResearchAgent not initialized',
                'timestamp': datetime.now()
            }
            return
        
        try:
            workflow_start = time.time()
            
            async for event in self.research_agent.stream_query(query):
                # Track completion
                if any(node_name == "__end__" for node_name in event.keys()):
                    self.performance_stats["full_workflow_count"] += 1
                    workflow_time = time.time() - workflow_start
                    self._update_avg_time("full_workflow", workflow_time)
                
                # Process and yield event
                for node_name, node_data in event.items():
                    if node_name == "__end__":
                        yield {
                            'type': 'final',
                            'content': node_data,
                            'timestamp': datetime.now()
                        }
                    elif node_name == "planner":
                        yield {
                            'type': 'plan',
                            'content': node_data.get('plan', []),
                            'timestamp': datetime.now()
                        }
                    elif node_name == "agent":
                        yield {
                            'type': 'execution',
                            'content': node_data,
                            'timestamp': datetime.now()
                        }
                    elif node_name == "replan":
                        yield {
                            'type': 'replan',
                            'content': node_data,
                            'timestamp': datetime.now()
                        }
                    else:
                        yield {
                            'type': 'step',
                            'content': node_data,
                            'node': node_name,
                            'timestamp': datetime.now()
                        }
                        
        except Exception as e:
            yield {
                'type': 'error',
                'content': {
                    'error': f"Full workflow error: {str(e)}",
                    'traceback': traceback.format_exc()
                },
                'timestamp': datetime.now()
            }
    
    def _update_avg_time(self, workflow_type: str, time_taken: float):
        """Update average response time statistics."""
        avg_key = f"avg_{workflow_type}_time"
        count_key = f"{workflow_type}_count"
        
        if avg_key in self.performance_stats:
            current_avg = self.performance_stats[avg_key]
            count = self.performance_stats[count_key]
            
            # Calculate new average
            new_avg = ((current_avg * (count - 1)) + time_taken) / count
            self.performance_stats[avg_key] = new_avg
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics."""
        total_queries = self.performance_stats["fast_path_count"] + self.performance_stats["full_workflow_count"]
        
        return {
            **self.performance_stats,
            'total_queries': total_queries,
            'fast_path_percentage': (self.performance_stats["fast_path_count"] / max(1, total_queries)) * 100,
            'escalation_rate': (self.performance_stats["escalation_count"] / 
                               max(1, self.performance_stats["fast_path_count"])) * 100 if self.performance_stats["fast_path_count"] > 0 else 0
        }
    
    def get_processing_message(self, query: str, conversation_history: Optional[List[Dict]] = None) -> str:
        """Get appropriate processing message for user feedback."""
        return self.query_classifier.get_processing_message(query, conversation_history)
    
    def get_router_info(self) -> Dict[str, Any]:
        """Get information about the router state."""
        return {
            'initialized': self.is_initialized(),
            'research_agent_initialized': self.research_agent is not None,
            'es_client_connected': self.es_client is not None and self.es_client.ping() if self.es_client else False,
            'index_name': self.index_name,
            'performance_stats': self.get_performance_stats()
        }


# Convenience functions for easy usage
def process_hybrid_query(query: str, conversation_history: Optional[List[Dict]] = None, 
                        es_client: Optional[Elasticsearch] = None, 
                        index_name: str = "research-publications-static") -> Dict[str, Any]:
    """Process a query using the hybrid router."""
    router = HybridRouter(es_client=es_client, index_name=index_name)
    return router.process_query(query, conversation_history)


async def stream_hybrid_query(query: str, conversation_history: Optional[List[Dict]] = None,
                             es_client: Optional[Elasticsearch] = None,
                             index_name: str = "research-publications-static") -> AsyncIterator[Dict[str, Any]]:
    """Stream a query using the hybrid router."""
    router = HybridRouter(es_client=es_client, index_name=index_name)
    async for event in router.stream_query(query, conversation_history):
        yield event