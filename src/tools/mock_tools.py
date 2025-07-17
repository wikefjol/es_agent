"""Mock tools for testing the agent system."""

import asyncio
from typing import Any, Dict, List
from src.tools.base import BaseTool, ToolResult


class MockSearchPublicationsTool(BaseTool):
    """Mock tool for searching publications."""

    def __init__(self):
        super().__init__(
            name="search_publications",
            description="Search for research publications by query, author, or topic",
        )
        self._mock_data = [
            {
                "title": "Machine Learning in Healthcare",
                "abstract": "This paper explores the applications of machine learning in healthcare systems.",
                "authors": ["John Smith", "Jane Doe"],
                "year": 2023,
                "publication_type": "journal",
                "doi": "10.1234/ml-healthcare-2023",
                "keywords": ["machine learning", "healthcare", "AI"],
            },
            {
                "title": "Deep Learning for Computer Vision",
                "abstract": "A comprehensive review of deep learning techniques for computer vision tasks.",
                "authors": ["Alice Johnson", "Bob Wilson"],
                "year": 2023,
                "publication_type": "conference",
                "doi": "10.1234/dl-cv-2023",
                "keywords": ["deep learning", "computer vision", "neural networks"],
            },
            {
                "title": "Natural Language Processing Advances",
                "abstract": "Recent advances in natural language processing and their applications.",
                "authors": ["John Smith", "Carol Brown"],
                "year": 2022,
                "publication_type": "journal",
                "doi": "10.1234/nlp-advances-2022",
                "keywords": ["NLP", "transformers", "language models"],
            },
        ]

    async def execute(self, **kwargs) -> ToolResult:
        """Execute the mock search."""
        query = kwargs.get("query", "")
        author = kwargs.get("author", "")
        topic = kwargs.get("topic", "")
        limit = kwargs.get("limit", 10)

        # Simulate some processing time
        await asyncio.sleep(0.1)

        results = []
        for pub in self._mock_data:
            match = False

            # Check query match
            if query and (
                query.lower() in pub["title"].lower()
                or query.lower() in pub["abstract"].lower()
                or any(query.lower() in k.lower() for k in pub["keywords"])
            ):
                match = True

            # Check author match
            if author and any(author.lower() in a.lower() for a in pub["authors"]):
                match = True

            # Check topic/keyword match
            if topic and any(topic.lower() in k.lower() for k in pub["keywords"]):
                match = True

            # If no filters provided, return all
            if not query and not author and not topic:
                match = True

            if match:
                results.append(pub)

        # Apply limit
        results = results[:limit]

        return ToolResult(
            success=True,
            data={
                "publications": results,
                "total_found": len(results),
                "query_info": {
                    "query": query,
                    "author": author,
                    "topic": topic,
                    "limit": limit,
                },
            },
            metadata={"execution_time": 0.1, "tool": "search_publications"},
        )


class MockSearchByAuthorTool(BaseTool):
    """Mock tool for searching by author."""

    def __init__(self):
        super().__init__(
            name="search_by_author",
            description="Search for publications by a specific author",
        )
        self._mock_authors = {
            "john smith": {
                "name": "John Smith",
                "publications": [
                    {"title": "Machine Learning in Healthcare", "year": 2023},
                    {"title": "Natural Language Processing Advances", "year": 2022},
                ],
                "total_publications": 2,
                "main_topics": ["machine learning", "healthcare", "NLP"],
            },
            "jane doe": {
                "name": "Jane Doe",
                "publications": [
                    {"title": "Machine Learning in Healthcare", "year": 2023}
                ],
                "total_publications": 1,
                "main_topics": ["machine learning", "healthcare"],
            },
        }

    async def execute(self, **kwargs) -> ToolResult:
        """Execute the mock author search."""
        author_name = kwargs.get("author", "").lower()
        fuzzy_match = kwargs.get("fuzzy_match", False)

        # Simulate processing time
        await asyncio.sleep(0.1)

        if author_name in self._mock_authors:
            author_data = self._mock_authors[author_name]
            return ToolResult(
                success=True,
                data=author_data,
                metadata={"execution_time": 0.1, "tool": "search_by_author"},
            )

        # If fuzzy matching is enabled, try partial matches
        if fuzzy_match:
            for key, data in self._mock_authors.items():
                if author_name in key or key in author_name:
                    return ToolResult(
                        success=True,
                        data=data,
                        metadata={
                            "execution_time": 0.1,
                            "tool": "search_by_author",
                            "fuzzy_match": True,
                        },
                    )

        return ToolResult(
            success=False,
            data=None,
            error=f"Author '{author_name}' not found",
            metadata={"execution_time": 0.1, "tool": "search_by_author"},
        )


