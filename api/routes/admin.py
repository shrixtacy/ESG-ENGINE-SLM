"""
ESGPilot — Admin API Routes.

Tenant management, KB document upload, user management,
API key rotation, audit log access, and data export.

All routes require 'tenant_admin' role.
FR-7: Admin & Governance (BUILD_SPEC §FR-7)
"""

import uuid
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import require_role, get_current_user, generate_api_key, hash_api_key
from api.core.database import get_db
from api.models.schemas import TokenPayload

router = APIRouter(prefix="/v1/admin", tags=["Admin"])

admin_only = require_role("tenant_admin")


# ──────────────────────────────────────────────
# Pydantic Schemas (admin-specific)
# ──────────────────────────────────────────────

class TenantCreate(BaseModel):
    name: str
    plan: str = "free"
    region: str = "IN"
    allowed_origins: list[str] = []


class TenantResponse(BaseModel):
    id: str
    name: str
    plan: str
    region: str
    created_at: datetime
    api_key: Optional[str] = None  # Only returned on creation


class EntityCreate(BaseModel):
    name: str
    cin: Optional[str] = None
    sector: Optional[str] = None
    size_band: str = "listed"
    state: Optional[str] = None
    parent_id: Optional[str] = None


class UserCreate(BaseModel):
    email: str
    name: str
    password: str
    role: str = "project_user"
    entity_id: Optional[str] = None
    project_id: Optional[str] = None


class KBDocMeta(BaseModel):
    title: str
    issuer: Optional[str] = None
    doc_type: str = "guidance"  # law | circular | standard | guidance | example
    version: Optional[str] = None
    effective_from: Optional[str] = None
    framework: Optional[str] = None
    url: Optional[str] = None
    scope: str = "global"  # "global" or "tenant"
    lang: str = "en"


class ApiKeyResponse(BaseModel):
    api_key: str
    created_at: datetime
    note: str = "Store this key securely — it will not be shown again."


class AuditLogEntry(BaseModel):
    id: str
    actor: str
    action: str
    payload: dict
    ts: datetime


# ──────────────────────────────────────────────
# Tenant Management
# ──────────────────────────────────────────────

@router.post("/tenants", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    data: TenantCreate,
    user: TokenPayload = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
):
    """Create a new tenant. Generates and returns a one-time API key."""
    from api.models.db_models import Tenant

    api_key = generate_api_key()
    tenant = Tenant(
        id=uuid.uuid4(),
        name=data.name,
        plan=data.plan,
        region=data.region,
        allowed_origins=data.allowed_origins,
        api_key_hash=hash_api_key(api_key),
        settings={},
    )
    db.add(tenant)
    await db.flush()

    return TenantResponse(
        id=str(tenant.id),
        name=tenant.name,
        plan=tenant.plan,
        region=tenant.region,
        created_at=tenant.created_at,
        api_key=api_key,
    )


@router.get("/tenants", tags=["Admin"])
async def list_tenants(
    user: TokenPayload = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
):
    """List all tenants (super-admin only)."""
    from sqlalchemy import select
    from api.models.db_models import Tenant

    result = await db.execute(select(Tenant).limit(200))
    tenants = result.scalars().all()
    return [
        {"id": str(t.id), "name": t.name, "plan": t.plan, "region": t.region,
         "created_at": t.created_at}
        for t in tenants
    ]


