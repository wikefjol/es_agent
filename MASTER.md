# Technical Specification: Adaptive Plan-and-Execute Agent System

## Project Overview
Build a conversational agent system that uses plan-and-execute architecture with adaptive replanning and memory management. The system must handle complex research queries by orchestrating multiple tools and maintaining context across conversation turns.

## Virtual Environment & git
A virtual environment "venv" has been created. An empty requirements.txt file has been created as well. Also the following has been written in terminal:

```
filipberntsson@mbp:~/Dev/es_agent$ git init
hint: Using 'master' as the name for the initial branch. This default branch name
hint: is subject to change. To configure the initial branch name to use in all
hint: of your new repositories, which will suppress this warning, call:
hint:
hint:   git config --global init.defaultBranch <name>
hint:
hint: Names commonly chosen instead of 'master' are 'main', 'trunk' and
hint: 'development'. The just-created branch can be renamed via this command:
hint:
hint:   git branch -m <name>
Initialized empty Git repository in /Users/filipberntsson/Dev/es_agent/.git/
filipberntsson@mbp:~/Dev/es_agent$ echo "# es_agent" >> README.md
filipberntsson@mbp:~/Dev/es_agent$ git add README.md
filipberntsson@mbp:~/Dev/es_agent$ git commit -m "first commit"
git branch -M main
git remote add origin https://github.com/wikefjol/es_agent.git
git push -u origin main[master (root-commit) cee412a] first commit
 1 file changed, 1 insertion(+)
 create mode 100644 README.md
filipberntsson@mbp:~/Dev/es_agent$ git branch -M main
filipberntsson@mbp:~/Dev/es_agent$ git remote add origin https://github.com/wikefjol/es_agent.git
filipberntsson@mbp:~/Dev/es_agent$ git push -u origin main
Enumerating objects: 3, done.
Counting objects: 100% (3/3), done.
Writing objects: 100% (3/3), 219 bytes | 219.00 KiB/s, done.
Total 3 (delta 0), reused 0 (delta 0), pack-reused 0 (from 0)
To https://github.com/wikefjol/es_agent.git
 * [new branch]      main -> main
branch 'main' set up to track 'origin/main'.
filipberntsson@mbp:~/Dev/es_agent$ 
```

You should use the venv, and all libraries packages should be in the requirements.txt. Use git to keep version control tidy and clear.

## Git Workflow Requirements
- Create feature branches for each phase: `feature/phase-1-core-infrastructure`
- Commit after each test file creation and after making tests pass
- Use conventional commits: `test: add tool registry tests`, `feat: implement tool registry`
- Push changes at the end of each working session

## Expected Project Structure
```
es_agent/
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── orchestrator.py
│   │   ├── planner.py
│   │   ├── executor.py
│   │   └── context_manager.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── registry.py
│   │   └── elasticsearch/
│   │       ├── __init__.py
│   │       └── publications.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py
│   └── utils/
│       ├── __init__.py
│       └── llm_factory.py
├── api/                        # NEW: Phase 5 API Layer
│   ├── __init__.py
│   ├── main.py                 # FastAPI application
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── chat.py            # Chat endpoints
│   │   ├── health.py          # Health check endpoints
│   │   └── debug.py           # Debug endpoints
│   ├── websocket.py           # WebSocket handlers
│   ├── middleware.py          # CORS, logging middleware
│   └── static/                # Demo interface files
│       ├── index.html
│       ├── style.css
│       └── app.js
├── scripts/                   # NEW: Deployment scripts
│   ├── run_demo.py           # Local demo server
│   ├── run_server.py         # Production server
│   └── deploy.py             # University deployment
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_orchestrator.py
│   │   ├── test_planner.py
│   │   ├── test_executor.py
│   │   ├── test_context_manager.py
│   │   └── test_tool_registry.py
│   ├── integration/
│   │   └── test_integration.py
│   └── api/                  # NEW: API tests
│       ├── test_routes.py
│       ├── test_websocket.py
│       └── test_integration_api.py
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
└── pytest.ini
```

