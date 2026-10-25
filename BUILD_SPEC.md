# BUILD_SPEC.md — ESG Copilot (working name: **ESGPilot**)

> An embeddable, SLM-powered ESG reporting copilot. Plugs into any reporting app via API + JS widget, reads form data live, answers compliance doubts, reviews entries against BRSR / UN SDGs / India frameworks, and compares subsidiaries/projects for large groups.

---

## 1. Product Summary

| Item | Decision |
|---|---|
| Model class | **SLM (3B–8B)** + RAG + deterministic rules engine. No frontier-size LLM. |
| Delivery | (a) REST/WebSocket API, (b) drop-in JS widget (bottom-right bot icon) |
| Primary users | ESG/sustainability officers, plant/project data-entry staff, group-level ESG heads |
| Frameworks covered (v1) | SEBI BRSR + BRSR Core, NGRBC principles, UN SDGs (17 goals/169 targets/indicators), India SDG framework (MoSPI NIF, NITI Aayog index), GRI, Companies Act s.135 (CSR) |
| Frameworks (v1.5) | ISSB IFRS S1/S2, TCFD, SASB, CDP, GHG Protocol, India CCTS, CSRD/ESRS (for export-facing clients) |
| Tenancy | Multi-tenant: **Group → Subsidiary → Project** hierarchy (supports 200+ subsidiaries, e.g. MEIL-scale) |

### Core Principle (important)
**The SLM explains and recommends. It never calculates or decides compliance on its own.**
Numbers (emissions, intensity ratios, scores, completeness) come from a **deterministic rules/analytics engine**. The SLM gets those results as structured context and narrates them. This kills hallucinated numbers — the #1 risk in ESG tooling.

---

## 2. Functional Requirements

### FR-1 Embedded Widget
- FR-1.1 Floating bot icon, bottom-right, on every page where SDK is loaded.
- FR-1.2 Widget attaches to forms via **Form Adapter** (see §5) and reads field values **live** (debounced, on blur + on change).
- FR-1.3 When analysis finds something useful (missing mandatory field, outlier, inconsistency, better disclosure possible), show a small nudge popup: **"Want to explore some suggestions?"** with `Yes` / `Later`.
- FR-1.4 On `Yes`: chat panel opens as a top-layer modal; page behind gets `backdrop-filter: blur(8px)` + dim overlay; ESC / outside click to close; focus trap for accessibility.
- FR-1.5 Nudge frequency capped (max 1 per form-section per 5 min; user can mute per session).
- FR-1.6 Widget isolated via **Shadow DOM** so host-app CSS never breaks it and vice versa.
- FR-1.7 Theming via config (colors, logo, position, language).

### FR-2 Live Form Understanding
- FR-2.1 Read current form schema + values + validation state.
- FR-2.2 Map each field → framework reference (e.g. field "Total Scope 1 emissions" → BRSR Principle 6 Essential Indicator, GRI 305-1, SDG 13.2).
- FR-2.3 Field-level help: "What does this field mean? What unit? What's the source?" answered from the knowledge base.
- FR-2.4 Section-level review: completeness, consistency, plausibility, disclosure quality.
- FR-2.5 **Scoped suggestions mode**: only suggestions relevant to the *currently open* form/section, with explanation tied to *how to fill it* (not a generic ESG lecture).
- FR-2.6 Optional **suggest-fill** (proposes values/text; user must confirm — bot never auto-submits).

