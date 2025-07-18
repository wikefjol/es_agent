"""Realistic test data fixtures for comprehensive testing."""

import pytest
from datetime import datetime, timedelta
from typing import Dict, List, Any
from unittest.mock import Mock

from src.models.schemas import (
    ConversationContext,
    ExecutionContext,
    ExecutionPlan,
    PlanStep,
    AgentResponse,
    ExecutorConfig,
    FallbackStrategy,
    Condition,
)
from src.tools.base import ToolResult


class RealisticTestData:
    """Container for realistic test data."""

    # Realistic author data
    AUTHORS = {
        "john_smith": {
            "name": "John Smith",
            "affiliation": "MIT",
            "email": "j.smith@mit.edu",
            "total_publications": 47,
            "h_index": 23,
            "years_active": [2010, 2024],
            "primary_fields": ["machine learning", "computer vision"],
        },
        "jane_doe": {
            "name": "Jane Doe",
            "affiliation": "Stanford University",
            "email": "jane.doe@stanford.edu",
            "total_publications": 89,
            "h_index": 31,
            "years_active": [2008, 2024],
            "primary_fields": ["natural language processing", "deep learning"],
        },
        "robert_johnson": {
            "name": "Robert Johnson",
            "affiliation": "Google Research",
            "email": "r.johnson@google.com",
            "total_publications": 23,
            "h_index": 18,
            "years_active": [2015, 2024],
            "primary_fields": ["reinforcement learning", "robotics"],
        },
    }

    # Realistic publication data
    PUBLICATIONS = {
        "pub_001": {
            "title": "Deep Learning for Computer Vision: A Comprehensive Survey",
            "authors": ["John Smith", "Alice Brown"],
            "venue": "IEEE Transactions on Pattern Analysis and Machine Intelligence",
            "year": 2023,
            "citations": 142,
            "abstract": "This paper presents a comprehensive survey of deep learning techniques applied to computer vision problems...",
            "keywords": ["deep learning", "computer vision", "neural networks"],
            "doi": "10.1109/TPAMI.2023.001",
            "field": "computer vision",
        },
        "pub_002": {
            "title": "Attention Mechanisms in Natural Language Processing",
            "authors": ["Jane Doe", "Michael Chen"],
            "venue": "Annual Meeting of the Association for Computational Linguistics",
            "year": 2022,
            "citations": 89,
            "abstract": "We propose novel attention mechanisms for improving natural language understanding tasks...",
            "keywords": ["attention", "nlp", "transformers"],
            "doi": "10.18653/v1/2022.acl-long.123",
            "field": "natural language processing",
        },
        "pub_003": {
            "title": "Reinforcement Learning in Robotics: Recent Advances",
            "authors": ["Robert Johnson", "Sarah Wilson"],
            "venue": "International Conference on Robotics and Automation",
            "year": 2024,
            "citations": 15,
            "abstract": "This work reviews recent advances in applying reinforcement learning to robotic systems...",
            "keywords": ["reinforcement learning", "robotics", "control"],
            "doi": "10.1109/ICRA.2024.001",
            "field": "robotics",
        },
    }

    # Realistic field statistics
    FIELD_STATISTICS = {
        "machine learning": {
            "total_publications": 15432,
            "total_authors": 8901,
            "avg_citations_per_paper": 12.4,
            "top_venues": ["NeurIPS", "ICML", "ICLR"],
            "trending_topics": [
                "transformer models",
                "few-shot learning",
                "federated learning",
            ],
            "publication_growth_rate": 0.23,
            "yearly_stats": {
                "2023": {"publications": 2341, "authors": 1234},
                "2022": {"publications": 1987, "authors": 1098},
                "2021": {"publications": 1654, "authors": 923},
            },
        },
        "computer vision": {
            "total_publications": 12876,
            "total_authors": 7543,
            "avg_citations_per_paper": 14.2,
            "top_venues": ["CVPR", "ICCV", "ECCV"],
            "trending_topics": [
                "vision transformers",
                "object detection",
                "image segmentation",
            ],
            "publication_growth_rate": 0.18,
            "yearly_stats": {
                "2023": {"publications": 1923, "authors": 1087},
                "2022": {"publications": 1678, "authors": 945},
                "2021": {"publications": 1432, "authors": 823},
            },
        },
        "natural language processing": {
            "total_publications": 9876,
            "total_authors": 5432,
            "avg_citations_per_paper": 16.8,
            "top_venues": ["ACL", "EMNLP", "NAACL"],
            "trending_topics": [
                "large language models",
                "multilingual nlp",
                "dialogue systems",
            ],
            "publication_growth_rate": 0.31,
            "yearly_stats": {
                "2023": {"publications": 1567, "authors": 891},
                "2022": {"publications": 1234, "authors": 723},
                "2021": {"publications": 987, "authors": 612},
            },
        },
    }

    # Realistic query patterns
    QUERY_PATTERNS = {
        "author_search": [
            "Find publications by John Smith",
            "What papers has Jane Doe published?",
            "Show me Robert Johnson's research",
            "List all publications by Dr. Smith from MIT",
        ],
        "topic_search": [
            "Find papers on machine learning",
            "Search for computer vision research",
            "What are the latest papers on NLP?",
            "Show me deep learning publications from 2023",
        ],
        "statistics": [
            "Get statistics for machine learning field",
            "How many papers were published in computer vision?",
            "Show me trends in NLP research",
            "What's the growth rate for AI research?",
        ],
        "complex": [
            "Find John Smith's papers and get ML statistics",
            "Search for computer vision papers and show field trends",
            "Get Jane Doe's publications and compare with field averages",
        ],
    }

    # Realistic conversation contexts
    CONVERSATION_CONTEXTS = {
        "research_session": {
            "session_id": "research_123",
            "user_id": "researcher_001",
            "session_type": "academic_research",
            "start_time": datetime.now() - timedelta(minutes=15),
            "total_queries": 5,
            "successful_queries": 4,
            "failed_queries": 1,
        },
        "quick_lookup": {
            "session_id": "quick_456",
            "user_id": "student_002",
            "session_type": "quick_reference",
            "start_time": datetime.now() - timedelta(minutes=2),
            "total_queries": 1,
            "successful_queries": 1,
            "failed_queries": 0,
        },
        "deep_analysis": {
            "session_id": "analysis_789",
            "user_id": "analyst_003",
            "session_type": "comprehensive_analysis",
            "start_time": datetime.now() - timedelta(hours=1),
            "total_queries": 12,
            "successful_queries": 10,
            "failed_queries": 2,
        },
    }


