"""LLM-specific test fixtures for conversational AI testing."""

import pytest
from unittest.mock import Mock, AsyncMock
from typing import Dict, Any, List


@pytest.fixture
def mock_llm():
    """Create a mock LLM for testing conversational responses."""
    llm = Mock()
    
    # Mock async predict method
    llm.apredict = AsyncMock()
    
    # Default conversational responses
    llm.apredict.return_value = "I'm a helpful research assistant. How can I help you today?"
    
    return llm


@pytest.fixture
def mock_llm_factory(mock_llm):
    """Create a mock LLM factory that returns mock LLMs."""
    factory = Mock()
    factory.create_orchestrator_llm = Mock(return_value=mock_llm)
    factory.create_planner_llm = Mock(return_value=mock_llm)
    factory.create_tool_llm = Mock(return_value=mock_llm)
    return factory


@pytest.fixture
def conversational_test_cases():
    """Test cases for conversational queries and expected LLM behaviors."""
    return [
        {
            "query": "What do you think about AI research?",
            "expected_llm_called": True,
            "expected_tools_called": False,
            "expected_response_contains": ["AI", "research"],
            "expected_confidence": 0.9
        },
        {
            "query": "How are you doing today?",
            "expected_llm_called": True,
            "expected_tools_called": False,
            "expected_response_contains": ["today"],
            "expected_confidence": 0.9
        },
        {
            "query": "Tell me about the future of machine learning",
            "expected_llm_called": True,
            "expected_tools_called": False,
            "expected_response_contains": ["machine learning"],
            "expected_confidence": 0.9
        },
        {
            "query": "Find publications by John Smith",
            "expected_llm_called": False,
            "expected_tools_called": True,
            "expected_response_contains": ["publications"],
            "expected_confidence": 0.8
        }
    ]


@pytest.fixture
def mock_llm_responses():
    """Predefined LLM responses for different query types."""
    return {
        "ai_research": "AI research is a fascinating field that's rapidly evolving. There are exciting developments in machine learning, natural language processing, and computer vision. Would you like me to search for specific research papers on any of these topics?",
        "greeting": "Hello! I'm doing well, thank you for asking. I'm here to help you with research queries and academic information. What would you like to explore today?",
        "future_ml": "Machine learning is advancing rapidly with developments in large language models, automated machine learning, and AI safety. The field is moving toward more interpretable and efficient models. Would you like me to find recent publications on any specific ML topic?",
        "default": "I'm a helpful research assistant. I can help you find academic publications, analyze research trends, and discuss various topics. What would you like to know about?"
    }