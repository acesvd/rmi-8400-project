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


class CaseExtractionManualUpdate(BaseModel):
    payer: str | None = None
    plan_type: str | None = None
    patient_name: str | None = None
    claimant_name: str | None = None
    claim_number: str | None = None
    auth_number: str | None = None
    member_id: str | None = None
    denial_reasons: list[str] = Field(default_factory=list)
    deadlines: list[str] = Field(default_factory=list)
    submission_channels: list[str] = Field(default_factory=list)
    requested_documents: list[str] = Field(default_factory=list)


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


# --- A1: Denial Outcomes ---


class AppealabilityScore(BaseModel):
    overturn_rate: float | None = None
    sample_size: int = 0
    overturned_count: int = 0
    upheld_count: int = 0
    confidence: Literal["high", "medium", "low", "very_low", "none"] = "none"
    year_range: str = ""
    source: str = ""
    note: str = ""


class InsurerBenchmark(BaseModel):
    insurer: str = ""
    year: int | None = None
    internal_appeals_filed: int | None = None
    internal_appeals_overturned: int | None = None
    internal_overturn_pct: float | None = None
    external_appeals_filed: int | None = None
    external_appeals_overturned: int | None = None
    external_overturn_pct: float | None = None
    source: str = ""
    error: str | None = None


class AppealabilityResponse(BaseModel):
    case_id: str
    denial_classification: Literal["R1", "R2", "technical", "unknown"]
    denial_label: str = ""
    payer: str = ""
    a_score: AppealabilityScore = Field(default_factory=AppealabilityScore)
    insurer_benchmark: InsurerBenchmark = Field(default_factory=InsurerBenchmark)
    recommendations: list[str] = Field(default_factory=list)
