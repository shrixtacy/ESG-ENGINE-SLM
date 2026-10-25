"""
ESGPilot — SQLAlchemy ORM models.
Maps to the data schema defined in ARCHITECTURE.md §4.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String,
    Integer,
    Float,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    Index,
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from api.core.database import Base


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

import enum


class ReportStatus(str, enum.Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    SUBMITTED = "submitted"
    APPROVED = "approved"


class SuggestionSeverity(str, enum.Enum):
    INFO = "info"
    WARN = "warn"
    CRITICAL = "critical"


class SuggestionStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    IGNORED = "ignored"
    APPLIED = "applied"


class SuggestionScope(str, enum.Enum):
    FIELD = "field"
    SECTION = "section"
    FORM = "form"
    PORTFOLIO = "portfolio"


class SuggestionSource(str, enum.Enum):
    RULE = "rule"
    SLM = "slm"
    HYBRID = "hybrid"


class UserRole(str, enum.Enum):
    PROJECT_USER = "project_user"
    ENTITY_ADMIN = "entity_admin"
    GROUP_ADMIN = "group_admin"
    AUDITOR = "auditor"
    TENANT_ADMIN = "tenant_admin"


class FieldType(str, enum.Enum):
    NUMBER = "number"
    TEXT = "text"
    TEXTAREA = "textarea"
    SELECT = "select"
    BOOLEAN = "boolean"
    DATE = "date"
    FILE = "file"


# ──────────────────────────────────────────────
# Tenant / Hierarchy
# ──────────────────────────────────────────────


class Tenant(Base):
    """Top-level group / organisation."""
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[str] = mapped_column(String(50), default="free")
    region: Mapped[str] = mapped_column(String(10), default="IN")
    settings: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    api_key_hash: Mapped[Optional[str]] = mapped_column(String(255))
    allowed_origins: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    entities: Mapped[list["Entity"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    users: Mapped[list["User"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")


class Entity(Base):
    """Subsidiary / partner within a tenant group."""
    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cin: Mapped[Optional[str]] = mapped_column(String(21))  # Company Identification Number
    sector: Mapped[Optional[str]] = mapped_column(String(100))
    size_band: Mapped[Optional[str]] = mapped_column(String(50))  # e.g. "top_1000", "listed", "unlisted"
    state: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="entities")
    projects: Mapped[list["Project"]] = relationship(back_populates="entity", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_entities_tenant", "tenant_id"),
    )


class Project(Base):
    """A specific project under an entity."""
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[Optional[str]] = mapped_column(String(100))
    location: Mapped[Optional[str]] = mapped_column(String(255))
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    entity: Mapped["Entity"] = relationship(back_populates="projects")
    reports: Mapped[list["Report"]] = relationship(back_populates="project", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_projects_entity", "entity_id"),
    )


class User(Base):
    """User within a tenant, with role-based access."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole), default=UserRole.PROJECT_USER
    )
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id")
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="users")

    __table_args__ = (
        Index("ix_users_tenant", "tenant_id"),
    )


# ──────────────────────────────────────────────
# Reports & Field Values
# ──────────────────────────────────────────────


class Report(Base):
    """A report for a project-FY-framework combination."""
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    fy: Mapped[str] = mapped_column(String(10), nullable=False)  # e.g. "FY2025"
    framework: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "BRSR"
    status: Mapped[ReportStatus] = mapped_column(
        SAEnum(ReportStatus), default=ReportStatus.DRAFT
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="reports")
    field_values: Mapped[list["FieldValue"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )
    suggestions: Mapped[list["Suggestion"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_reports_project_fy", "project_id", "fy"),
    )


class FieldDef(Base):
    """Machine-readable definition of an ESG reporting field."""
    __tablename__ = "field_defs"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # e.g. "brsr_p6_ei7_scope1"
    framework: Mapped[str] = mapped_column(String(50), nullable=False)
    section: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "P6-EI-7"
    label: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(50))
    field_type: Mapped[FieldType] = mapped_column(
        SAEnum(FieldType), default=FieldType.NUMBER
    )
    mandatory_for: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    formula: Mapped[Optional[str]] = mapped_column(Text)
    validations: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    refs: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    version: Mapped[str] = mapped_column(String(20), default="2024")

    __table_args__ = (
        Index("ix_field_defs_framework_section", "framework", "section"),
    )


class FieldValue(Base):
    """Actual value entered for a field in a report."""
    __tablename__ = "field_values"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.id"), nullable=False
    )
    field_code: Mapped[str] = mapped_column(String(100), nullable=False)
    value_num: Mapped[Optional[float]] = mapped_column(Float)
    value_text: Mapped[Optional[str]] = mapped_column(Text)
    unit: Mapped[Optional[str]] = mapped_column(String(50))
    source_type: Mapped[Optional[str]] = mapped_column(String(50))  # meter, bill, estimate
    evidence_url: Mapped[Optional[str]] = mapped_column(Text)
    entered_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    entered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    verified_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))

    # Relationships
    report: Mapped["Report"] = relationship(back_populates="field_values")

    __table_args__ = (
        Index("ix_field_values_report_field", "report_id", "field_code"),
    )


