from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ===== 知识库 =====
class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=1000)


class KnowledgeBaseRead(KnowledgeBaseCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime


# ===== 文档 =====
class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    knowledge_base_id: str
    filename: str
    mime_type: str
    size: int
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class DocumentCreated(BaseModel):
    document_id: str
    status: str


# ===== 聊天 =====
class ChatRequest(BaseModel):
    conversation_id: str | None = None
    knowledge_base_id: str
    message: str = Field(min_length=1, max_length=8000)


# ===== 身份与结果 =====
class Principal(BaseModel):
    user_id: str
    email: str = ""


class Citation(BaseModel):
    document_id: str
    chunk_id: str
    filename: str
    page: int | None = None


class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    content: str
    score: float
    page: int | None = None
    metadata: dict = Field(default_factory=dict)