class MockGetFieldStatisticsTool(BaseTool):
    """Mock tool for getting field statistics."""

    def __init__(self):
        super().__init__(
            name="get_field_statistics",
            description="Get statistics about research fields and topics",
        )
        self._mock_stats = {
            "machine learning": {
                "total_publications": 1247,
                "yearly_trend": {"2020": 234, "2021": 345, "2022": 456, "2023": 212},
                "top_journals": [
                    {"name": "Machine Learning Journal", "count": 234},
                    {"name": "AI Research", "count": 198},
                ],
                "related_topics": ["deep learning", "neural networks", "AI"],
            },
            "healthcare": {
                "total_publications": 2345,
                "yearly_trend": {"2020": 456, "2021": 567, "2022": 678, "2023": 644},
                "top_journals": [
                    {"name": "Healthcare Technology", "count": 456},
                    {"name": "Medical AI", "count": 321},
                ],
                "related_topics": ["medical imaging", "clinical decision support"],
            },
        }

    async def execute(self, **kwargs) -> ToolResult:
        """Execute the mock statistics lookup."""
        field = kwargs.get("field", "").lower()
        include_trends = kwargs.get("include_trends", True)

        # Simulate processing time
        await asyncio.sleep(0.2)

        if field in self._mock_stats:
            stats = self._mock_stats[field].copy()

            if not include_trends:
                stats.pop("yearly_trend", None)

            return ToolResult(
                success=True,
                data=stats,
                metadata={"execution_time": 0.2, "tool": "get_field_statistics"},
            )

        return ToolResult(
            success=False,
            data=None,
            error=f"Statistics for field '{field}' not found",
            metadata={"execution_time": 0.2, "tool": "get_field_statistics"},
        )


class MockSlowTool(BaseTool):
    """Mock tool that simulates slow operations for timeout testing."""

    def __init__(self):
        super().__init__(
            name="slow_tool", description="A tool that takes a long time to execute"
        )

    async def execute(self, **kwargs) -> ToolResult:
        """Execute with configurable delay."""
        delay = kwargs.get("delay", 5.0)
        await asyncio.sleep(delay)

        return ToolResult(
            success=True,
            data={"message": f"Completed after {delay} seconds"},
            metadata={"execution_time": delay, "tool": "slow_tool"},
        )


class MockFailingTool(BaseTool):
    """Mock tool that simulates failures for error handling testing."""

    def __init__(self):
        super().__init__(
            name="failing_tool",
            description="A tool that fails for testing error handling",
        )
        self._call_count = 0

    async def execute(self, **kwargs) -> ToolResult:
        """Execute with configurable failure behavior."""
        self._call_count += 1

        failure_mode = kwargs.get("failure_mode", "always")
        fail_after = kwargs.get("fail_after", 1)

        if failure_mode == "always":
            return ToolResult(
                success=False,
                data=None,
                error="This tool always fails",
                metadata={
                    "execution_time": 0.1,
                    "tool": "failing_tool",
                    "call_count": self._call_count,
                },
            )
        elif failure_mode == "after_n_calls" and self._call_count >= fail_after:
            return ToolResult(
                success=False,
                data=None,
                error=f"Tool failed after {fail_after} calls",
                metadata={
                    "execution_time": 0.1,
                    "tool": "failing_tool",
                    "call_count": self._call_count,
                },
            )
        else:
            return ToolResult(
                success=True,
                data={"message": f"Success on call {self._call_count}"},
                metadata={
                    "execution_time": 0.1,
                    "tool": "failing_tool",
                    "call_count": self._call_count,
                },
            )


def create_mock_tools() -> List[BaseTool]:
    """Create all mock tools for testing."""
    return [
        MockSearchPublicationsTool(),
        MockSearchByAuthorTool(),
        MockGetFieldStatisticsTool(),
        MockSlowTool(),
        MockFailingTool(),
    ]