## Required .gitignore
```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
.env

# Testing
.coverage
.pytest_cache/
htmlcov/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Project specific
logs/
*.log
```

## Development Methodology
**Test-Driven Development (TDD) is mandatory**. For each component:
1. Write failing tests first
2. Implement minimal code to pass tests
3. Refactor while keeping tests green
4. Maintain >90% test coverage

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      API Gateway                              │
├─────────────────────────────────────────────────────────────┤
│                   Session Manager                             │
├─────────────────────────────────────────────────────────────┤
│                 Orchestrator Agent                            │
├──────────────┬────────────────┬──────────────────────────────┤
│   Planner    │   Executor     │   Context Manager            │
├──────────────┴────────────────┴──────────────────────────────┤
│                    Tool Registry                              │
├─────────────────────────────────────────────────────────────┤
│   Research DB Tools  │  Web Search  │  Future Tools          │
└─────────────────────────────────────────────────────────────┘
```

## Core Components Specifications

### 1. Orchestrator Agent
**Purpose**: Main entry point that routes queries and manages conversation flow

**Test Cases**:
```python
# test_orchestrator.py
- test_orchestrator_identifies_new_query_requiring_tools()
- test_orchestrator_uses_cached_results_for_similar_query()
- test_orchestrator_handles_clarification_questions()
- test_orchestrator_maintains_conversation_context()
- test_orchestrator_handles_invalid_queries()
```

**Interface**:
```python
class OrchestratorAgent:
    async def process_query(
        self, 
        query: str, 
        session_id: str
    ) -> AgentResponse
    
    def _requires_new_tools(
        self, 
        query: str, 
        context: ConversationContext
    ) -> bool
```

**Implementation Requirements**:
- Use LangChain's ConversationSummaryBufferMemory
- Implement semantic similarity check (threshold: 0.85) using sentence-transformers
- Return structured AgentResponse with sources, confidence, and metadata

### 2. Planning Agent
**Purpose**: Creates and adapts execution plans based on available tools and context

**Test Cases**:
```python
# test_planner.py
- test_planner_creates_simple_linear_plan()
- test_planner_creates_plan_with_dependencies()
- test_planner_creates_conditional_plan()
- test_planner_adapts_plan_after_tool_failure()
- test_planner_validates_tool_availability()
- test_planner_handles_ambiguous_queries()
```

**Interface**:
```python
class PlanningAgent:
    def create_plan(
        self, 
        query: str, 
        available_tools: List[Tool],
        context: Optional[Context]
    ) -> ExecutionPlan
    
    def adapt_plan(
        self, 
        original_plan: ExecutionPlan,
        execution_results: List[ToolResult],
        failure_point: int
    ) -> ExecutionPlan
```

**Plan Structure**:
```python
@dataclass
class ExecutionPlan:
    steps: List[PlanStep]
    expected_outputs: Dict[str, OutputSchema]
    fallback_strategies: Dict[str, FallbackStrategy]
    
@dataclass
class PlanStep:
    id: str
    tool_name: str
    parameters: Dict[str, Any]
    dependencies: List[str]  # IDs of steps that must complete first
    condition: Optional[Condition]  # For conditional execution
```

### 3. Executor
**Purpose**: Executes plans with retry logic and error handling

**Test Cases**:
```python
# test_executor.py
- test_executor_runs_simple_plan_successfully()
- test_executor_handles_tool_timeout()
- test_executor_retries_failed_tool_calls()
- test_executor_respects_dependency_order()
- test_executor_evaluates_conditions_correctly()
- test_executor_collects_all_results()
- test_executor_stops_on_critical_failure()
```

**Interface**:
```python
class Executor:
    async def execute_plan(
        self,
        plan: ExecutionPlan,
        context: ExecutionContext
    ) -> ExecutionResult
    
    async def execute_step(
        self,
        step: PlanStep,
        previous_results: Dict[str, ToolResult]
    ) -> ToolResult
```

**Configuration**:
```python
@dataclass
class ExecutorConfig:
    max_retries: int = 3
    timeout_seconds: int = 30
    parallel_execution: bool = True
    retry_delay_seconds: int = 2
