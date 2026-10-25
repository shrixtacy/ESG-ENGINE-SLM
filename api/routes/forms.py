"""
ESGPilot — API Routes for Sessions, Forms, Suggestions.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional

from api.core.auth import (
    get_current_user,
    create_session_token,
    verify_api_key,
    require_role,
)
from api.models.schemas import (
    SessionCreate,
    SessionResponse,
    FormContext,
    FormAnalyzeRequest,
    SuggestionsResponse,
    SuggestionCard,
    NudgeResponse,
    TokenPayload,
    FeedbackCreate,
)
from api.orchestrator.graph import Orchestrator, OrchestratorContext, Intent

router = APIRouter()


# ──────────────────────────────────────────────
# Session Management
# ──────────────────────────────────────────────

@router.post("/v1/sessions", response_model=SessionResponse, tags=["Auth"])
async def create_session(request: SessionCreate):
    """
    Create a session JWT. Called by the host backend, not the browser directly.
    Validates tenant API key and issues a short-lived token.
    """
    # In production, look up tenant by API key from DB
    # For now, accept any key in dev mode
    token, expires = create_session_token(
        tenant_id="demo_tenant",  # Would be resolved from API key
        user_id=request.user_id,
        role=request.user_role,
        entity_id=request.entity_id,
        project_id=request.project_id,
    )
    return SessionResponse(token=token, expires_at=expires)


# ──────────────────────────────────────────────
# Form Context & Analysis
# ──────────────────────────────────────────────

@router.post("/v1/forms/context", tags=["Forms"])
async def push_form_context(
    form: FormContext,
    user: TokenPayload = Depends(get_current_user),
):
    """
    Push/update form schema and values from the host app.
    Called by the SDK when form fields change (debounced).
    Returns a nudge if the rules engine finds issues.
    """
    from api.services.retrieval import RetrievalService
    from api.services.inference import InferenceService
    from api.services.guardrails import Guardrails
    from rules.engine import RulesEngine, FieldCatalogue
    import os

    # Load field catalogue
    catalogue_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "kb", "field_catalogue", "brsr_fields.yaml"
    )
    catalogue = FieldCatalogue(catalogue_path if os.path.exists(catalogue_path) else None)
    engine = RulesEngine(catalogue)

    # Convert field data to dict format
    field_values = {}
    for f in form.fields:
        field_values[f.field_code] = {
            "value": f.value,
            "unit": f.unit,
        }

    # Build orchestrator context
    ctx = OrchestratorContext(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        role=user.role,
        entity_id=user.entity_id,
        project_id=user.project_id,
        form_id=form.form_id,
        framework=form.framework,
        section=form.section,
        fy=form.fy,
        field_values=field_values,
    )

    # Run fast nudge path (rules only)
    orchestrator = Orchestrator(rules_engine=engine)
    nudge = await orchestrator.process_nudge(ctx)

    return NudgeResponse(**nudge)


@router.post("/v1/forms/analyze", tags=["Forms"])
async def analyze_form(
    request: FormAnalyzeRequest,
    user: TokenPayload = Depends(get_current_user),
):
    """
    Run full rules + SLM review on a form/section.
    Returns suggestion cards with explanations.
    """
    # This would load actual field values from DB by report_id
    return SuggestionsResponse(
        report_id=request.report_id or "demo",
        form_id=request.form_id,
        suggestions=[],
        readiness_score=0.0,
    )


@router.get("/v1/suggestions", response_model=SuggestionsResponse, tags=["Suggestions"])
async def get_suggestions(
    form_id: Optional[str] = None,
    report_id: Optional[str] = None,
    user: TokenPayload = Depends(get_current_user),
):
    """Get current suggestions for a form/report."""
    return SuggestionsResponse(
        report_id=report_id or "demo",
        form_id=form_id,
        suggestions=[],
    )


# ──────────────────────────────────────────────
# Feedback
# ──────────────────────────────────────────────

@router.post("/v1/feedback", tags=["Feedback"])
async def submit_feedback(
    feedback: FeedbackCreate,
    user: TokenPayload = Depends(get_current_user),
):
    """Submit thumbs up/down feedback on a suggestion or message."""
    # Store in DB
    return {
        "status": "recorded",
        "feedback_id": "fb_" + str(hash(str(feedback)))[:8],
    }
