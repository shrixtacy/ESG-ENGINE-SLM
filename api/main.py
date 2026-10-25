"""
ESGPilot — Main FastAPI Application.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.core.config import get_settings
from api.routes import forms, knowledge, portfolio, admin

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 ESGPilot starting in {settings.environment} mode")
    try:
        from api.services.retrieval import RetrievalService
        RetrievalService().ensure_collections()
        print("✅ Qdrant collections ready")
    except Exception as e:
        print(f"⚠️  Qdrant not available: {e}")
    yield
    print("👋 ESGPilot shutting down")


app = FastAPI(
    title="ESGPilot API",
    description="SLM-powered ESG reporting copilot.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(forms.router)
app.include_router(knowledge.router)
app.include_router(portfolio.router)
app.include_router(admin.router)


@app.get("/", tags=["Health"])
async def root():
    return {"service": "ESGPilot", "version": "0.1.0", "status": "running", "docs": "/docs"}


@app.get("/health", tags=["Health"])
async def health():
    """Fast health check — no blocking DB calls."""
    services = {}

    # Qdrant (non-blocking, short timeout)
    try:
        from qdrant_client import QdrantClient
        QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port,
                     timeout=1).get_collections()
        services["qdrant"] = "ok"
    except Exception:
        services["qdrant"] = "unavailable"

    # Redis (non-blocking)
    try:
        import redis as r
        r.from_url(settings.redis_url, socket_connect_timeout=1).ping()
        services["redis"] = "ok"
    except Exception:
        services["redis"] = "unavailable"

    # Ollama / vLLM
    try:
        import httpx
        resp = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=1)
        services["llm"] = "ok" if resp.status_code == 200 else "unavailable"
    except Exception:
        services["llm"] = "unavailable"

    return {
        "status": "ok",
        "api": "running",
        "services": services,
        "mode": settings.environment,
    }
