from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Category = Literal[
    "personal",
    "career",
    "projects",
    "preferences",
    "goals",
    "decisions",
    "commitments",
    "work",
    "health",
    "finance",
    "family",
]
MemoryStatus = Literal["active", "outdated", "superseded"]


class MemorySave(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)
    category: Category = "personal"
    owner_id: str = Field(default="user", min_length=1, max_length=100)
    source_agent: str | None = Field(default=None, max_length=100)
    memory_key: str | None = Field(default=None, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: MemoryStatus = "active"
    is_demo: bool = False

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("content cannot be blank")
        return value

    @field_validator("memory_key")
    @classmethod
    def normalize_key(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None


class MemoryUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=20_000)
    category: Category | None = None
    status: MemoryStatus | None = None
    metadata: dict[str, Any] | None = None
    memory_key: str | None = Field(default=None, max_length=200)

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError("content cannot be blank")
        return value

    @field_validator("memory_key")
    @classmethod
    def normalize_key(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None


class MemoryRetrieve(BaseModel):
    query: str = Field(min_length=1, max_length=4_000)
    owner_id: str = Field(default="user", min_length=1, max_length=100)
    limit: int = Field(default=8, ge=1, le=50)
    categories: list[Category] | None = None
    include_demo: bool = False

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query cannot be blank")
        return value


class AgentSessionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    role: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2_000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value


class AgentChat(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=20_000)
    owner_id: str = Field(default="user", min_length=1, max_length=100)


class ResolveConflict(BaseModel):
    action: Literal["make_current"]
