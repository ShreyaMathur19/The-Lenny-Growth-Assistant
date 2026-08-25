from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SessionCreate(BaseModel):
    user_id: str = "demo-user"
    user_metadata: dict = Field(default_factory=dict)


class SessionOut(OrmModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class SourceOut(OrmModel):
    id: str
    episode_title: str | None = None
    guest: str | None = None
    source_url: str | None = None
    source_path: str
    excerpt: str
    score: float | None = None


class ArtifactOut(OrmModel):
    id: str
    type: Literal["markdown", "html"]
    title: str
    content: str


class MessageOut(OrmModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    provider: str | None = None
    model: str | None = None
    sources: list[SourceOut] = Field(default_factory=list)
    created_at: datetime


class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1, max_length=12000)
    provider: Literal["ollama", "cloud"] = "ollama"
    mode: Literal["auto", "qa", "ship30", "artifact"] = "auto"
    artifact_type: Literal["markdown", "html"] = "markdown"


class ChatResponse(BaseModel):
    message: MessageOut
    mode: Literal["qa", "ship30", "artifact"]
    artifact: ArtifactOut | None = None


class ProviderConfig(BaseModel):
    local_provider: str
    local_model: str
    cloud_provider: str
    cloud_model: str
    cloud_enabled: bool