@pytest.fixture
def realistic_authors():
    """Provide realistic author data."""
    return RealisticTestData.AUTHORS


@pytest.fixture
def realistic_publications():
    """Provide realistic publication data."""
    return RealisticTestData.PUBLICATIONS


@pytest.fixture
def realistic_field_statistics():
    """Provide realistic field statistics."""
    return RealisticTestData.FIELD_STATISTICS


@pytest.fixture
def realistic_queries():
    """Provide realistic query patterns."""
    return RealisticTestData.QUERY_PATTERNS


@pytest.fixture
def realistic_conversation_contexts():
    """Provide realistic conversation contexts."""
    return RealisticTestData.CONVERSATION_CONTEXTS


@pytest.fixture
def realistic_tool_results():
    """Generate realistic tool results."""

    def _generate_tool_result(
        tool_name: str, query_params: Dict[str, Any]
    ) -> ToolResult:
        """Generate realistic tool result based on tool name and parameters."""

        if tool_name == "search_by_author":
            author_name = query_params.get("author", "Unknown Author")
            author_data = None

            # Find matching author
            for author_key, author_info in RealisticTestData.AUTHORS.items():
                if author_info["name"].lower() == author_name.lower():
                    author_data = author_info
                    break

            if author_data:
                # Generate publications for this author
                publications = []
                for pub_id, pub_data in RealisticTestData.PUBLICATIONS.items():
                    if author_data["name"] in pub_data["authors"]:
                        publications.append(pub_data)

                return ToolResult(
                    success=True,
                    data={
                        "author": author_data,
                        "publications": publications,
                        "total_publications": len(publications),
                        "query_timestamp": datetime.now().isoformat(),
                    },
                    metadata={"tool_name": tool_name, "execution_time": 0.234},
                )
            else:
                return ToolResult(
                    success=False,
                    error=f"Author '{author_name}' not found in database",
                    data=None,
                    metadata={"tool_name": tool_name, "execution_time": 0.123},
                )

        elif tool_name == "search_publications":
            query = query_params.get("query", "")
            limit = query_params.get("limit", 10)

            # Find matching publications
            matching_pubs = []
            for pub_id, pub_data in RealisticTestData.PUBLICATIONS.items():
                if (
                    query.lower() in pub_data["title"].lower()
                    or query.lower() in pub_data["abstract"].lower()
                    or any(
                        keyword.lower() in query.lower()
                        for keyword in pub_data["keywords"]
                    )
                ):
                    matching_pubs.append(pub_data)

            # Limit results
            limited_pubs = matching_pubs[:limit]

            return ToolResult(
                success=True,
                data={
                    "publications": limited_pubs,
                    "total_found": len(matching_pubs),
                    "total_returned": len(limited_pubs),
                    "query": query,
                    "query_timestamp": datetime.now().isoformat(),
                },
                metadata={"tool_name": tool_name, "execution_time": 0.456},
            )

        elif tool_name == "get_field_statistics":
            field = query_params.get("field", "")

            field_data = RealisticTestData.FIELD_STATISTICS.get(field.lower())
            if field_data:
                return ToolResult(
                    success=True,
                    data={
                        "field": field,
                        "statistics": field_data,
                        "query_timestamp": datetime.now().isoformat(),
                    },
                    metadata={"tool_name": tool_name, "execution_time": 0.345},
                )
            else:
                return ToolResult(
                    success=False,
                    error=f"No statistics available for field '{field}'",
                    data=None,
                    metadata={"tool_name": tool_name, "execution_time": 0.123},
                )

        else:
            return ToolResult(
                success=False,
                error=f"Unknown tool: {tool_name}",
                data=None,
                metadata={"tool_name": tool_name, "execution_time": 0.001},
            )

    return _generate_tool_result


