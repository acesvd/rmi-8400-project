from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class CaseOut(BaseModel):
    case_id: str
    title: str
    status: str
    created_at: str
    updated_at: str


class DocumentOut(BaseModel):
    document_id: str
    case_id: str
    type: str
    filename: str
    storage_path: str
    processed_status: str
    uploaded_at: str


class CaseExtractionOut(BaseModel):
    extraction_id: str
    case_id: str
    case_json: dict[str, Any]
    warnings: list[str]
    created_at: str


class TaskOut(BaseModel):
    task_id: str
    case_id: str
    title: str
    description: str
    owner: str
    due_date: str | None
    status: str
    created_at: str


class TaskUpdate(BaseModel):
    status: Literal["todo", "waiting", "done"]


class ArtifactOut(BaseModel):
    artifact_id: str
    case_id: str
    type: str
    version: int
    storage_path: str
    metadata: dict[str, Any]
    created_at: str


class EventCreate(BaseModel):
    type: Literal["submitted", "followup", "decision", "phone_call"]
    timestamp: str
    notes: str = Field(min_length=1)


class EventOut(BaseModel):
    event_id: str
    case_id: str
    type: str
    timestamp: str
    notes: str


class LetterRequest(BaseModel):
    style: Literal["formal", "concise"] = "formal"


class PacketRequest(BaseModel):
    include_uploaded_pdfs: bool = True


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    mode: str
    warning: str | None = None