```

### 4. Context Manager
**Purpose**: Manages conversation memory and tool result caching

**Test Cases**:
```python
# test_context_manager.py
- test_context_stores_tool_results()
- test_context_retrieves_relevant_cached_results()
- test_context_expires_old_cache_entries()
- test_context_calculates_similarity_correctly()
- test_context_handles_large_results()
- test_context_persists_across_sessions()
```

**Interface**:
```python
class ContextManager:
    def store_result(
        self,
        session_id: str,
        tool_name: str,
        parameters: Dict,
        result: Any,
        metadata: Dict
    ) -> str  # cache_key
    
    def find_relevant_results(
        self,
        session_id: str,
        query: str,
        similarity_threshold: float = 0.85
    ) -> List[CachedResult]
    
    def get_conversation_summary(
        self,
        session_id: str
    ) -> str
```

### 5. Tool Registry
**Purpose**: Dynamic tool registration and discovery

**Test Cases**:
```python
# test_tool_registry.py
- test_registry_registers_tool_with_metadata()
- test_registry_prevents_duplicate_names()
- test_registry_validates_tool_interface()
- test_registry_finds_tools_by_category()
- test_registry_handles_tool_versioning()
```

**Interface**:
```python
class ToolRegistry:
    def register_tool(
        self,
        tool: BaseTool,
        category: str,
        metadata: Dict
    ) -> None
    
    def get_tools_for_query(
        self,
        query: str,
        categories: Optional[List[str]] = None
    ) -> List[BaseTool]
```

## Tool Implementation Specifications

### Minimal Tool Interface Specification
```python
# tool_interface_spec.py
"""
This is the interface ALL tools must implement.
The coding agent should create mock implementations first for testing.
"""

from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Any, Dict, Optional

class ToolResult(BaseModel):
    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}

class BaseTool(ABC):
    name: str
    description: str
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        pass
```

### Elasticsearch Schema Documentation
```yaml
# elasticsearch_schema.yaml
index: research-publications-static
elasticsearch_version: 6.8.23
mapping:
  Title: text
  Abstract: text
  Year: integer
  PublicationType: keyword
  Source: text
  Persons:
    type: nested
    properties:
      PersonData:
        properties:
          DisplayName: text
  Keywords: text
  IdentifierDoi: keyword
  DetailsUrlEng: keyword
```

### Example Query Patterns
```markdown
# example_queries.md
## Example queries the system should handle:
1. "Find publications by John Smith"
2. "What are the top research topics in 2023?"
3. "Show me machine learning papers with fuzzy author matching"
4. "How many journal articles has <name> written, and what are the top 3 main topics of their research?"
5. "Summarize three distinct articles they have published for a non-technical reader"

## Expected tool usage patterns:
- Simple query → single tool call
- Complex query → multiple coordinated tool calls
- Follow-up → use cached results when possible
```

### Research Database Tools
**Test Cases for each tool type**:
```python
# test_research_db_tools.py
- test_search_publications_by_author()
- test_search_handles_fuzzy_matching()
- test_get_publication_details()
- test_search_persons_returns_structured_data()
- test_get_organization_funding()
- test_tool_handles_connection_errors()
- test_tool_validates_input_parameters()
```

**Tool Interface Standard**:
```python
class ElasticsearchTool(BaseTool):
    name: str  # Format: "elasticsearch_{entity}_{action}"
    description: str  # For LLM to understand when to use
    args_schema: Type[BaseModel]  # Pydantic model for validation
    
    async def _arun(self, **kwargs) -> ToolResult:
        # Implementation
        pass
```

**Tool Result Structure**:
```python
@dataclass
class ToolResult:
    success: bool
    data: Any  # Actual result data
    error: Optional[str]
    metadata: Dict  # execution time, result count, etc.
    raw_response: Optional[Dict]  # For debugging
```

## Test File Template Example
```python
# tests/unit/test_tool_registry.py
"""Tests for the Tool Registry component."""

