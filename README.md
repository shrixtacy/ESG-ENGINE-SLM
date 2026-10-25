# ESG-ENGINE-SLM

> An embeddable, SLM-powered ESG reporting copilot for Indian listed companies and large groups.

ESG-ENGINE-SLM (working name **ESGPilot**) plugs into any ESG reporting application via a REST/WebSocket API and a drop-in JavaScript widget. It reads live form data, answers compliance doubts with citations, reviews entries against BRSR / UN SDGs / India frameworks, and compares subsidiaries or projects across large groups — all without a frontier-size LLM.

The core design principle: **the SLM explains and recommends; it never calculates or decides compliance on its own.** Numbers (emissions, intensity ratios, readiness scores) come exclusively from a deterministic rules and analytics engine. The SLM receives those results as structured context and narrates them. This eliminates hallucinated metrics — the #1 risk in ESG tooling.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Running with Docker](#running-with-docker)
- [Frontend (Widget / SDK)](#frontend-widget--sdk)
- [API Reference](#api-reference)
- [Evaluation](#evaluation)
- [Contributing](#contributing)
- [License](#license)

---

## Features

| Area | What it does |
|---|---|
| **Live form analysis** | Reads ESG form fields in real-time (debounced), runs completeness, consistency, and outlier checks, and surfaces a nudge when something needs attention |
| **Compliance Q&A** | Answers BRSR / NGRBC / SDG / CSR doubts with citations (document, clause, version/date); says "I don't know" when evidence is insufficient |
| **Rules engine** | Deterministic Python library — Scope 1/2 calculations, unit conversions, cross-field arithmetic, YoY delta checks, disclosure-quality scoring |
| **RAG knowledge base** | Hybrid dense + sparse retrieval (BGE-M3) over versioned regulatory documents; reranked and filtered by framework, FY, and tenant |
| **Group / portfolio mode** | Compare subsidiaries and projects on normalised metrics; NL → safe parameterised SQL against allow-listed analytics views |
| **Drop-in widget** | Shadow DOM TypeScript widget (< 80 KB gz); blur-modal panel with Suggestions / Ask / Compare tabs; `Jump to field` button |
| **Multi-tenant** | Group → Subsidiary → Project hierarchy; PostgreSQL Row-Level Security; per-tenant vector namespace in Qdrant |
| **On-prem ready** | Docker / Kubernetes Helm chart; CPU fallback (llama.cpp + 3B model) for air-gapped deployments |

**Frameworks covered (v1):** SEBI BRSR + BRSR Core, NGRBC principles, UN SDGs (17 goals / 169 targets), India SDG framework (MoSPI NIF, NITI Aayog), GRI, Companies Act s.135 (CSR)

**Planned (v1.5):** ISSB IFRS S1/S2, TCFD, SASB, CDP, GHG Protocol, India CCTS, CSRD/ESRS

---

## Architecture

```
┌────────────────────────────────────────────────────────┐
│  Host Application (client's reporting app)              │
│  Forms / Pages  ←→  ESGPilot Widget (Shadow DOM)        │
└────────────────────────┬───────────────────────────────┘
                         │ WSS / HTTPS + JWT
                         ▼
               ┌─────────────────┐
               │  API Gateway    │  auth, rate-limit, tenant resolve
               └────────┬────────┘
                        │
          ┌─────────────▼──────────────┐
          │   Orchestrator (LangGraph) │
          │  ┌──────────┐ ┌─────────┐  │
          │  │  Rules   │ │  RAG    │  │
          │  │ Engine   │ │ Service │  │
          │  └──────────┘ └─────────┘  │
          │  ┌──────────┐ ┌─────────┐  │
          │  │  SLM     │ │ Guard-  │  │
          │  │(vLLM 7B) │ │ rails   │  │
          │  └──────────┘ └─────────┘  │
          └──────────┬─────────────────┘
                     │
          ┌──────────┴──────────┐
          │  Qdrant (vectors)   │  PostgreSQL (RLS)
          └─────────────────────┘
```

Full architecture documentation is in [`ARCHITECTURE.md`](ARCHITECTURE.md). The build spec and product requirements are in [`BUILD_SPEC.md`](BUILD_SPEC.md).

---

## Tech Stack

| Layer | Choice |
|---|---|
| API | FastAPI + WebSocket/SSE |
| Orchestration | LangGraph |
| SLM serving | vLLM (GPU) / llama.cpp (CPU/dev) |
| Embeddings | BAAI/bge-m3 (dense + sparse) |
| Reranker | bge-reranker-v2-m3 |
| Vector DB | Qdrant (hybrid search, per-tenant namespaces) |
| Relational DB | PostgreSQL with Row-Level Security |
| Widget / SDK | TypeScript, Shadow DOM, Vite |
| Cache / Queue | Redis, Celery / Arq |
| Observability | Langfuse, OpenTelemetry, Prometheus |
| Doc parsing | PyMuPDF, BeautifulSoup4, Tesseract OCR |
| Eval | RAGAS + custom BRSR gold set |
| Infra | Docker, Kubernetes (Helm) |

---

## Project Structure

```
ESG-ENGINE-SLM/
├── api/                        # FastAPI application
│   ├── core/                   # Config, auth, database connection
│   ├── models/                 # SQLAlchemy models + Pydantic schemas
│   ├── orchestrator/           # LangGraph agent graph
│   ├── routes/                 # API route handlers
│   ├── services/               # Inference, retrieval, guardrails
│   └── main.py
├── ingestion/                  # Offline ingestion pipeline
│   ├── crawlers/               # SEBI, MCA, UN SDG crawlers
│   └── parsers/                # PDF, HTML, table parsers
├── rules/                      # Deterministic rules & analytics engine
│   ├── calculators/            # Scope 1/2 emissions, unit conversions
│   ├── checks/                 # Completeness, boundary, disclosure quality
│   └── tests/                  # Unit tests for every rule
├── kb/                         # Knowledge base definitions
│   ├── emission_factors/       # India emission factor tables (YAML)
│   ├── field_catalogue/        # BRSR field catalogue (YAML)
│   └── sources/                # KB source manifest
├── sdk/                        # TypeScript widget + SDK
│   └── src/
│       ├── adapters/           # L1 (schema push) / L2 (attributes) / L3 (auto)
│       ├── components/         # ChatPanel, SuggestionCard
│       ├── core/               # ESGPilotSDK, NudgeManager, Transport
│       └── types.ts
├── esg-frontend/               # Next.js reference frontend
├── training/                   # SFT / DPO / quantisation scripts
├── eval/                       # Evaluation harness + BRSR gold set
├── docs/                       # Analytics views SQL, n8n workflow JSON
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── ARCHITECTURE.md
├── BUILD_SPEC.md
└── RESOURCES.md                # Data sources, model links, licence register
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+ (for SDK / frontend)
- Docker & Docker Compose
- PostgreSQL 16+ (or use the Docker Compose stack)
- Redis (or use the Docker Compose stack)
- Qdrant (or use the Docker Compose stack)
- A GPU with ≥ 24 GB VRAM for the 7B 4-bit model (or run in CPU mode with a 3B model)

### 1. Clone and set up environment

```bash
git clone https://github.com/shrixtacy/ESG-ENGINE-SLM.git
cd ESG-ENGINE-SLM
cp .env.example .env
# Edit .env — fill in database URLs, API keys, model paths
```

### 2. Install Python dependencies

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install PyTorch with the correct CUDA version for your GPU:
pip install torch==2.4.0+cu121 --index-url https://download.pytorch.org/whl/cu121

pip install -r requirements.txt
```

### 3. Initialise the database

```bash
# Start PostgreSQL (or point .env at an existing instance)
docker compose up -d postgres

# Run migrations
alembic upgrade head

# (Optional) seed initial data
psql $DATABASE_URL -f api/core/init_db.sql
```

### 4. Start the API

```bash
uvicorn api.main:app --reload --port 8000
```

Visit `http://localhost:8000/docs` for the interactive API explorer.

### 5. Start the SDK development build

```bash
cd sdk
npm install
npm run dev
```

---

## Configuration

All runtime settings are loaded from environment variables (or a `.env` file). Copy `.env.example` to `.env` and fill in the values.

Key variables:

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `QDRANT_URL` | Qdrant endpoint |
| `REDIS_URL` | Redis connection string |
| `SECRET_KEY` | JWT signing secret |
| `LLM_BASE_URL` | vLLM or Ollama endpoint |
| `LLM_MODEL_NAME` | Model identifier (e.g. `Qwen/Qwen2.5-7B-Instruct`) |
| `EMBEDDINGS_MODEL` | Embedding model path (default `BAAI/bge-m3`) |
| `LANGFUSE_SECRET_KEY` | Langfuse observability key (optional) |

---

## Running with Docker

The Docker Compose stack starts the full local environment (API, PostgreSQL, Qdrant, Redis):

```bash
docker compose up --build
```

For GPU-accelerated SLM inference, add the vLLM service separately or uncomment the relevant section in `docker-compose.yml` and ensure the NVIDIA Container Toolkit is installed.

---

## Frontend (Widget / SDK)

The embeddable widget lives in `sdk/`. The reference Next.js app is in `esg-frontend/`.

**Embedding the widget in any host app:**

```html
<script src="https://cdn.esgpilot.io/sdk.js"
  data-tenant="my-org"
  data-key="pk_live_xxx"
  data-position="bottom-right"
  data-lang="en">
</script>
<script>
  ESGPilot.init({
    user: { id: "u_123", role: "project_user", projectId: "proj_456" },
    mode: "single"
  });
  ESGPilot.attachForm("#brsr-form", { framework: "BRSR", section: "C-P6" });
</script>
```

Three integration levels are supported:

| Level | Method | When to use |
|---|---|---|
| L1 – Schema push | `esgpilot.setFormContext({ schema, values })` | You control the host app |
| L2 – Declarative attributes | `data-esg-field="p6.scope1"` on inputs | Light-touch markup change |
| L3 – Auto-discovery | SDK scans labels/placeholders | Third-party apps you can't modify |

---

## API Reference

Full OpenAPI spec available at `/docs` (Swagger UI) or `/redoc` when the server is running.

Core endpoints:

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/sessions` | Start a session (returns short-lived JWT) |
| `WS` | `/v1/chat/stream` | Streaming chat |
| `POST` | `/v1/forms/context` | Push / update form schema + values |
| `POST` | `/v1/forms/analyze` | Run rules + SLM review on a form section |
| `GET` | `/v1/suggestions` | Fetch current suggestions for a form |
| `POST` | `/v1/kb/ask` | Stateless Q&A with citations |
| `POST` | `/v1/portfolio/compare` | Compare entities / projects |
| `POST` | `/v1/portfolio/query` | NL → safe analytics query |
| `POST` | `/v1/sdg/map` | Text → SDG goals / targets |
| `POST` | `/v1/feedback` | Submit thumbs-up / thumbs-down |
| `GET/POST` | `/v1/admin/*` | Tenant, KB, and config management |

---

## Evaluation

The eval harness lives in `eval/`. Run the BRSR gold-set evaluation:

```bash
pytest eval/harness/ -v
```

Acceptance targets:

- Retrieval recall@5 ≥ 0.90, MRR ≥ 0.80
- Answer faithfulness (RAGAS) ≥ 0.92
- Citation precision ≥ 95%
- Correct abstention on out-of-corpus questions ≥ 90%
- Rules engine: 100% pass on BRSR unit tests

---

## Contributing

Contributions are welcome. Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a pull request and follow our [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

Good first issues are labelled `good first issue` in the issue tracker.

---

## License

This project is licensed under the **Apache License 2.0** — see [`LICENSE`](LICENSE) for details.

> **Disclaimer:** ESGPilot is an assistive tool. It is not a substitute for professional legal, assurance, or compliance advice. All regulatory interpretations should be verified with a qualified ESG practitioner.