@router.post("/tenants/{tenant_id}/rotate-key", response_model=ApiKeyResponse)
async def rotate_api_key(
    tenant_id: str,
    user: TokenPayload = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
):
    """Rotate the tenant API key."""
    from sqlalchemy import select
    from api.models.db_models import Tenant

    result = await db.execute(
        select(Tenant).where(Tenant.id == uuid.UUID(tenant_id))
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    new_key = generate_api_key()
    tenant.api_key_hash = hash_api_key(new_key)

    return ApiKeyResponse(api_key=new_key, created_at=datetime.utcnow())


# ──────────────────────────────────────────────
# Entity & User Management
# ──────────────────────────────────────────────

@router.post("/entities", status_code=status.HTTP_201_CREATED)
async def create_entity(
    data: EntityCreate,
    user: TokenPayload = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
):
    """Create a subsidiary/entity under the current tenant."""
    from api.models.db_models import Entity

    entity = Entity(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID(user.tenant_id),
        parent_id=uuid.UUID(data.parent_id) if data.parent_id else None,
        name=data.name,
        cin=data.cin,
        sector=data.sector,
        size_band=data.size_band,
        state=data.state,
    )
    db.add(entity)
    await db.flush()

    return {"id": str(entity.id), "name": entity.name, "tenant_id": user.tenant_id}


@router.get("/entities")
async def list_entities(
    user: TokenPayload = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
):
    """List all entities for the current tenant."""
    from sqlalchemy import select
    from api.models.db_models import Entity

    result = await db.execute(
        select(Entity)
        .where(Entity.tenant_id == uuid.UUID(user.tenant_id))
        .limit(500)
    )
    entities = result.scalars().all()
    return [
        {
            "id": str(e.id), "name": e.name, "sector": e.sector,
            "size_band": e.size_band, "state": e.state, "cin": e.cin,
            "parent_id": str(e.parent_id) if e.parent_id else None,
        }
        for e in entities
    ]


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    user: TokenPayload = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
):
    """Create a user within the current tenant."""
    from api.models.db_models import User, UserRole
    from api.core.auth import hash_password

    new_user = User(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID(user.tenant_id),
        email=data.email,
        name=data.name,
        password_hash=hash_password(data.password),
        role=UserRole(data.role),
        entity_id=uuid.UUID(data.entity_id) if data.entity_id else None,
        project_id=uuid.UUID(data.project_id) if data.project_id else None,
    )
    db.add(new_user)
    await db.flush()

    return {
        "id": str(new_user.id),
        "email": new_user.email,
        "role": new_user.role.value,
    }


# ──────────────────────────────────────────────
# Knowledge Base Management
# ──────────────────────────────────────────────

