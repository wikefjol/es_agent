"""Data models and schemas for the agent system."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel


class PlanStepStatus(Enum):
    """Status of a plan step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Condition:
    """Condition for conditional step execution."""

    field: str
    operator: str  # eq, ne, in, not_in, contains, etc.
    value: Any


@dataclass
class FallbackStrategy:
    """Fallback strategy for plan step failures."""

    strategy_type: str  # retry, skip, alternate_tool, etc.
    max_retries: int = 3
    retry_delay: int = 2
    alternate_tool: Optional[str] = None


@dataclass
class PlanStep:
    """Individual step in an execution plan."""

    id: str
    tool_name: str
    parameters: Dict[str, Any]
    dependencies: List[str] = None  # IDs of steps that must complete first
    condition: Optional[Condition] = None  # For conditional execution
    status: PlanStepStatus = PlanStepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    description: Optional[str] = None  # Human-readable description of the step

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class OutputSchema:
    """Expected output schema for plan results."""

    type: str  # json, text, list, etc.
    fields: Dict[str, str]  # field_name -> field_type
    required: List[str] = None

    def __post_init__(self):
        if self.required is None:
            self.required = []


@dataclass
class ExecutionPlan:
    """Complete execution plan for a query."""

    steps: List[PlanStep]
    expected_outputs: Dict[str, OutputSchema]
    fallback_strategies: Dict[str, FallbackStrategy]
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ExecutionResult:
    """Result of plan execution."""

    plan_id: str
    success: bool
    results: Dict[str, Any]  # step_id -> result
    errors: Dict[str, str]  # step_id -> error
    execution_time: float
    steps_completed: int
    steps_total: int
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ExecutionContext:
    """Context for plan execution."""

    session_id: str
    user_query: str
    available_tools: List[str]
    timeout_seconds: int = 300
    parallel_execution: bool = True
    max_retries: int = 3
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ExecutorConfig:
    """Configuration for the executor."""

    max_retries: int = 3
    timeout_seconds: int = 30
    parallel_execution: bool = True
    retry_delay_seconds: int = 2


@dataclass
class PlannerConfig:
    """Configuration for the planner."""

    max_steps: int = 20
    parallel_execution: bool = True
    enable_conditional_execution: bool = True
    fallback_strategy_enabled: bool = True
    plan_timeout_seconds: int = 60


@dataclass
class OrchestratorConfig:
    """Configuration for the orchestrator."""

    cache_enabled: bool = True
    cache_ttl_seconds: int = 300
    similarity_threshold: float = 0.8
    max_conversation_length: int = 100
    llm_model: str = "gpt-3.5-turbo"
    max_concurrent_queries: int = 10


class AgentResponse(BaseModel):
    """Response from the orchestrator agent."""

    response: str
    sources: List[Dict[str, Any]] = []
    execution_plan: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    session_id: str
    metadata: Dict[str, Any] = {}


class ConversationContext(BaseModel):
    """Context for conversation management."""

    session_id: str
    messages: List[Dict[str, str]] = []
    cached_results: Dict[str, Any] = {}
    summary: str = ""
    metadata: Dict[str, Any] = {}


@dataclass
class CachedResult:
    """Cached result from previous tool executions."""

    cache_key: str
    tool_name: str
    parameters: Dict[str, Any]
    result: Any
    timestamp: float
    session_id: str
    similarity_score: float = 0.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