import pytest
from unittest.mock import Mock, AsyncMock
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
        tool.execute = AsyncMock(return_value=ToolResult(
            success=True,
            data={"test": "data"},
            metadata={"execution_time": 0.1}
        ))
        return tool
    
    def test_registry_starts_empty(self, registry):
        """Test that registry initializes with no tools."""
        assert len(registry.list_tools()) == 0
    
    def test_register_tool_adds_to_registry(self, registry, mock_tool):
        """Test that registering a tool adds it to the registry."""
        registry.register_tool(mock_tool, category="test", metadata={})
        assert len(registry.list_tools()) == 1
        assert registry.get_tool("test_tool") == mock_tool
    
    # ... more tests following the test cases specified
```

## Phase-Based Implementation Instructions

### Phase 1 Instructions: Core Infrastructure (Week 1)

1. **Study the provided tool interface specification and ES schema**
2. **Design and implement the ToolRegistry with full tests**
3. **Create mock tools that implement BaseTool interface**
4. **These mocks should simulate the Elasticsearch tools but use in-memory data**

Requirements:
- Set up project structure with pytest
- Implement ToolRegistry with tests
- Implement basic Orchestrator with tests
- Create mock tools for testing

### Phase 2 Instructions: Planning and Execution (Week 2)

Only after completing Phase 1 with 100% test coverage:
1. **Review the provided reference implementation** (will be provided after Phase 1)
2. **Extract the useful patterns but improve the architecture**
3. **Implement proper async support**
4. **Add proper error handling and retries**
5. **Ensure tools return structured ToolResult objects**

Requirements:
- Implement PlanningAgent with tests
- Implement Executor with tests
- Add retry and error handling logic
- Integration tests for plan-execute flow

### Phase 3: Context and Memory (Week 3)
1. Implement ContextManager with tests
2. Add conversation memory
3. Implement similarity search
4. Add session management

### Phase 4: Real Tools and LLM Integration (Week 4)
1. Implement Elasticsearch tools with tests
2. Replace mock tools with production-ready async Elasticsearch tools
3. Implement LLM Factory with LiteLLM integration
4. Integrate real tools and LLM with existing orchestrator and planner
5. End-to-end testing with real tools and LLM

### Phase 5: API and Production Infrastructure (Week 5)
1. Create FastAPI application and REST endpoints
2. Implement session management with Redis
3. Add WebSocket support for real-time updates
4. Add web search tool
5. Production deployment infrastructure
6. Health checks and monitoring
7. Load testing and scalability validation

## Phase 5: Development & Deployment Strategy

### Target Environment
- **Scale**: <100 users, typically <10 concurrent
- **Deployment**: University subdomain integration
- **Use Case**: Academic demo/workspace for colleagues
- **Development**: Local demo → test → integrate → deploy workflow

### Local Demo Mode
- Standalone FastAPI server for local testing
- `python run_demo.py` command for quick development
- Built-in simple HTML interface for testing
- No external dependencies (Redis optional for basic mode)
- Immediate feedback for development and debugging

### Integration Mode  
- CORS-enabled API for web app integration
- Static file serving capability
- Compatible with existing university web app collection
- Environment-based configuration (local vs. production)
- Easy injection into existing web application architecture

### University Server Deployment
- Integration with existing web app collection
- Simple deployment scripts for university infrastructure
- Configured for academic use case (<100 users)
- Subdomain hosting compatible with current setup

## Key Improvements to Make (Phase 4 - Elasticsearch Tools):

1. **All tools should be async**
2. **Proper connection pooling for Elasticsearch**
3. **Structured error types** (NetworkError, ValidationError, etc.)
4. **Batch operations where possible**
5. **Caching layer within tools for repeated queries**
6. **No global state** - proper dependency injection
7. **Comprehensive input validation**
8. **Parallel execution support**

## Session Management (Phase 5)
**Purpose**: Handle browser refreshes and maintain state

**Test Cases**:
```python
# test_session_manager.py
- test_session_creates_new_session()
- test_session_restores_existing_session()
- test_session_expires_after_timeout()
- test_session_handles_concurrent_requests()
- test_session_cleans_up_resources()
```

**Implementation**:
- Use Redis for session storage
- Session timeout: 2 hours
- Include WebSocket support for real-time updates

## Real-time User Experience Requirements

### Critical UX Challenge
Multi-tool execution can take 5-15 seconds. Users need continuous feedback to understand the system is working and what it's doing.

### WebSocket Progress Updates
**Required Progress Messages**:
1. **"Planning your query..."** - Initial query analysis
2. **"Searching 356K publications..."** - Database search in progress  
3. **"Found 45 papers, analyzing authors..."** - Processing results
4. **"Generating summary..."** - Final response generation
5. **"Complete!"** - Ready to display results

### Progress Update Format
```python
# WebSocket message structure
{
  "type": "progress",
  "message": "Searching publications...",
  "step": 1,
  "total_steps": 3,
  "estimated_time": "2-5 seconds",
  "details": {
    "current_tool": "search_publications",
    "parameters": {"query": "machine learning", "limit": 10}
  }
}