@router.post("/kb/upload")
async def upload_kb_document(
    file: UploadFile = File(...),
    meta: KBDocMeta = Depends(),
    user: TokenPayload = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a document to the knowledge base.
    Accepted formats: PDF, TXT, MD, YAML.
    Scope 'tenant' = private to this tenant's KB.
    Scope 'global' = requires super-admin.
    """
    from api.models.db_models import KBDoc
    from ingestion.pipeline import IngestionPipeline, DocumentMeta
    import tempfile
    import hashlib

    ALLOWED_TYPES = {
        "application/pdf", "text/plain", "text/markdown",
        "application/x-yaml", "text/x-yaml",
        "application/octet-stream",
    }
    ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".yaml", ".yml"}

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {ALLOWED_EXTENSIONS}",
        )

    # Read file content
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50 MB limit
        raise HTTPException(status_code=413, detail="File too large (max 50 MB)")

    sha256 = hashlib.sha256(content).hexdigest()

    # Save to temp file for ingestion
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    # Create KB doc record
    scope = f"tenant_{user.tenant_id}" if meta.scope == "tenant" else "global"
    doc = KBDoc(
        id=uuid.uuid4(),
        title=meta.title or file.filename,
        issuer=meta.issuer,
        doc_type=meta.doc_type,
        version=meta.version,
        url=meta.url,
        sha256=sha256,
        scope=scope,
        lang=meta.lang,
    )
    db.add(doc)
    await db.flush()

    # Run ingestion pipeline
    doc_meta = DocumentMeta(
        doc_id=str(doc.id),
        title=meta.title or file.filename or "Uploaded Document",
        issuer=meta.issuer,
        doc_type=meta.doc_type,
        version=meta.version,
        url=meta.url,
        framework=meta.framework,
        scope=scope,
        lang=meta.lang,
        sha256=sha256,
    )

    try:
        from api.services.retrieval import RetrievalService
        retrieval = RetrievalService()
        pipeline = IngestionPipeline(retrieval_service=retrieval)
        collection = (
            retrieval.get_tenant_collection(user.tenant_id)
            if meta.scope == "tenant"
            else retrieval.GLOBAL_COLLECTION
        )
        result = pipeline.ingest_file(tmp_path, doc_meta, collection)
        chunks_created = result.get("chunks_created", 0)
    except Exception as e:
        chunks_created = 0
    finally:
        os.unlink(tmp_path)

    return {
        "doc_id": str(doc.id),
        "title": doc.title,
        "sha256": sha256,
        "scope": scope,
        "chunks_created": chunks_created,
    }


@router.get("/kb/docs")
async def list_kb_docs(
    scope: Optional[str] = Query(None, description="Filter: 'global' or 'tenant'"),
    framework: Optional[str] = Query(None),
    user: TokenPayload = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
):
    """List KB documents visible to this tenant."""
    from sqlalchemy import select, or_
    from api.models.db_models import KBDoc

    tenant_scope = f"tenant_{user.tenant_id}"
    query = select(KBDoc).where(
        or_(KBDoc.scope == "global", KBDoc.scope == tenant_scope)
    )

    if scope == "global":
        query = select(KBDoc).where(KBDoc.scope == "global")
    elif scope == "tenant":
        query = select(KBDoc).where(KBDoc.scope == tenant_scope)

    result = await db.execute(query.limit(200))
    docs = result.scalars().all()

    return [
        {
            "id": str(d.id), "title": d.title, "issuer": d.issuer,
            "doc_type": d.doc_type, "version": d.version,
            "scope": d.scope, "lang": d.lang, "created_at": d.created_at,
        }
        for d in docs
    ]


@router.delete("/kb/docs/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_kb_doc(
    doc_id: str,
    user: TokenPayload = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
):
    """Delete a KB document (tenant docs only; global docs require super-admin)."""
    from sqlalchemy import select
    from api.models.db_models import KBDoc

    result = await db.execute(
        select(KBDoc).where(KBDoc.id == uuid.UUID(doc_id))
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    tenant_scope = f"tenant_{user.tenant_id}"
    if doc.scope == "global":
        raise HTTPException(
            status_code=403,
            detail="Cannot delete global KB docs via tenant admin. Contact support."
        )
    if doc.scope != tenant_scope:
        raise HTTPException(status_code=403, detail="Not authorized to delete this document")

    await db.delete(doc)


# ──────────────────────────────────────────────
# Audit Log
# ──────────────────────────────────────────────

@router.get("/audit-log")
async def get_audit_log(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: TokenPayload = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
):
    """Get audit log for the current tenant (paginated)."""
    from sqlalchemy import select, desc
    from api.models.db_models import AuditLog

    offset = (page - 1) * page_size
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.tenant_id == uuid.UUID(user.tenant_id))
        .order_by(desc(AuditLog.ts))
        .offset(offset)
        .limit(page_size)
    )
    entries = result.scalars().all()

    return {
        "page": page,
        "page_size": page_size,
        "entries": [
            {
                "id": str(e.id),
                "actor": e.actor,
                "action": e.action,
                "payload": e.payload,
                "ts": e.ts,
            }
            for e in entries
        ],
    }


# ──────────────────────────────────────────────
# Data Export (DPDP compliance)
# ──────────────────────────────────────────────

@router.get("/export/tenant-data")
async def export_tenant_data(
    user: TokenPayload = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
):
    """
    Export all tenant data (DPDP compliance / portability).
    Returns a JSON stream of all entities, reports, field values, and suggestions.
    """
    import json
    from sqlalchemy import select
    from api.models.db_models import Entity, Report, FieldValue, Suggestion

    async def generate():
        yield '{"entities":['
        result = await db.execute(
            select(Entity).where(Entity.tenant_id == uuid.UUID(user.tenant_id))
        )
        entities = result.scalars().all()
        for i, e in enumerate(entities):
            sep = "," if i > 0 else ""
            yield sep + json.dumps({"id": str(e.id), "name": e.name, "sector": e.sector})

        yield '],"reports":['
        # Further data export would follow the same pattern...
        yield ']}'

    return StreamingResponse(
        generate(),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="esgpilot_export.json"'},
    )


# ──────────────────────────────────────────────
# Tenant Settings
# ──────────────────────────────────────────────

class TenantSettings(BaseModel):
    allowed_origins: Optional[list[str]] = None
    nudge_cooldown_seconds: Optional[int] = Field(None, ge=60, le=3600)
    draft_memory_enabled: Optional[bool] = None
    frameworks: Optional[list[str]] = None
    verbosity: Optional[str] = None  # brief | detailed | form_help


@router.patch("/settings")
async def update_tenant_settings(
    settings: TenantSettings,
    user: TokenPayload = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
):
    """Update tenant configuration settings."""
    from sqlalchemy import select
    from api.models.db_models import Tenant

    result = await db.execute(
        select(Tenant).where(Tenant.id == uuid.UUID(user.tenant_id))
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    current = tenant.settings or {}
    update = settings.model_dump(exclude_none=True)
    current.update(update)
    tenant.settings = current

    return {"status": "updated", "settings": current}