### FR-3 Knowledge Q&A (Compliance Brain)
- FR-3.1 Answer any employee doubt about ESG/BRSR/SDG/regulatory requirements with **citations** (document, section/clause, version/date).
- FR-3.2 Version-aware: knows which circular/amendment applies for which FY and which company class (top 1000 listed, value-chain phase-in, assurance phase-in, etc.).
- FR-3.3 Says "I don't know / not in my sources" instead of guessing. Confidence + citation required.
- FR-3.4 Glossary mode (Scope 1/2/3, intensity, PPA, EPR, GJ vs kWh conversions, etc.).
- FR-3.5 Languages: English + Hindi at v1; Odia/Telugu/Tamil etc. via translation layer at v2 (clients in India's regions).

### FR-4 Analysis & Recommendations
- FR-4.1 **Completeness check** vs selected framework (BRSR Section A/B/C, Core KPIs).
- FR-4.2 **Consistency checks** (e.g., total = sum of parts, units, YoY jumps, intensity vs turnover).
- FR-4.3 **Outlier detection** vs own history and vs peer projects (z-score / IQR; robust to small samples).
- FR-4.4 **Disclosure-quality review** for narrative fields (specific, measurable, time-bound, boundary stated).
- FR-4.5 **SDG mapping**: auto-tag activities/projects to SDGs & targets with rationale.
- FR-4.6 **Gap analysis** → prioritised recommendations (impact × effort), each with rationale + reference.
- FR-4.7 **Readiness score** per framework (rules-computed, explainable breakdown).

### FR-5 Group / Portfolio Comparison
- FR-5.1 Compare **subsidiary vs subsidiary**, **project vs project**, **project vs group average**, **vs previous FY**.
- FR-5.2 Normalised metrics (per ₹ crore turnover, per employee, per MW, per km road, per sq m built-up — sector-specific denominators).
- FR-5.3 Ranking, quartile position, best-practice surfacing ("Project X cuts diesel intensity 22% lower — here's what they report doing").
- FR-5.4 Data-quality heatmap: which subsidiaries have missing/late/low-quality data.
- FR-5.5 Natural-language queries: "Which 10 subsidiaries have highest Scope 2 intensity and incomplete water data?" → translated to safe, parameterised SQL (text-to-SQL with allow-listed views only).
- FR-5.6 Role-based scoping: a project user sees only their project (+ anonymised peer benchmarks if group allows).

### FR-6 Single-Entity Mode
- FR-6.1 Same engine, hierarchy flattened. Comparison features degrade gracefully to YoY + sector benchmarks.
- FR-6.2 "Only what I need" — user-controlled verbosity: `Brief` / `Detailed` / `Explain like form-help`.

### FR-7 Admin & Governance
- FR-7.1 Tenant console: API keys, allowed origins, framework selection, form-adapter configs, branding.
- FR-7.2 Knowledge base admin: upload client policies (e.g., MEIL internal ESG policy) into tenant-private index.
- FR-7.3 Audit log: every suggestion, citation, user action (accept/ignore), model version.
- FR-7.4 Feedback loop: 👍/👎 + reason → eval dataset.
- FR-7.5 Data export (DPDP compliance), delete-on-request.

---

## 3. Non-Functional Requirements

| Area | Target |
|---|---|
| Latency | Nudge analysis < 1.5 s (rules first, SLM async). Chat first token < 1.2 s, full answer < 6 s (7B quantised, GPU) |
| Throughput | 200 concurrent chats / GPU node (vLLM continuous batching) |
| Accuracy | Citation precision ≥ 95%; numeric hallucination rate ≈ 0 (numbers only from engine); eval set ≥ 600 Q&A |
| Availability | 99.5% v1, 99.9% v2 |
| Security | TLS 1.3, per-tenant isolation (row-level security + namespace per vector index), JWT short-lived tokens, encryption at rest, secrets in vault |
| Privacy | DPDP Act 2023 aligned; no tenant data used for training without opt-in; PII redaction before logging |
| Deployability | SaaS **and** on-prem/VPC (big groups like MEIL often demand this) — Docker/K8s Helm chart |
| Accessibility | WCAG 2.1 AA for widget |
| Browser support | Last 2 versions Chrome/Edge/Firefox/Safari; widget bundle < 80 KB gz (lazy-load chat panel) |

---

## 4. Model Strategy (SLM, not LLM)

### 4.1 Choice
| Role | Model candidates | Notes |
|---|---|---|
| Main generator | **Qwen2.5-7B-Instruct** (or 3B for edge), **Llama-3.1-8B-Instruct**, **Phi-3.5-mini** | Start with Qwen2.5-7B — strong instruction following + structured JSON + multilingual. Check licenses before commercial use. |
| Light router/classifier | Qwen2.5-0.5B/1.5B or fine-tuned DeBERTa/ModernBERT | Intent routing, field→framework mapping |
| Embeddings | **BAAI/bge-m3** (multilingual, dense+sparse) | Handles Hindi/English mix |
| Reranker | **bge-reranker-v2-m3** | Big precision jump for clause retrieval |
| Translation (v2) | **IndicTrans2** | Odia/Hindi/Telugu etc. |

### 4.2 What goes where
- **RAG** → all regulatory/framework *knowledge* (changes often, needs citations). **Do not bake law into weights.**
- **Fine-tuning (LoRA/QLoRA)** → *behaviour*: ESG reviewer tone, structured output (JSON schema), tool-calling, "cite or abstain", disclosure-quality critique, SDG tagging.
- **Rules engine** → validation, scoring, arithmetic, unit conversion, comparisons.
- **Tools** → SQL analytics, emission-factor lookup, SDG mapper, benchmark API.

### 4.3 Training plan
1. **Stage 0 – Baseline**: untuned model + RAG; build eval harness first.
2. **Stage 1 – SFT (LoRA r=16–64)** on ~5–15k curated examples: (a) doc-grounded Q&A with citations, (b) form-field explanation, (c) critique of ESG narratives, (d) SDG tagging, (e) JSON recommendation objects, (f) refusal/abstain cases.
3. **Stage 2 – Preference tuning (DPO/ORPO)**: pairs of good vs. hallucinated/uncited/over-verbose answers.
4. **Stage 3 – Domain-adaptive continued pretraining (optional)** on ESG corpus if baseline weak on terminology.
5. **Quantise** (AWQ/GPTQ 4-bit or GGUF Q4_K_M) → serve with vLLM / llama.cpp.
6. **Synthetic data**: use a larger teacher model *offline* to draft Q&A pairs from the corpus → **human SME review (ESG consultant) of at least 20%** → train. Never ship unreviewed synthetic data.

### 4.4 Output contract (structured)
Every recommendation is a JSON object, rendered by UI:
```json
{
  "id": "rec_8f2",
  "scope": "field|section|form|portfolio",
  "severity": "info|warn|critical",
  "title": "Scope 2 emissions look 3.4x higher than last FY",
  "why": "Electricity consumption rose 4% but Scope 2 rose 240%...",
  "how_to_fix": "Check emission factor year and unit (kWh vs MWh)...",
  "references": [{"doc": "BRSR Annexure I", "section": "P6 EI-7", "version": "2023-07-12"}],
  "sdg_tags": ["13.2", "7.2"],
  "confidence": 0.86,
  "source": "rule|slm|hybrid"
}
```

---

## 5. Form Integration Spec

### 5.1 Three integration levels (offer all)
| Level | How | Reliability | Use when |
|---|---|---|---|
| **L1 – Schema push** (preferred) | Host app calls `esgpilot.setFormContext({formId, schema, values})` | Highest | You control the app (your internal reporting apps) |
| **L2 – Declarative attributes** | Add `data-esg-field="p6.scope1"` `data-esg-form="brsr-c"` to inputs; SDK observes via `MutationObserver` + input events | High | Light-touch change to host markup |
| **L3 – Auto-discovery** | SDK scans labels/names/placeholders; classifier maps to framework fields | Medium (needs user confirm) | Third-party apps you can't modify |

### 5.2 SDK sketch
```html
<script src="https://cdn.esgpilot.io/sdk.js"
  data-tenant="meil" data-key="pk_live_xxx"
  data-position="bottom-right" data-lang="en"></script>
<script>
  ESGPilot.init({ user: { id, role, subsidiaryId, projectId }, mode: "group" });
  ESGPilot.attachForm("#brsr-form", { framework: "BRSR", section: "C-P6" });
</script>
```
Events emitted: `field_changed`, `section_completed`, `nudge_shown`, `suggestion_accepted`.

### 5.3 Privacy for live reading
- Only fields mapped as ESG fields are sent (allow-list). Password/PII inputs ignored.
- Tenant can set `redact: ["employee_name","aadhaar"]`.
- Values sent over WSS, not stored unless tenant enables "draft memory".

---

## 6. Group / Hierarchy Data Model (summary)

```
Tenant (Group)
 └─ Entity (Subsidiary / Partner)  [200+]
     └─ Project  [many]
         └─ Report (FY, framework)
             └─ Section → Field → Value (+ unit, source, evidence_url, status)
```
- Every value carries: `entity_id, project_id, fy, unit, source_type (meter/bill/estimate), evidence, entered_by, entered_at, verified_by`.
- Normalisation table: sector → denominators (turnover, MWh generated, km laid, MT cement…).
- Peer groups: define by sector + size + geography for fair comparison.

---

## 7. UX Spec

**States**
1. **Idle**: round icon bottom-right (48px), subtle pulse when nudge pending.
2. **Nudge**: small card above icon — *"Want to explore some suggestions?"* [Yes] [Later] [Mute].
3. **Panel (modal)**: centered or right-docked large panel, `z-index: max`, backdrop blur + dim; header (context chip: *BRSR · Principle 6 · Project Alpha*), tabs: **Suggestions | Ask | Compare** (Compare shown only in group mode).
4. **Suggestion cards**: severity color + title + why + how to fix + citation chips + `Jump to field` button (scrolls/focuses the field in the host form, then closes modal or minimises).
5. **Ask tab**: chat with streaming answers, citation chips open a side drawer with source excerpt.
6. **Compare tab**: charts (bar/quartile), table, "explain this chart" button.

**Details**: keyboard shortcuts, mobile bottom-sheet layout, "answer length" toggle, 👍/👎 per message.

---

## 8. API Surface (v1)

| Endpoint | Purpose |
|---|---|
| `POST /v1/sessions` | Start session (JWT from host backend) |
| `WS /v1/chat/stream` | Streaming chat |
| `POST /v1/forms/context` | Push/update schema + values |
| `POST /v1/forms/analyze` | Run rules + SLM review on form/section |
| `GET /v1/suggestions?formId=` | Current suggestions |
| `POST /v1/kb/ask` | Stateless Q&A with citations |
| `POST /v1/portfolio/compare` | Compare entities/projects (metrics, FY, peer group) |
| `POST /v1/portfolio/query` | NL → safe analytics |
| `POST /v1/sdg/map` | Text → SDG goals/targets |
| `POST /v1/feedback` | Ratings |
| `GET/POST /v1/admin/*` | Tenants, KB docs, configs |

Auth: tenant API key (server) + short-lived session JWT (browser). Rate limits per tenant/user.

---

## 9. Tech Stack

| Layer | Choice |
|---|---|
| Widget | TypeScript, Lit or Preact, Shadow DOM, Vite build |
| API | **FastAPI** (Python) + WebSocket/SSE |
| Orchestration | **LangGraph** (agent graph) — fits existing stack; n8n for ingestion/ops automation |
| Model serving | **vLLM** (GPU) / llama.cpp or Ollama (CPU/dev) |
| Vector DB | **Qdrant** (hybrid dense+sparse, payload filters per tenant/framework/version) — or pgvector for simplicity |
| Relational/analytics | PostgreSQL (RLS) + materialised views; ClickHouse/DuckDB later for 200+ entity analytics |
| Doc parsing | Docling / Unstructured + PyMuPDF; OCR (Tesseract/PaddleOCR) for scanned reports |
| Cache/queue | Redis, Celery/Arq |
| Observability | OpenTelemetry, Langfuse (LLM traces), Prometheus/Grafana |
| Eval | RAGAS + custom ESG gold set |
| Infra | Docker, K8s (Helm), GPU node (L4/A10/4090-class for 7B 4-bit) |
| CI/CD | GitHub Actions; model registry (HF private / MLflow) |

---

## 10. Milestones

| Phase | Weeks | Deliverables |
|---|---|---|
| **P0 – Foundations** | 1–2 | Corpus collection, legal/licence check, eval set skeleton, repo + infra |
| **P1 – Knowledge Brain** | 3–6 | Ingestion pipeline, chunking w/ clause metadata, hybrid retrieval + rerank, cited Q&A API, baseline SLM |
| **P2 – Rules Engine** | 5–8 | BRSR/BRSR Core field catalogue (machine-readable), completeness + consistency + unit checks, emission factor tables |
| **P3 – Widget + Form Adapter** | 7–10 | SDK, L1/L2 adapters, nudge popup, blur modal, field-jump |
| **P4 – Fine-tune** | 8–12 | SFT dataset (SME reviewed), LoRA training, DPO, quantised serving, eval gates |
| **P5 – Portfolio Mode** | 10–14 | Hierarchy model, normalisation, comparisons, NL→SQL, peer groups, RBAC |
| **P6 – Hardening & Pilot** | 14–18 | Security review, load test, on-prem package, pilot with 1 group + 3 subsidiaries |
| **P7 – Expand** | 18+ | ISSB/TCFD/CSRD packs, regional languages, L3 auto-discovery, DPDP tooling |

---

## 11. Evaluation & Acceptance

- **Retrieval**: recall@5 ≥ 0.9, MRR ≥ 0.8 on gold clause-lookup set.
- **Answer quality**: faithfulness ≥ 0.92 (RAGAS), citation precision ≥ 95%, SME acceptability ≥ 85% on 200-sample blind review.
- **Rules engine**: 100% pass on unit tests for each BRSR check; golden-file tests against real published BRSR reports.
- **Abstain test**: ≥ 90% correct abstention on out-of-corpus questions.
- **Latency/load**: targets in §3 under 200 concurrent users.
- **UX**: nudge acceptance rate tracked; false-positive nudge rate < 15%.
- **Regression gate**: no model/KB release without passing the full eval suite.

---

## 12. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Regulations change (BRSR amendments, new circulars) | Versioned KB, scheduled crawler (n8n) + human review, "last updated" shown in answers |
| Hallucinated numbers / false compliance claims | Numbers only from engine; mandatory citations; abstain policy; disclaimer: *assistive, not assurance/legal advice* |
| SLM too weak on reasoning | Retrieval + rerank + tool use; escalate hard queries to larger model **only if tenant opts in** |
| Form auto-discovery brittle | Prefer L1/L2; L3 requires human confirm |
| Data leakage between subsidiaries | RLS + per-tenant vector namespace + role-scoped retrieval + audit logs |
| Licence issues (model/data) | Licence register in RESOURCES.md; avoid redistributing copyrighted standards (GRI/SASB/ISSB text) — link + summarise, check usage terms |
| Greenwashing enabled by "suggest-fill" | Fill only from existing evidence; flag unverifiable claims; require evidence attach |
| Cost of GPU | 4-bit quant, batching, autoscale, CPU fallback for rules-only mode |

---

## 13. Open Questions (decide before P0 ends)
1. Which frameworks are **mandatory for pilot client** (BRSR only, or BRSR + GRI + CDP)?
2. SaaS vs on-prem for first big client?
3. Data residency (India-only)?
4. Do host apps allow markup changes (L2) or must we use L3?
5. Sector list for normalisation at launch (infra, power, irrigation, construction, etc.)?
6. Human-in-the-loop: do clients want ESG consultant review inside the product?
