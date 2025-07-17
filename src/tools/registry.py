"""Tool registry for managing and discovering tools."""

from typing import Dict, List, Optional, Any
from src.tools.base import BaseTool


class ToolRegistry:
    """Registry for managing and discovering tools."""

    def __init__(self):
        """Initialize the tool registry."""
        self._tools: Dict[str, BaseTool] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._categories: Dict[str, List[str]] = {}

    def register_tool(
        self, tool: BaseTool, category: str, metadata: Dict[str, Any]
    ) -> None:
        """Register a tool with the registry.

        Args:
            tool: The tool to register
            category: Category for the tool
            metadata: Additional metadata for the tool

        Raises:
            ValueError: If tool name already exists
            TypeError: If tool is not a BaseTool instance
        """
        if not isinstance(tool, BaseTool):
            raise TypeError("Tool must be an instance of BaseTool")

        if tool.name in self._tools:
            raise ValueError(f"Tool with name '{tool.name}' already exists")

        self._tools[tool.name] = tool

        # Store metadata with category
        tool_metadata = metadata.copy()
        tool_metadata["category"] = category
        self._metadata[tool.name] = tool_metadata

        # Add to category index
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(tool.name)

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name.

        Args:
            name: Name of the tool

        Returns:
            The tool if found, None otherwise
        """
        return self._tools.get(name)

    def get_tool_metadata(self, name: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a tool.

        Args:
            name: Name of the tool

        Returns:
            Metadata dictionary if found, None otherwise
        """
        return self._metadata.get(name)

    def list_tools(self) -> List[str]:
        """List all registered tool names.

        Returns:
            List of tool names
        """
        return list(self._tools.keys())

    def get_all_tools(self) -> List[BaseTool]:
        """Get all registered tools.

        Returns:
            List of all registered tools
        """
        return list(self._tools.values())
    
    def get_available_tools(self) -> List[BaseTool]:
        """Get all available tools (alias for get_all_tools).

        Returns:
            List of all available tools
        """
        return self.get_all_tools()

    def find_tools_by_category(self, category: str) -> List[BaseTool]:
        """Find tools by category.

        Args:
            category: Category to search for

        Returns:
            List of tools in the category
        """
        if category not in self._categories:
            return []

        return [self._tools[tool_name] for tool_name in self._categories[category]]
    
    def get_tools_by_category(self, category: str) -> List[BaseTool]:
        """Get tools by category (alias for find_tools_by_category).

        Args:
            category: Category to search for

        Returns:
            List of tools in the category
        """
        return self.find_tools_by_category(category)

    def get_tools_for_query(
        self, query: str, categories: Optional[List[str]] = None
    ) -> List[BaseTool]:
        """Get tools that are relevant for a query.

        Args:
            query: The query string
            categories: Optional list of categories to filter by

        Returns:
            List of relevant tools
        """
        relevant_tools = []

        # Simple keyword matching for now
        query_lower = query.lower()
        keywords = ["publication", "research", "paper", "author", "search", "find"]

        for tool_name, tool in self._tools.items():
            # Check if tool is in requested categories
            if categories:
                tool_category = self._metadata[tool_name].get("category", "")
                if tool_category not in categories:
                    continue

            # Check if tool description or name matches query keywords
            tool_text = f"{tool.name} {tool.description}".lower()
            if any(keyword in query_lower for keyword in keywords) and any(
                keyword in tool_text for keyword in keywords
            ):
                relevant_tools.append(tool)

        return relevant_tools
