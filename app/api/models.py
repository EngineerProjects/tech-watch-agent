from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, EmailStr, field_validator, model_validator

class HealthResponse(BaseModel):
    status: str
    database: str
    memory: str
    agents: dict[str, bool]

class UserCreate(BaseModel):
    email: EmailStr
    username: Optional[str] = None
    preferences: dict[str, Any] = Field(default_factory=dict)

class UserResponse(BaseModel):
    id: str
    email: str
    username: Optional[str]
    preferences: dict[str, Any]
    is_active: bool
    created_at: datetime

class UserTopicCreate(BaseModel):
    topic: str
    frequency: str = "daily"

class ArticleResponse(BaseModel):
    id: str
    title: str
    summary: Optional[str]
    url: str
    source: str
    topic: str
    published_date: Optional[datetime]
    relevance_score: int

class SourceResponse(BaseModel):
    id: str
    session_id: str
    session_brief: str
    step_id: Optional[str]
    step_name: Optional[str]
    article_id: Optional[str]
    title: str
    url: str
    source: str
    topic: Optional[str]
    summary: Optional[str]
    published_date: Optional[str]
    relevance_score: Optional[float]
    tool_name: Optional[str]
    created_at: Optional[str]

class NewsletterGenerateRequest(BaseModel):
    topics: Optional[list[str]] = None
    send_email: bool = True
    user_id: Optional[str] = None

class NewsletterGenerateResponse(BaseModel):
    run_id: str
    subject: str
    article_count: int
    status: str
    preview: str
    email_sent: bool = False
    delivery_message: Optional[str] = None

class DeepResearchRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    research_depth: str = "medium"
    allow_clarification: bool = True

    @field_validator("query")
    @classmethod
    def query_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("query must not be empty")
        return v

    @field_validator("research_depth")
    @classmethod
    def depth_valid(cls, v: str) -> str:
        if v not in ("shallow", "medium", "deep"):
            raise ValueError("research_depth must be 'shallow', 'medium', or 'deep'")
        return v

class DeepResearchResponse(BaseModel):
    session_id: str
    status: str
    final_report: Optional[str]
    research_brief: Optional[str]
    notes_count: int

class ToolListResponse(BaseModel):
    tools: list[dict[str, Any]]
    count: int

class ToolExecuteRequest(BaseModel):
    tool_name: str
    params: dict[str, Any] = Field(default_factory=dict)

class ModelCatalogItemResponse(BaseModel):
    id: str
    label: str
    description: Optional[str] = None
    context_window: Optional[int] = None
    max_output_tokens: Optional[int] = None
    dimensions: Optional[int] = None
    capabilities: list[str] = Field(default_factory=list)
    recommended_role: Optional[str] = None
    source: str = "curated"
    available: Optional[bool] = None
    family: Optional[str] = None
    parameter_size: Optional[str] = None
    quantization: Optional[str] = None
    size_bytes: Optional[int] = None

class ProviderResponse(BaseModel):
    name: str
    label: Optional[str] = None
    base_url: str
    default_model: str
    requires_api_key: bool
    supports_dynamic_discovery: bool = False
    discovery_error: Optional[str] = None
    chat_models: list[ModelCatalogItemResponse] = Field(default_factory=list)
    embedding_models: list[ModelCatalogItemResponse] = Field(default_factory=list)

class ProviderListResponse(BaseModel):
    providers: list[ProviderResponse]
    current_provider: str
    current_model: str
    current_embedding_provider: Optional[str] = None
    current_embedding_model: Optional[str] = None

class OrchestratorRequest(BaseModel):
    task: str = "Weekly tech watch"
    subject: Optional[str] = None
    title: Optional[str] = None
    research_instructions: Optional[str] = None
    topics: Optional[list[str]] = None
    send_email: bool = True
    mode: str = "v2"
    autonomous: bool = True

    @field_validator("task")
    @classmethod
    def task_clean(cls, v: str) -> str:
        return v.strip()

    @field_validator("subject")
    @classmethod
    def subject_clean(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned or None

    @field_validator("title")
    @classmethod
    def title_clean(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned or None

    @field_validator("research_instructions")
    @classmethod
    def research_instructions_clean(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned or None

    @model_validator(mode="after")
    def ensure_task_or_subject(self) -> "OrchestratorRequest":
        if not self.subject and not self.task:
            raise ValueError("task or subject must be provided")
        return self

    @field_validator("mode")
    @classmethod
    def mode_valid(cls, v: str) -> str:
        if v not in ("v1", "v2"):
            raise ValueError("mode must be 'v1' or 'v2'")
        return v

    @field_validator("topics")
    @classmethod
    def topics_clean(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return None
        cleaned = [t.strip() for t in v if t.strip()]
        return cleaned or None

class OrchestratorResponse(BaseModel):
    success: bool
    session_id: Optional[str] = None
    report: Optional[str] = None
    subject: Optional[str] = None
    email_sent: bool
    research_results_count: int = 0
    plan_steps: int = 0
    execution_time: Optional[float] = None
    quality_score: Optional[float] = None
    approval_status: Optional[str] = None
    errors: list[str] = Field(default_factory=list)

class ProviderHealthResponse(BaseModel):
    provider: str
    healthy: bool
    latency_ms: Optional[float]

class ProviderSetRequest(BaseModel):
    provider: str
    model: Optional[str] = None

class OllamaPullRequest(BaseModel):
    model: str

    @field_validator("model")
    @classmethod
    def model_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("model must not be empty")
        return v


class OllamaPullResponse(BaseModel):
    status: str
    provider: str
    model: str
    message: str

class ToolExecuteResponse(BaseModel):
    success: bool
    data: Optional[Any]
    error: Optional[str]
    metadata: dict[str, Any]

class StatsResponse(BaseModel):
    total_articles: int
    total_users: int
    total_newsletter_runs: int
    successful_deliveries: int
    active_sessions: int

class ArticleQuery(BaseModel):
    topics: Optional[list[str]] = None
    sources: Optional[list[str]] = None
    min_relevance: int = 0
    limit: int = 50