@pytest.fixture
def realistic_conversation_history():
    """Generate realistic conversation history."""
    return [
        {
            "role": "user",
            "content": "Find publications by John Smith",
            "timestamp": datetime.now() - timedelta(minutes=10),
        },
        {
            "role": "assistant",
            "content": "I found 2 publications by John Smith. Here are the details...",
            "timestamp": datetime.now() - timedelta(minutes=9, seconds=45),
        },
        {
            "role": "user",
            "content": "What about his recent work on computer vision?",
            "timestamp": datetime.now() - timedelta(minutes=8),
        },
        {
            "role": "assistant",
            "content": "John Smith's recent computer vision work includes...",
            "timestamp": datetime.now() - timedelta(minutes=7, seconds=30),
        },
        {
            "role": "user",
            "content": "Can you get statistics for the computer vision field?",
            "timestamp": datetime.now() - timedelta(minutes=5),
        },
    ]


@pytest.fixture
def realistic_execution_contexts():
    """Generate realistic execution contexts."""
    return {
        "standard": ExecutionContext(
            session_id="research_session_001",
            user_query="Find publications by John Smith",
            available_tools=[
                "search_by_author",
                "search_publications",
                "get_field_statistics",
            ],
            timeout_seconds=30,
            parallel_execution=True,
            metadata={
                "user_id": "researcher_001",
                "request_timestamp": datetime.now().isoformat(),
                "user_preferences": {"include_abstracts": True, "max_results": 20},
            },
        ),
        "limited": ExecutionContext(
            session_id="quick_lookup_002",
            user_query="Quick search for AI papers",
            available_tools=["search_publications"],
            timeout_seconds=10,
            parallel_execution=False,
            metadata={
                "user_id": "student_002",
                "request_timestamp": datetime.now().isoformat(),
                "user_preferences": {"include_abstracts": False, "max_results": 5},
            },
        ),
        "comprehensive": ExecutionContext(
            session_id="deep_analysis_003",
            user_query="Comprehensive analysis of machine learning field",
            available_tools=[
                "search_publications",
                "get_field_statistics",
                "search_by_author",
            ],
            timeout_seconds=120,
            parallel_execution=True,
            metadata={
                "user_id": "analyst_003",
                "request_timestamp": datetime.now().isoformat(),
                "user_preferences": {"include_abstracts": True, "max_results": 100},
                "analysis_type": "comprehensive",
            },
        ),
    }


