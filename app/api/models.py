from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, EmailStr

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

class DeepResearchRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    research_depth: str = "medium"
    allow_clarification: bool = True

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

class ProviderResponse(BaseModel):
    name: str
    base_url: str
    default_model: str
    requires_api_key: bool

class ProviderListResponse(BaseModel):
    providers: list[ProviderResponse]
    current_provider: str
    current_model: str

class OrchestratorRequest(BaseModel):
    task: str = "Weekly tech watch"
    topics: Optional[list[str]] = None
    send_email: bool = True
    mode: str = "v2"

class OrchestratorResponse(BaseModel):
    success: bool
    report: Optional[str] = None
    subject: Optional[str] = None
    email_sent: bool
    research_results_count: int = 0
    plan_steps: int = 0
    execution_time: Optional[float] = None
    errors: list[str] = Field(default_factory=list)

class ProviderHealthResponse(BaseModel):
    provider: str
    healthy: bool
    latency_ms: Optional[float]

class ProviderSetRequest(BaseModel):
    provider: str
    model: Optional[str] = None

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