# ──────────────────────────────────────────────
# Suggestions & Feedback
# ──────────────────────────────────────────────


class Suggestion(Base):
    """A recommendation generated by the rules engine or SLM."""
    __tablename__ = "suggestions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.id"), nullable=False
    )
    field_code: Mapped[Optional[str]] = mapped_column(String(100))
    scope: Mapped[SuggestionScope] = mapped_column(
        SAEnum(SuggestionScope), default=SuggestionScope.FIELD
    )
    severity: Mapped[SuggestionSeverity] = mapped_column(
        SAEnum(SuggestionSeverity), default=SuggestionSeverity.INFO
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    why: Mapped[Optional[str]] = mapped_column(Text)
    how_to_fix: Mapped[Optional[str]] = mapped_column(Text)
    references: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    sdg_tags: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    source: Mapped[SuggestionSource] = mapped_column(
        SAEnum(SuggestionSource), default=SuggestionSource.RULE
    )
    status: Mapped[SuggestionStatus] = mapped_column(
        SAEnum(SuggestionStatus), default=SuggestionStatus.PENDING
    )
    payload: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    model_version: Mapped[Optional[str]] = mapped_column(String(50))
    kb_version: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    report: Mapped["Report"] = relationship(back_populates="suggestions")

    __table_args__ = (
        Index("ix_suggestions_report", "report_id"),
    )


class Feedback(Base):
    """User feedback on a suggestion or chat message."""
    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    suggestion_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suggestions.id")
    )
    message_id: Mapped[Optional[str]] = mapped_column(String(100))
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 = thumbs down, 5 = thumbs up
    reason: Mapped[Optional[str]] = mapped_column(Text)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ──────────────────────────────────────────────
# Knowledge Base
# ──────────────────────────────────────────────


class KBDoc(Base):
    """A document in the knowledge base."""
    __tablename__ = "kb_docs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    issuer: Mapped[Optional[str]] = mapped_column(String(255))
    doc_type: Mapped[str] = mapped_column(String(50))  # law, circular, standard, guidance, example
    version: Mapped[Optional[str]] = mapped_column(String(50))
    effective_from: Mapped[Optional[datetime]] = mapped_column(DateTime)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime)
    superseded_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    url: Mapped[Optional[str]] = mapped_column(Text)
    sha256: Mapped[Optional[str]] = mapped_column(String(64))
    scope: Mapped[str] = mapped_column(String(20), default="global")  # global or tenant_{id}
    lang: Mapped[str] = mapped_column(String(5), default="en")
    licence: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    chunks: Mapped[list["KBChunk"]] = relationship(back_populates="doc", cascade="all, delete-orphan")


class KBChunk(Base):
    """A chunk of a KB document, mirrored in Qdrant."""
    __tablename__ = "kb_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kb_docs.id"), nullable=False
    )
    section_path: Mapped[Optional[str]] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page: Mapped[Optional[int]] = mapped_column(Integer)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # Relationships
    doc: Mapped["KBDoc"] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("ix_kb_chunks_doc", "doc_id"),
    )


# ──────────────────────────────────────────────
# Emission Factors
# ──────────────────────────────────────────────


class EmissionFactor(Base):
    """Versioned emission factor for GHG calculations."""
    __tablename__ = "emission_factors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    region: Mapped[str] = mapped_column(String(50), default="IN")
    fuel_or_grid: Mapped[str] = mapped_column(String(100), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    factor: Mapped[float] = mapped_column(Float, nullable=False)
    gwp_basis: Mapped[Optional[str]] = mapped_column(String(20))  # AR5, AR6

    __table_args__ = (
        Index("ix_emission_factors_source_year", "source", "year"),
    )


# ──────────────────────────────────────────────
# Audit Log
# ──────────────────────────────────────────────


class AuditLog(Base):
    """Immutable audit trail for every action."""
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_audit_log_tenant_ts", "tenant_id", "ts"),
    )