@pytest.fixture
def realistic_execution_plans():
    """Generate realistic execution plans."""
    return {
        "simple_author_search": ExecutionPlan(
            steps=[
                PlanStep(
                    id="author_search",
                    tool_name="search_by_author",
                    parameters={"author": "John Smith"},
                    description="Search for publications by John Smith",
                )
            ],
            expected_outputs={"author_publications": "author_search"},
            fallback_strategies={
                "search_by_author": FallbackStrategy(
                    strategy_type="retry", max_retries=2, retry_delay=1.0
                )
            },
        ),
        "complex_analysis": ExecutionPlan(
            steps=[
                PlanStep(
                    id="author_search",
                    tool_name="search_by_author",
                    parameters={"author": "John Smith"},
                    description="Find John Smith's publications",
                ),
                PlanStep(
                    id="field_stats",
                    tool_name="get_field_statistics",
                    parameters={"field": "machine learning"},
                    description="Get ML field statistics",
                    dependencies=["author_search"],
                    condition=Condition(
                        field="total_publications", operator="gt", value=0
                    ),
                ),
                PlanStep(
                    id="topic_search",
                    tool_name="search_publications",
                    parameters={"query": "machine learning", "limit": 10},
                    description="Search for recent ML papers",
                ),
            ],
            expected_outputs={
                "author_publications": "author_search",
                "field_statistics": "field_stats",
                "related_papers": "topic_search",
            },
            fallback_strategies={
                "search_by_author": FallbackStrategy(
                    strategy_type="retry", max_retries=2
                ),
                "get_field_statistics": FallbackStrategy(strategy_type="skip"),
                "search_publications": FallbackStrategy(
                    strategy_type="retry", max_retries=1
                ),
            },
        ),
    }


@pytest.fixture
def realistic_error_scenarios():
    """Generate realistic error scenarios."""
    return {
        "network_timeout": {
            "tool_name": "search_publications",
            "error_type": "timeout",
            "error_message": "Request timed out after 30 seconds",
            "retry_count": 2,
            "recovery_strategy": "retry_with_backoff",
        },
        "author_not_found": {
            "tool_name": "search_by_author",
            "error_type": "not_found",
            "error_message": "Author 'Unknown Person' not found in database",
            "retry_count": 0,
            "recovery_strategy": "suggest_alternatives",
        },
        "invalid_field": {
            "tool_name": "get_field_statistics",
            "error_type": "invalid_parameter",
            "error_message": "Field 'invalid_field' is not supported",
            "retry_count": 0,
            "recovery_strategy": "validate_input",
        },
        "rate_limit": {
            "tool_name": "search_publications",
            "error_type": "rate_limit",
            "error_message": "Rate limit exceeded. Please wait 60 seconds",
            "retry_count": 1,
            "recovery_strategy": "exponential_backoff",
        },
    }