# Final result message
{
  "type": "result",
  "data": {
    "response": "Found 45 publications...",
    "sources": [...],
    "execution_plan": {...}
  }
}

# Error message
{
  "type": "error", 
  "message": "Elasticsearch connection failed",
  "recoverable": true,
  "retry_in": 5
}
```

### User Feedback Requirements
- **Progress indication**: Show current step (1/3, 2/3, etc.)
- **Time estimates**: Rough completion time when possible
- **Tool transparency**: Let users see which tools are being used
- **Error recovery**: Clear messages when things go wrong
- **Cancellation**: Allow users to cancel long-running queries

## API Specifications (Phase 5)

**Main Endpoint**:
```python
POST /api/chat
{
    "query": str,
    "session_id": str,
    "stream": bool  # Enable streaming responses
}

Response:
{
    "response": str,
    "sources": List[Source],
    "execution_plan": Optional[ExecutionPlan],
    "confidence": float,
    "session_id": str
}
```

## Integration Architecture

### Development Workflow
```bash
# 1. Local Development & Testing
python run_demo.py --port 8000 --demo-mode
# Access at: http://localhost:8000 (built-in test interface)

# 2. Integration Testing  
python run_server.py --port 8000 --cors-origins "*"
# Test with existing web app frontend

# 3. University Deployment
python run_server.py --port 8000 --cors-origins "https://your-domain.se"
# Deploy to university subdomain
```

### Web App Integration Strategy
```javascript
// Frontend integration example
const ws = new WebSocket('ws://localhost:8000/ws');

// Send query
ws.send(JSON.stringify({
  type: 'query',
  data: {
    query: 'Find papers by John Smith',
    session_id: 'user123'
  }
}));

// Receive progress updates
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  if (message.type === 'progress') {
    showProgress(message.message, message.step, message.total_steps);
  } else if (message.type === 'result') {
    showResult(message.data);
  } else if (message.type === 'error') {
    showError(message.message, message.recoverable);
  }
};
```

### CORS Configuration
```python
# Development: Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Production: Restrict to university domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.se"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

### Debug and Development Features
```python
# Debug endpoint for conversation download
GET /api/debug/conversation/{session_id}
Response: {
    "conversation": [...],
    "execution_plans": [...],
    "tool_calls": [...],
    "performance_metrics": {...}
}

# Health check endpoints
GET /health          # Simple health check
GET /health/detailed # Include ES connection, LLM availability
GET /metrics         # Prometheus-style metrics
```

## Error Handling Requirements

**Test Cases**:
```python
# test_error_handling.py
- test_system_handles_llm_api_errors()
- test_system_handles_tool_failures_gracefully()
- test_system_provides_user_friendly_error_messages()
- test_system_logs_errors_appropriately()
```

## Performance Requirements
- Query processing: <3 seconds for simple queries
- Tool execution timeout: 30 seconds per tool
- Support 100 concurrent sessions
- Memory usage: <100MB per session

## Testing Infrastructure

**Required Test Fixtures**:
```python
# conftest.py
@pytest.fixture
def mock_llm():
    # Returns consistent responses for testing

@pytest.fixture
def mock_elasticsearch():
    # In-memory Elasticsearch mock

@pytest.fixture
def sample_execution_plans():
    # Various plan types for testing
```

