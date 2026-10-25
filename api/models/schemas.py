"""
ESGPilot — Pydantic request/response schemas for API endpoints.
"""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────

class SessionCreate(BaseModel):
    """Host backend requests a session JWT."""
    tenant_key: str
    user_id: str
    user_role: str
    entity_id: Optional[str] = None
    project_id: Optional[str] = None


class SessionResponse(BaseModel):
    token: str
    expires_at: datetime


class TokenPayload(BaseModel):
    tenant_id: str
    user_id: str
    role: str
    entity_id: Optional[str] = None
    project_id: Optional[str] = None
    exp: datetime


# ──────────────────────────────────────────────
# Form Context
# ──────────────────────────────────────────────

class FieldData(BaseModel):
    """A single field's current state."""
    field_code: str
    value: Optional[str | float] = None
    unit: Optional[str] = None
    label: Optional[str] = None


class FormContext(BaseModel):
    """Pushed by the host app via SDK / API."""
    form_id: str
    framework: str = "BRSR"
    section: Optional[str] = None
    fy: str = "FY2025"
    entity_id: Optional[str] = None
    project_id: Optional[str] = None
    fields: list[FieldData] = []


class FormAnalyzeRequest(BaseModel):
    form_id: str
    framework: str = "BRSR"
    section: Optional[str] = None
    report_id: Optional[str] = None


# ──────────────────────────────────────────────
# Suggestions
# ──────────────────────────────────────────────

class ReferenceItem(BaseModel):
    doc: str
    section: Optional[str] = None
    version: Optional[str] = None
    url: Optional[str] = None


class SuggestionCard(BaseModel):
    """Output contract per BUILD_SPEC §4.4."""
    id: str
    scope: str = "field"  # field | section | form | portfolio
    severity: str = "info"  # info | warn | critical
    title: str
    why: Optional[str] = None
    how_to_fix: Optional[str] = None
    references: list[ReferenceItem] = []
    sdg_tags: list[str] = []
    confidence: float = 0.0
    source: str = "rule"  # rule | slm | hybrid


class SuggestionsResponse(BaseModel):
    report_id: str
    form_id: Optional[str] = None
    suggestions: list[SuggestionCard] = []
    readiness_score: Optional[float] = None
    readiness_breakdown: Optional[dict] = None


class NudgeResponse(BaseModel):
    """Lightweight nudge (rules-only, fast)."""
    has_findings: bool
    count: int = 0
    top_severity: str = "info"
    summary: Optional[str] = None


# ──────────────────────────────────────────────
# Knowledge Q&A
# ──────────────────────────────────────────────

class KBQuestion(BaseModel):
    question: str
    framework: Optional[str] = None
    fy: Optional[str] = None
    entity_class: Optional[str] = None  # "top_1000", "listed", etc.
    conversation_id: Optional[str] = None


class CitationChip(BaseModel):
    doc_title: str
    section: Optional[str] = None
    version: Optional[str] = None
    url: Optional[str] = None
    excerpt: Optional[str] = None


class KBAnswer(BaseModel):
    answer: str
    citations: list[CitationChip] = []
    confidence: float = 0.0
    last_verified: Optional[str] = None
    abstained: bool = False


# ──────────────────────────────────────────────
# Portfolio / Comparison
# ──────────────────────────────────────────────

class CompareRequest(BaseModel):
    metric: str
    dimensions: list[str] = ["entity"]
    filters: Optional[dict] = None
    group_by: Optional[str] = None
    fy: str = "FY2025"
    top_n: Optional[int] = None
    peer_group: Optional[str] = None


class CompareResult(BaseModel):
    data: list[dict]
    chart_spec: Optional[dict] = None  # Vega-Lite JSON
    narrative: Optional[str] = None
    data_quality: Optional[dict] = None


class NLQueryRequest(BaseModel):
    """Natural-language query for portfolio analytics."""
    query: str
    fy: Optional[str] = "FY2025"


class NLQueryResponse(BaseModel):
    query_plan: dict
    sql: Optional[str] = None  # For debug; not exposed to end users in production
    data: list[dict] = []
    chart_spec: Optional[dict] = None
    narrative: Optional[str] = None


# ──────────────────────────────────────────────
# SDG Mapping
# ──────────────────────────────────────────────

class SDGMapRequest(BaseModel):
    text: str
    context: Optional[str] = None


class SDGTag(BaseModel):
    goal: int
    target: Optional[str] = None
    confidence: float
    rationale: Optional[str] = None


class SDGMapResponse(BaseModel):
    tags: list[SDGTag] = []


# ──────────────────────────────────────────────
# Feedback
# ──────────────────────────────────────────────

class FeedbackCreate(BaseModel):
    suggestion_id: Optional[str] = None
    message_id: Optional[str] = None
    rating: int = Field(..., ge=1, le=5)
    reason: Optional[str] = None


# ──────────────────────────────────────────────
# Chat
# ──────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    citations: list[CitationChip] = []
    timestamp: Optional[datetime] = None


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    form_context: Optional[FormContext] = None
