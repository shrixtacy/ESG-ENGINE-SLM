"""
ESGPilot — API Routes for Knowledge Q&A, Chat, SDG Mapping.
"""

import json
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from typing import Optional

from api.core.auth import get_current_user
from api.models.schemas import (
    KBQuestion,
    KBAnswer,
    CitationChip,
    ChatRequest,
    ChatMessage,
    SDGMapRequest,
    SDGMapResponse,
    SDGTag,
    TokenPayload,
)
from api.orchestrator.graph import Orchestrator, OrchestratorContext, Intent

router = APIRouter()


# ──────────────────────────────────────────────
# Knowledge Q&A
# ──────────────────────────────────────────────

@router.post("/v1/kb/ask", response_model=KBAnswer, tags=["Knowledge"])
async def ask_knowledge_base(
    question: KBQuestion,
    user: TokenPayload = Depends(get_current_user),
):
    """
    Stateless Q&A with citations.
    Answers compliance/regulatory doubts from the knowledge base.
    """
    ctx = OrchestratorContext(
        user_message=question.question,
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        role=user.role,
        framework=question.framework or "BRSR",
        fy=question.fy or "FY2025",
        intent=Intent.KB_QUESTION,
    )

    # In production, orchestrator would be injected via DI
    orchestrator = Orchestrator()
    ctx = await orchestrator.process(ctx)

    response = ctx.final_response or {}

    return KBAnswer(
        answer=response.get("answer", "I'm unable to answer this question at the moment."),
        citations=[
            CitationChip(**c) for c in response.get("citations", [])
        ],
        confidence=response.get("confidence", 0.0),
        abstained=response.get("abstained", True),
    )


# ──────────────────────────────────────────────
# SDG Mapping
# ──────────────────────────────────────────────

@router.post("/v1/sdg/map", response_model=SDGMapResponse, tags=["SDG"])
async def map_to_sdg(
    request: SDGMapRequest,
    user: TokenPayload = Depends(get_current_user),
):
    """Map text/activity to UN SDG goals and targets."""
    ctx = OrchestratorContext(
        user_message=request.text,
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        role=user.role,
        intent=Intent.SDG_MAP,
    )

    orchestrator = Orchestrator()
    ctx = await orchestrator.process(ctx)

    # Parse SLM response as SDG tags
    tags = []
    try:
        if ctx.slm_response:
            parsed = json.loads(ctx.slm_response)
            if isinstance(parsed, list):
                tags = [SDGTag(**t) for t in parsed]
    except (json.JSONDecodeError, TypeError):
        pass

    return SDGMapResponse(tags=tags)


# ──────────────────────────────────────────────
# WebSocket Chat (streaming)
# ──────────────────────────────────────────────

@router.websocket("/v1/chat/stream")
async def chat_stream(websocket: WebSocket):
    """
    WebSocket endpoint for streaming chat.
    Client sends messages, server streams responses token by token.
    """
    await websocket.accept()

    try:
        while True:
            # Receive message
            data = await websocket.receive_json()

            message = data.get("message", "")
            framework = data.get("framework", "BRSR")
            fy = data.get("fy", "FY2025")
            form_context = data.get("form_context")

            ctx = OrchestratorContext(
                user_message=message,
                framework=framework,
                fy=fy,
                tenant_id=data.get("tenant_id", "demo"),
                user_id=data.get("user_id", "demo_user"),
                role=data.get("role", "project_user"),
            )

            if form_context:
                ctx.form_id = form_context.get("form_id")
                ctx.section = form_context.get("section")
                ctx.field_values = form_context.get("fields", {})

            # Process through orchestrator
            orchestrator = Orchestrator()
            ctx = await orchestrator.process(ctx)

            # Send response
            response = ctx.final_response or {"answer": ctx.slm_response}
            await websocket.send_json({
                "type": "response",
                "data": response,
                "request_id": ctx.request_id,
                "intent": ctx.intent.value if ctx.intent else "unknown",
                "latency_ms": ctx.latency_ms,
            })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e),
            })
        except Exception:
            pass