**Integration Tests**:
```python
# test_integration.py
- test_end_to_end_simple_query()
- test_end_to_end_complex_multi_tool_query()
- test_conversation_with_follow_ups()
- test_system_under_load()
```

## pytest.ini Configuration
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
addopts = 
    -ra
    --strict-markers
    --cov=src
    --cov-report=html
    --cov-report=term-missing:skip-covered
```

## Code Quality Requirements
- Type hints on all functions
- Docstrings following Google style
- Black formatting
- Pylint score > 9.0
- Test coverage > 90%

## Dependencies (requirements.txt format)
```
# Core
langchain==0.1.0
langchain-litellm==0.1.0
langgraph==0.0.20
pydantic==2.0.0

# Tools
elasticsearch>=7.0.0,<8.0.0  # Compatible with ES 6.8.23
redis==5.0.0
sentence-transformers==2.2.0

# API (Phase 5)
fastapi==0.100.0
uvicorn==0.23.0
websockets==11.0.0
python-multipart==0.0.6

# Testing
pytest==7.4.0
pytest-asyncio==0.21.0
pytest-cov==4.1.0

# Code Quality
black==23.0.0
pylint==2.17.0

# Utilities
python-dotenv==1.0.0
tenacity==8.2.0
```

## LLM Configuration

### LiteLLM Integration
The system uses LiteLLM for all LLM interactions, providing a unified interface to multiple model providers.

**Environment Variables Required**:
```bash
LITELLM_API_KEY=your_api_key_here
LITELLM_BASE_URL=your_base_url_here
```

**LLM Initialization Pattern**:
```python
from langchain_litellm import ChatLiteLLM
import os

class LLMFactory:
    """Factory for creating configured LLM instances"""
    
    @staticmethod
    def create_orchestrator_llm() -> ChatLiteLLM:
        """Create LLM for the main orchestrator agent"""
        return ChatLiteLLM(
            model="anthropic/claude-3-sonnet-20240229",  # Fast model for orchestration
            api_key=os.getenv("LITELLM_API_KEY"),
            api_base=os.getenv("LITELLM_BASE_URL"),
            temperature=0.3  # Lower temperature for consistent routing
        )
    
    @staticmethod
    def create_planner_llm() -> ChatLiteLLM:
        """Create LLM for the planning agent"""
        return ChatLiteLLM(
            model="anthropic/claude-3-opus-20240229",  # More capable model for complex planning
            api_key=os.getenv("LITELLM_API_KEY"),
            api_base=os.getenv("LITELLM_BASE_URL"),
            temperature=0.1  # Very low temperature for structured planning
        )
    
    @staticmethod
    def create_tool_llm() -> ChatLiteLLM:
        """Create LLM for tool-specific tasks"""
        return ChatLiteLLM(
            model="anthropic/claude-3-haiku-20240307",  # Fastest model for simple tool calls
            api_key=os.getenv("LITELLM_API_KEY"),
            api_base=os.getenv("LITELLM_BASE_URL"),
            temperature=0.0  # Deterministic for tool operations
        )
```

**Model Selection Guidelines**:
- **Orchestrator**: Use fast, capable models (e.g., Claude Sonnet) for routing decisions
- **Planner**: Use most capable models (e.g., Claude Opus) for complex planning
- **Tools**: Use fastest models (e.g., Claude Haiku) for structured tool operations
- **Summaries**: Use fast models with good comprehension for context summarization

**Available Models Helper**:
```python
import requests
from typing import List, Optional

class LiteLLMHelper:
    """Helper utilities for LiteLLM operations"""
    
    @staticmethod
    def get_available_models() -> Optional[List[str]]:
        """Get list of available models from LiteLLM proxy"""
        api_key = os.getenv("LITELLM_API_KEY")
        base_url = os.getenv("LITELLM_BASE_URL")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(
                f"{base_url}/models",
                headers=headers
            )
            
            if response.status_code == 200:
                models = response.json()
                return [model["id"] for model in models["data"]]
            return None
        except Exception:
            return None
    
    @staticmethod
    def validate_model_availability(model_name: str) -> bool:
        """Check if a specific model is available"""
        available_models = LiteLLMHelper.get_available_models()
        return available_models is not None and model_name in available_models
