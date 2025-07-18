# TOOL IMPLEMENTATION GUIDE

This guide provides comprehensive instructions for implementing new tools in the ES Agent system.

## Overview

The ES Agent system uses a modular tool architecture that allows for easy extension with new capabilities. Tools are self-contained units that perform specific tasks and return structured results.

## Architecture

### Key Components

1. **BaseTool** (src/tools/base.py)
   - Abstract base class for all tools
   - Requires `name` and `description` attributes
   - Must implement `async execute(**kwargs) -> ToolResult`

2. **ToolResult** (src/tools/base.py)
   - Standardized response format
   - Fields: success (bool), data (Any), error (Optional[str]), metadata (Dict)

3. **ToolRegistry** (src/tools/registry.py)
   - Central registry for tool management
   - Handles tool registration, categorization, and discovery
   - Provides tool lookup by name, category, or query relevance

4. **Factory** (src/core/factory.py)
   - Creates and configures tool registry
   - Auto-detects environment (mock vs real tools)
   - Handles fallback to mock tools if real tools fail

## Implementation Steps

### 1. Create Your Tool Class

```python
# src/tools/your_category/your_tool.py
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from src.tools.base import BaseTool, ToolResult

class YourToolInput(BaseModel):
    """Input schema for your tool."""
    param1: str = Field(..., description="Description of param1")
    param2: Optional[int] = Field(None, description="Optional param2")
    
class YourTool(BaseTool):
    """Tool for performing specific task."""
    
    name = "your_tool_name"
    description = """Clear description of what your tool does.
    Include what inputs it accepts and what it returns."""
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool logic."""
        try:
            # Validate input
            params = YourToolInput(**kwargs)
            
            # Implement your tool logic here
            result_data = await self._perform_operation(params)
            
            # Return structured result
            return ToolResult(
                success=True,
                data=result_data,
                metadata={
                    "tool_name": self.name,
                    "processed_items": len(result_data)
                }
            )
            
        except ValueError as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Invalid input: {str(e)}"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Unexpected error: {str(e)}"
            )
```

### 2. For External Service Tools (e.g., Elasticsearch)

If your tool interacts with external services, create a base class for service-specific tools:

```python
# src/tools/your_service/base.py
from src.tools.base import BaseTool
from tenacity import retry, stop_after_attempt, wait_exponential

class YourServiceBaseTool(BaseTool):
    """Base class for YourService tools."""
    
    def __init__(self, client):
        self.client = client
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def _execute_with_retry(self, operation):
        """Execute operation with retry logic."""
        return await operation()
```

### 3. Register Your Tool

Update the factory to include your tool:

```python
# src/core/factory.py
from src.tools.your_category.your_tool import YourTool

def create_tool_registry(use_mock_tools: bool = False) -> ToolRegistry:
    registry = ToolRegistry()
    
    if not use_mock_tools:
        # Register your real tool
        tool = YourTool()
        registry.register_tool(
            tool,
            category="your_category",
            metadata={"type": "your_type", "real": True}
        )
```

### 4. Create Mock Version (Optional but Recommended)

```python
# src/tools/mock_tools.py
class MockYourTool(BaseTool):
    """Mock version of YourTool for testing."""
    
    name = "your_tool_name"
    description = "Mock version of your tool"
    
    async def execute(self, **kwargs) -> ToolResult:
        # Return mock data
        return ToolResult(
            success=True,
            data={"mock": True, "result": "test data"},
            metadata={"tool_name": self.name, "mock": True}
        )
```

## Best Practices

### 1. Input Validation
- Use Pydantic models for input validation
- Provide clear field descriptions
- Include validation logic for business rules

### 2. Error Handling
- Catch specific exceptions and return meaningful error messages
- Always return ToolResult, never raise exceptions to caller
- Include error context in the error message

### 3. Async Implementation
- All tools must be async (use `async def execute`)
- Use `await` for I/O operations
- Consider concurrent operations where appropriate

### 4. Documentation
- Write clear docstrings for class and methods
- Include usage examples in docstrings
- Document expected inputs and outputs

### 5. Testing
```python
# tests/unit/tools/test_your_tool.py
import pytest
from src.tools.your_category.your_tool import YourTool

@pytest.mark.asyncio
async def test_your_tool_success():
    tool = YourTool()
    result = await tool.execute(param1="test", param2=42)
    
    assert result.success is True
    assert result.data is not None
    assert result.error is None

@pytest.mark.asyncio
async def test_your_tool_invalid_input():
    tool = YourTool()
    result = await tool.execute(invalid_param="test")
    
    assert result.success is False
    assert result.error is not None
```

## Integration with LLM

The system uses different LLMs for different purposes:

1. **Orchestrator LLM**: Determines if tools are needed
2. **Planner LLM**: Creates execution plans using available tools
3. **Tool LLM**: Simple tool-related operations
4. **Result Formatter LLM**: Formats tool results for users

Your tool will be automatically available to the planner once registered.

## Tool Discovery

Tools are discovered by the planner based on:
- Tool name and description
- Category matching
- Query keyword matching (simple for now)

Make sure your tool description clearly states:
- What the tool does
- What types of queries it handles
- What data it returns

## Example: SearchPublicationsTool

See `src/tools/elasticsearch/publications.py` for a complete example that:
- Validates complex input with Pydantic
- Builds Elasticsearch queries
- Handles errors gracefully
- Formats results appropriately
- Includes both class-based and decorator-based implementations

## LangChain Integration

To make your tool available as a LangChain tool:

```python
from langchain.tools import tool

@tool("your_tool_name", args_schema=YourToolInput)
async def your_tool_langchain(param1: str, param2: Optional[int] = None):
    """LangChain wrapper for your tool."""
    tool_instance = YourTool()
    result = await tool_instance.execute(param1=param1, param2=param2)
    
    if result.success:
        return result.data
    else:
        raise Exception(result.error)
```

## Debugging Tips

1. **Enable Debug Logging**
   ```python
   import logging
   logger = logging.getLogger(__name__)
   logger.setLevel(logging.DEBUG)
   ```

2. **Test in Isolation**
   ```python
   # Test your tool directly
   tool = YourTool()
   result = await tool.execute(test_params)
   print(result)
   ```

3. **Check Registration**
   ```python
   from src.core.factory import create_tool_registry
   registry = create_tool_registry()
   print(registry.list_tools())
   ```

4. **Use API Debug Endpoint**
   - GET /api/debug/tools - List all registered tools
   - GET /api/debug/plan - See execution plans

## Common Pitfalls

1. **Forgetting Async**: All execute methods must be async
2. **Raising Exceptions**: Always return ToolResult, don't raise
3. **Missing Validation**: Always validate inputs with Pydantic
4. **Poor Descriptions**: Tool won't be discovered if description is vague
5. **No Mock Version**: Makes testing difficult
6. **Synchronous I/O**: Use async libraries for external calls

## Future Enhancements

The current system has room for improvement:
- Tool composition and chaining
- More sophisticated tool discovery (semantic search)
- Tool-level caching
- Rate limiting and quotas
- Tool versioning
- Dynamic tool loading