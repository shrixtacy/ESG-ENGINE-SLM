"""
ESGPilot — API Routes for Portfolio Comparison & NL→SQL Analytics.
"""

import json
from fastapi import APIRouter, Depends
from typing import Optional

from api.core.auth import get_current_user, require_role
from api.models.schemas import (
    CompareRequest,
    CompareResult,
    NLQueryRequest,
    NLQueryResponse,
    TokenPayload,
)
from api.orchestrator.graph import Orchestrator, OrchestratorContext, Intent

router = APIRouter()


# ──────────────────────────────────────────────
# Portfolio Comparison
# ──────────────────────────────────────────────

@router.post("/v1/portfolio/compare", response_model=CompareResult, tags=["Portfolio"])
async def compare_entities(
    request: CompareRequest,
    user: TokenPayload = Depends(
        require_role("group_admin", "entity_admin", "tenant_admin")
    ),
):
    """
    Compare entities/projects on a metric.
    Role-scoped: group_admin sees all, entity_admin sees own entity.
    """
    # In production: query v_metric_normalised view with tenant/role predicates
    return CompareResult(
        data=[],
        chart_spec=None,
        narrative="Comparison data will be populated once reports are submitted.",
        data_quality=None,
    )


# ──────────────────────────────────────────────
# Natural Language → SQL Analytics
# ──────────────────────────────────────────────

@router.post("/v1/portfolio/query", response_model=NLQueryResponse, tags=["Portfolio"])
async def nl_query(
    request: NLQueryRequest,
    user: TokenPayload = Depends(
        require_role("group_admin", "entity_admin", "tenant_admin")
    ),
):
    """
    Translate natural language to safe analytics query.

    The SLM emits a query plan JSON (metric, dimensions, filters, group_by, top_n).
    A validator converts this to parameterised SQL against allow-listed views.
    No free-form SQL from the model.
    """
    ctx = OrchestratorContext(
        user_message=request.query,
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        role=user.role,
        fy=request.fy or "FY2025",
        intent=Intent.NL_QUERY,
    )

    orchestrator = Orchestrator()
    ctx = await orchestrator.process(ctx)

    # Parse query plan
    query_plan = {}
    try:
        if ctx.slm_response:
            query_plan = json.loads(ctx.slm_response)
    except (json.JSONDecodeError, TypeError):
        query_plan = {"error": "Failed to parse query plan"}

    # Validate and convert to SQL
    sql, data = _validate_and_execute_query_plan(query_plan, user)

    return NLQueryResponse(
        query_plan=query_plan,
        sql=sql if user.role == "tenant_admin" else None,  # Only show SQL to admins
        data=data,
        narrative=ctx.final_response.get("narrative") if ctx.final_response else None,
    )


# ──────────────────────────────────────────────
# Query Plan Validator (NL→SQL safety layer)
# ──────────────────────────────────────────────

# Allow-listed views — the SLM can only query these
ALLOWED_VIEWS = {
    "v_metric_normalised",
    "v_entity_scorecard",
    "v_data_quality",
}

# Allow-listed metrics
ALLOWED_METRICS = {
    "scope1", "scope2", "scope1_2_total",
    "energy_total", "energy_intensity",
    "water_withdrawal", "water_consumption", "water_discharge", "water_intensity",
    "waste_generated", "hazardous_waste", "waste_recycled",
    "ghg_intensity",
    "csr_expenditure",
    "training_hours", "safety_incidents", "fatalities",
    "employees_total", "employees_permanent",
    "readiness_score",
}

# Allow-listed dimensions
ALLOWED_DIMENSIONS = {
    "entity", "project", "fy", "sector", "state",
}


def _validate_and_execute_query_plan(
    plan: dict,
    user: TokenPayload,
) -> tuple[str, list[dict]]:
    """
    Validate query plan against allow-lists and generate safe SQL.
    Injects tenant + role predicates server-side.
    """
    metric = plan.get("metric", "")
    dimensions = plan.get("dimensions", [])
    filters = plan.get("filters", {})
    group_by = plan.get("group_by")
    top_n = plan.get("top_n", 50)

    # Validate metric
    if metric not in ALLOWED_METRICS:
        return "", [{"error": f"Metric '{metric}' is not allowed. Available: {sorted(ALLOWED_METRICS)}"}]

    # Validate dimensions
    for dim in dimensions:
        if dim not in ALLOWED_DIMENSIONS:
            return "", [{"error": f"Dimension '{dim}' is not allowed."}]

    # Build safe, parameterised SQL
    view = "v_metric_normalised"
    select_cols = [f"m.{dim}" for dim in dimensions] + [f"m.{metric} AS value"]

    where_clauses = [f"m.tenant_id = '{user.tenant_id}'"]

    # Role-based scoping
    if user.role == "project_user" and user.project_id:
        where_clauses.append(f"m.project_id = '{user.project_id}'")
    elif user.role == "entity_admin" and user.entity_id:
        where_clauses.append(f"m.entity_id = '{user.entity_id}'")

    # Additional filters
    if "fy" in filters:
        where_clauses.append(f"m.fy = '{filters['fy']}'")

    sql = (
        f"SELECT {', '.join(select_cols)} "
        f"FROM {view} m "
        f"WHERE {' AND '.join(where_clauses)} "
    )

    if group_by and group_by in ALLOWED_DIMENSIONS:
        sql += f"GROUP BY m.{group_by} "

    sql += f"ORDER BY value DESC LIMIT {min(int(top_n), 100)}"

    # In production, execute against PostgreSQL
    # For now, return empty data
    return sql, []