```

**Test Configuration**:
```python
# test_fixtures/llm_fixtures.py
import pytest
from unittest.mock import Mock, AsyncMock
from langchain_litellm import ChatLiteLLM

@pytest.fixture
def mock_litellm():
    """Mock LiteLLM for testing without API calls"""
    mock = Mock(spec=ChatLiteLLM)
    mock.apredict = AsyncMock(return_value="Mocked LLM response")
    mock.predict = Mock(return_value="Mocked LLM response")
    return mock

@pytest.fixture
def mock_llm_factory(mock_litellm):
    """Mock LLMFactory that returns mock LLMs"""
    class MockLLMFactory:
        @staticmethod
        def create_orchestrator_llm():
            return mock_litellm
        
        @staticmethod
        def create_planner_llm():
            return mock_litellm
        
        @staticmethod
        def create_tool_llm():
            return mock_litellm
    
    return MockLLMFactory
```

**Streaming Support**:
```python
async def stream_llm_response(
    llm: ChatLiteLLM,
    messages: List[Dict[str, str]],
    callback_handler: Optional[AsyncCallbackHandler] = None
) -> AsyncGenerator[str, None]:
    """Stream responses from LLM for real-time updates"""
    async for chunk in llm.astream(
        messages,
        callbacks=[callback_handler] if callback_handler else []
    ):
        yield chunk.content
```

**Error Handling for LLM Calls**:
```python
from tenacity import retry, stop_after_attempt, wait_exponential

class LLMError(Exception):
    """Base exception for LLM-related errors"""
    pass

class LLMRateLimitError(LLMError):
    """Raised when rate limit is hit"""
    pass

class LLMTimeoutError(LLMError):
    """Raised when LLM call times out"""
    pass

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True
)
async def safe_llm_call(llm: ChatLiteLLM, messages: List[Dict]) -> str:
    """Wrapper for LLM calls with retry logic"""
    try:
        response = await llm.apredict_messages(messages)
        return response.content
    except Exception as e:
        if "rate_limit" in str(e).lower():
            raise LLMRateLimitError(f"Rate limit hit: {e}")
        elif "timeout" in str(e).lower():
            raise LLMTimeoutError(f"LLM call timed out: {e}")
        else:
            raise LLMError(f"LLM call failed: {e}")
