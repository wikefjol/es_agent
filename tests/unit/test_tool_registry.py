"""Tests for the Tool Registry component."""

import pytest
from unittest.mock import Mock, AsyncMock
from typing import Dict, Any

from src.tools.registry import ToolRegistry
from src.tools.base import BaseTool, ToolResult


class TestToolRegistry:
    """Test cases for ToolRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create a fresh ToolRegistry instance."""
        return ToolRegistry()

    @pytest.fixture
    def mock_tool(self):
        """Create a mock tool for testing."""
        tool = Mock(spec=BaseTool)
        tool.name = "test_tool"
        tool.description = "A test tool"
        tool.execute = AsyncMock(
            return_value=ToolResult(
                success=True, data={"test": "data"}, metadata={"execution_time": 0.1}
            )
        )
        return tool

    def test_registry_starts_empty(self, registry):
        """Test that registry initializes with no tools."""
        assert len(registry.list_tools()) == 0
        assert registry.get_all_tools() == []

    def test_register_tool_adds_to_registry(self, registry, mock_tool):
        """Test that registering a tool adds it to the registry."""
        registry.register_tool(mock_tool, category="test", metadata={})
        assert len(registry.list_tools()) == 1
        assert registry.get_tool("test_tool") == mock_tool

    def test_register_tool_prevents_duplicate_names(self, registry, mock_tool):
        """Test that registry prevents duplicate tool names."""
        registry.register_tool(mock_tool, category="test", metadata={})

        # Try to register another tool with the same name
        duplicate_tool = Mock(spec=BaseTool)
        duplicate_tool.name = "test_tool"
        duplicate_tool.description = "Another test tool"

        with pytest.raises(
            ValueError, match="Tool with name 'test_tool' already exists"
        ):
            registry.register_tool(duplicate_tool, category="test", metadata={})

    def test_register_tool_validates_tool_interface(self, registry):
        """Test that registry validates tool interface."""
        # Try to register something that's not a BaseTool
        invalid_tool = Mock()
        invalid_tool.name = "invalid_tool"

        with pytest.raises(TypeError, match="Tool must be an instance of BaseTool"):
            registry.register_tool(invalid_tool, category="test", metadata={})

    def test_find_tools_by_category(self, registry):
        """Test finding tools by category."""
        # Create tools in different categories
        tool1 = Mock(spec=BaseTool)
        tool1.name = "search_tool"
        tool1.description = "Search tool"

        tool2 = Mock(spec=BaseTool)
        tool2.name = "analysis_tool"
        tool2.description = "Analysis tool"

        registry.register_tool(tool1, category="search", metadata={})
        registry.register_tool(tool2, category="analysis", metadata={})

        search_tools = registry.find_tools_by_category("search")
        assert len(search_tools) == 1
        assert search_tools[0] == tool1

        analysis_tools = registry.find_tools_by_category("analysis")
        assert len(analysis_tools) == 1
        assert analysis_tools[0] == tool2

    def test_get_tools_for_query_basic(self, registry):
        """Test getting tools for a basic query."""
        tool = Mock(spec=BaseTool)
        tool.name = "search_publications"
        tool.description = "Search for research publications"

        registry.register_tool(tool, category="elasticsearch", metadata={})

        # This should return the tool since it's related to publications
        tools = registry.get_tools_for_query("find publications about machine learning")
        assert len(tools) == 1
        assert tools[0] == tool

    def test_get_tools_for_query_with_categories(self, registry):
        """Test getting tools for query with category filtering."""
        tool1 = Mock(spec=BaseTool)
        tool1.name = "search_publications"
        tool1.description = "Search for research publications"

        tool2 = Mock(spec=BaseTool)
        tool2.name = "web_search"
        tool2.description = "Search the web"

        registry.register_tool(tool1, category="elasticsearch", metadata={})
        registry.register_tool(tool2, category="web", metadata={})

        # Filter by category
        tools = registry.get_tools_for_query(
            "find publications", categories=["elasticsearch"]
        )
        assert len(tools) == 1
        assert tools[0] == tool1

    def test_get_tool_returns_none_for_nonexistent(self, registry):
        """Test that get_tool returns None for non-existent tool."""
        assert registry.get_tool("nonexistent_tool") is None

    def test_registry_handles_tool_versioning(self, registry):
        """Test that registry handles tool versioning in metadata."""
        tool = Mock(spec=BaseTool)
        tool.name = "versioned_tool"
        tool.description = "A versioned tool"

        metadata = {"version": "1.0.0", "author": "test"}
        registry.register_tool(tool, category="test", metadata=metadata)

        # Check that metadata is stored correctly
        stored_metadata = registry.get_tool_metadata("versioned_tool")
        assert stored_metadata["version"] == "1.0.0"
        assert stored_metadata["author"] == "test"
        assert stored_metadata["category"] == "test"

    def test_list_tools_returns_tool_names(self, registry, mock_tool):
        """Test that list_tools returns tool names."""
        registry.register_tool(mock_tool, category="test", metadata={})

        tool_names = registry.list_tools()
        assert tool_names == ["test_tool"]

    def test_get_all_tools_returns_tool_objects(self, registry, mock_tool):
        """Test that get_all_tools returns actual tool objects."""
        registry.register_tool(mock_tool, category="test", metadata={})

        tools = registry.get_all_tools()
        assert len(tools) == 1
        assert tools[0] == mock_tool