```

## Success Criteria

### Phase 1-4 (Completed)
1. All tests pass (>90% coverage) ✅
2. System handles example query successfully ✅
3. Follows conversation context appropriately ✅
4. Gracefully handles errors ✅
5. Performs within specified limits ✅

### Phase 5: API and Production Infrastructure ✅
1. **Local Demo Server**: `python run_demo.py` works with built-in interface ✅
2. **Real-time Progress**: WebSocket updates during multi-tool execution ✅
3. **University Integration**: Easy integration with existing web app collection ✅
4. **Performance**: <10s response time for typical queries, 95%+ uptime ✅
5. **User Experience**: Progress feedback, error recovery, cancellation support ⚠️
6. **Debug Capabilities**: Conversation download, execution plan inspection ✅
7. **Deployment**: Simple deployment to university subdomain ✅

### Phase 6: Production Quality & User Experience (NEW)
1. **Response Quality Enhancement**:
   - Rich publication summaries with abstracts and key findings
   - Proper source attribution with DOIs and publication details
   - Contextual responses that explain what was found and why it's relevant
   - Follow-up question suggestions based on results

2. **User Experience Improvements**:
   - Progress indicators showing "Searching 356K publications..."
   - Tool transparency: "Using Elasticsearch to search academic database..."
   - Error messages with suggested alternatives
   - Result export functionality (PDF, CSV, BibTeX)
   - Session history and conversation download

3. **Production Infrastructure**:
   - Redis session persistence across browser refreshes
   - Comprehensive error handling with user-friendly messages
   - Health monitoring and alerting
   - Load balancing and horizontal scaling
   - Automated deployment pipelines
   - Backup and disaster recovery procedures

4. **Enterprise Features**:
   - User authentication and authorization
   - Usage analytics and rate limiting
   - Configuration management via environment variables
   - Logging and audit trails
   - Security scanning and vulnerability management

### Technical Success Metrics
- **API Response Time**: REST endpoints <2s, WebSocket updates <500ms
- **Reliability**: 95%+ uptime for colleague usage
- **Scalability**: Handle <10 concurrent users smoothly
- **Error Handling**: Graceful degradation with user-friendly messages
- **Integration**: CORS working, static files served correctly

### User Experience Success Metrics
- **Feedback**: Users see progress during 5-15 second executions
- **Transparency**: Users understand what tools are being used
- **Debugging**: Developers can inspect conversation history
- **Deployment**: Single command deployment to university server
- **Adoption**: Colleagues actually use the system regularly

### Phase 6 Success Criteria
1. **Response Quality**:
   - Users receive rich, contextual responses instead of generic "Found 10 publications"
   - All sources properly attributed with DOI, title, authors, and publication year
   - Responses include relevant abstracts and key findings
   - Follow-up questions suggested based on search results

2. **User Experience**:
   - Progress indicators show specific actions: "Searching 356K publications...", "Analyzing results..."
   - Tool transparency: Users know when ES is being used vs. conversational responses
   - Error messages include suggested alternatives and recovery options
   - Results can be exported in standard academic formats (BibTeX, CSV, PDF)

3. **Production Readiness**:
   - 99.9% uptime with proper error handling and recovery
   - Sessions persist across browser refreshes
   - Handles 100+ concurrent users without degradation
   - Comprehensive logging and monitoring in place
   - Automated deployment and rollback procedures

4. **Enterprise Quality**:
   - User authentication and role-based access control
   - Usage analytics and reporting dashboard
   - Rate limiting and abuse prevention
   - Security audit compliance
   - Configuration management without code changes

## Reference Implementation Notes

A reference implementation of Elasticsearch tools will be provided after Phase 1 completion. This implementation should be studied for query patterns but requires significant improvements:

**Current Implementation Limitations**:
1. No async support - Everything is synchronous
2. No structured errors - Just JSON strings with error messages
3. No retry logic - Network calls can fail
4. No connection pooling - Creating new connections each time
5. No input validation beyond Pydantic - Need domain validation
6. No caching - Repeated identical queries hit ES every time
7. No batch operations - Can't efficiently fetch multiple documents
8. Tight coupling - Tools directly depend on global ES client

The autonomous agent should fix these issues while maintaining the same functionality.

## Phase 1 - Day 1 Starting Checklist
1. [ ] Activate virtual environment: `source venv/bin/activate`
2. [ ] Install initial dependencies: `pip install pytest pytest-asyncio pytest-cov black pylint`
3. [ ] Update requirements.txt: `pip freeze > requirements.txt`
4. [ ] Create project structure as specified above
5. [ ] Create .gitignore file
6. [ ] Create .env.example with placeholders
7. [ ] Create pytest.ini with basic configuration
8. [ ] Write first test file: `tests/unit/test_tool_registry.py`
9. [ ] Run tests and see them fail: `pytest tests/unit/test_tool_registry.py -v`
10. [ ] Commit: `git add . && git commit -m "test: add initial tool registry tests"`

## Phase 1 Completion Criteria
Before moving to Phase 2, ensure:
1. [ ] Tool Registry fully implemented with 100% test coverage
2. [ ] Mock tools created for: search_publications, search_by_author, get_field_statistics
3. [ ] Basic Orchestrator that can identify when tools are needed
4. [ ] All tests passing
5. [ ] Code formatted with Black
6. [ ] Pylint score > 9.0
7. [ ] Git history shows TDD approach (test commits before implementation)
8. [ ] README updated with setup and usage instructions

---

**Note for the coding agent**: Start with Phase 1 and ensure each component is fully tested before moving to the next phase. Use mocks extensively to test components in isolation before integration. The TDD approach means you should write the test files first, see them fail, then implement the functionality to make them pass.