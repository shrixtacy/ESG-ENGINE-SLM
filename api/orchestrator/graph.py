"""
ESGPilot — LangGraph Orchestrator.

Implements the agent graph per ARCHITECTURE.md §2.3:
  1. Context Builder → merges form/user context
  2. Intent Router → classifies user intent
  3. Rules Node → deterministic checks (always first for form events)
  4. Retrieve Node → hybrid RAG retrieval
  5. Tool Node → SQL analytics, EF lookup, SDG mapper
  6. Generate Node → SLM writes explanation/recommendation
  7. Guard Node → validates output (citations, numbers, PII)
  8. Respond Node → streams to client

Nudge path (fast): Rules → emit nudge → SLM elaboration only on click.
"""

import uuid
import json
from typing import Optional, TypedDict, Annotated, Any
from dataclasses import dataclass, field
from enum import Enum


class Intent(str, Enum):
    """User intent types from the intent router."""
    FIELD_HELP = "field_help"
    SECTION_REVIEW = "section_review"
    KB_QUESTION = "kb_question"
    COMPARE = "compare"
    NL_QUERY = "nl_query"
    SDG_MAP = "sdg_map"
    SMALLTALK = "smalltalk"
    NUDGE_ELABORATE = "nudge_elaborate"


@dataclass
class OrchestratorContext:
    """Full context for a request through the orchestrator."""
    # Request
    request_id: str = ""
    intent: Intent = Intent.KB_QUESTION
    user_message: str = ""

    # User context
    tenant_id: str = ""
    user_id: str = ""
    role: str = ""
    entity_id: Optional[str] = None
    project_id: Optional[str] = None

    # Form context
    form_id: Optional[str] = None
    framework: str = "BRSR"
    section: Optional[str] = None
    fy: str = "FY2025"
    field_values: dict = field(default_factory=dict)
    form_schema: Optional[dict] = None

    # Pipeline results
    rules_findings: list[dict] = field(default_factory=list)
    retrieved_chunks: list[dict] = field(default_factory=list)
    tool_results: Optional[dict] = None
    slm_response: str = ""
    guard_result: Optional[dict] = None
    final_response: Optional[dict] = None

    # Metadata
    model_version: str = ""
    kb_version: str = ""
    latency_ms: float = 0


class IntentRouter:
    """
    Classifies user intent based on message and context.
    Uses keyword matching for speed; can be replaced with a fine-tuned classifier.
    """

    FIELD_HELP_PATTERNS = [
        "what does this field", "what do i enter", "what goes in",
        "what unit", "how to fill", "what is the source", "explain this field",
        "help with field", "what does", "definition of",
    ]

    SECTION_REVIEW_PATTERNS = [
        "review", "check my", "validate", "completeness",
        "any issues", "anything missing", "section review",
        "readiness", "score",
    ]

    COMPARE_PATTERNS = [
        "compare", "vs", "versus", "ranking", "quartile",
        "best practice", "benchmark", "how do we rank",
        "subsidiaries", "projects comparison",
    ]

    NL_QUERY_PATTERNS = [
        "which subsidiaries", "which projects", "top 10",
        "highest", "lowest", "show me", "list all",
        "aggregate", "total across",
    ]

    SDG_PATTERNS = [
        "sdg", "sustainable development goal", "map to sdg",
        "which sdg", "sdg tag",
    ]

    SMALLTALK_PATTERNS = [
        "hello", "hi", "hey", "thanks", "thank you",
        "good morning", "who are you", "what can you do",
    ]

    def classify(
        self,
        message: str,
        has_form_context: bool = False,
        has_field_focus: bool = False,
    ) -> Intent:
        """Classify user intent."""
        msg_lower = message.lower().strip()

        # Check each category
        if any(p in msg_lower for p in self.SMALLTALK_PATTERNS):
            return Intent.SMALLTALK

        if any(p in msg_lower for p in self.SDG_PATTERNS):
            return Intent.SDG_MAP

        if any(p in msg_lower for p in self.NL_QUERY_PATTERNS):
            return Intent.NL_QUERY

        if any(p in msg_lower for p in self.COMPARE_PATTERNS):
            return Intent.COMPARE

        if any(p in msg_lower for p in self.SECTION_REVIEW_PATTERNS):
            return Intent.SECTION_REVIEW

        if has_field_focus or any(p in msg_lower for p in self.FIELD_HELP_PATTERNS):
            return Intent.FIELD_HELP

        # Default to knowledge Q&A
        return Intent.KB_QUESTION


class Orchestrator:
    """
    LangGraph-style orchestrator that processes requests through
    the agent graph pipeline.
    """

    def __init__(
        self,
        rules_engine=None,
        retrieval_service=None,
        inference_service=None,
        guardrails=None,
    ):
        self.rules_engine = rules_engine
        self.retrieval = retrieval_service
        self.inference = inference_service
        self.guardrails = guardrails
        self.router = IntentRouter()

    async def process(self, ctx: OrchestratorContext) -> OrchestratorContext:
        """
        Process a request through the full pipeline.

        Graph: context_build → intent_route → rules → retrieve → generate → guard → respond
        """
        import time
        start = time.time()

        # Generate request ID
        ctx.request_id = uuid.uuid4().hex[:12]

        # 1. Intent routing
        ctx.intent = self.router.classify(
            ctx.user_message,
            has_form_context=bool(ctx.form_id),
            has_field_focus=bool(ctx.section),
        )

        # 2. Execute based on intent
        if ctx.intent == Intent.SMALLTALK:
            ctx = await self._handle_smalltalk(ctx)
        elif ctx.intent == Intent.FIELD_HELP:
            ctx = await self._handle_field_help(ctx)
        elif ctx.intent == Intent.SECTION_REVIEW:
            ctx = await self._handle_section_review(ctx)
        elif ctx.intent == Intent.KB_QUESTION:
            ctx = await self._handle_kb_question(ctx)
        elif ctx.intent == Intent.COMPARE:
            ctx = await self._handle_compare(ctx)
        elif ctx.intent == Intent.NL_QUERY:
            ctx = await self._handle_nl_query(ctx)
        elif ctx.intent == Intent.SDG_MAP:
            ctx = await self._handle_sdg_map(ctx)
        elif ctx.intent == Intent.NUDGE_ELABORATE:
            ctx = await self._handle_nudge_elaborate(ctx)

        ctx.latency_ms = (time.time() - start) * 1000
        return ctx

    async def process_nudge(self, ctx: OrchestratorContext) -> dict:
        """
        Fast nudge path: Rules only → emit nudge immediately.
        SLM elaboration happens later if user clicks "Yes".
        """
        if not self.rules_engine:
            return {"has_findings": False, "count": 0, "top_severity": "info"}

        findings = self.rules_engine.run_all_checks(
            field_values=ctx.field_values,
            section=ctx.section,
        )

        if not findings:
            return {"has_findings": False, "count": 0, "top_severity": "info"}

        # Determine top severity
        severities = [f.severity.value for f in findings]
        if "critical" in severities:
            top = "critical"
        elif "warn" in severities:
            top = "warn"
        else:
            top = "info"

        # Store findings for later elaboration
        ctx.rules_findings = [
            {
                "rule_id": f.rule_id,
                "type": f.finding_type.value,
                "severity": f.severity.value,
                "field_code": f.field_code,
                "title": f.title,
                "detail": f.detail,
                "expected": f.expected,
                "actual": f.actual,
            }
            for f in findings
        ]

        return {
            "has_findings": True,
            "count": len(findings),
            "top_severity": top,
            "summary": f"{len(findings)} issue(s) found in this section.",
        }

    async def _handle_smalltalk(self, ctx: OrchestratorContext) -> OrchestratorContext:
        ctx.slm_response = (
            "Hello! I'm ESGPilot, your ESG reporting assistant. I can help you with:\n\n"
            "• **Form help** — explain what each field means and how to fill it\n"
            "• **Compliance Q&A** — answer doubts about BRSR, SDGs, and regulations with citations\n"
            "• **Section review** — check completeness and consistency of your entries\n"
            "• **Comparisons** — compare subsidiaries, projects, or track year-over-year changes\n"
            "• **SDG mapping** — map activities to UN SDG goals and targets\n\n"
            "How can I help you today?"
        )
        ctx.final_response = {"answer": ctx.slm_response, "intent": "smalltalk"}
        return ctx

    async def _handle_field_help(self, ctx: OrchestratorContext) -> OrchestratorContext:
        """Retrieve KB info about a specific field and explain it."""
        # Retrieve relevant knowledge
        if self.retrieval:
            chunks = self.retrieval.retrieve(
                query=ctx.user_message,
                tenant_id=ctx.tenant_id,
                framework=ctx.framework,
            )
            ctx.retrieved_chunks = [
                {
                    "text": c.text,
                    "doc_title": c.metadata.doc_title,
                    "section_path": c.metadata.section_path,
                    "version": c.metadata.version,
                    "url": c.metadata.url,
                }
                for c in chunks
            ]

        # Generate explanation
        if self.inference:
            ctx.slm_response = await self.inference.generate(
                user_message=ctx.user_message,
                adapter="kb_qa",
                context_chunks=ctx.retrieved_chunks,
                form_context={
                    "framework": ctx.framework,
                    "section": ctx.section,
                    "fy": ctx.fy,
                },
            )

        # Guard
        if self.guardrails:
            result = self.guardrails.check_all(
                output=ctx.slm_response,
                evidence_chunks=ctx.retrieved_chunks,
                input_text=ctx.user_message,
            )
            ctx.guard_result = {
                "passed": result.passed,
                "violations": result.violations,
                "action": result.action,
            }
            if result.sanitised_output:
                ctx.slm_response = result.sanitised_output

        ctx.final_response = {
            "answer": ctx.slm_response,
            "citations": [
                {
                    "doc_title": c.get("doc_title"),
                    "section": c.get("section_path"),
                    "version": c.get("version"),
                    "url": c.get("url"),
                }
                for c in ctx.retrieved_chunks
            ],
            "intent": "field_help",
        }
        return ctx

    async def _handle_section_review(self, ctx: OrchestratorContext) -> OrchestratorContext:
        """Run rules + SLM review on a section."""
        # 1. Rules first (deterministic)
        if self.rules_engine:
            findings = self.rules_engine.run_all_checks(
                field_values=ctx.field_values,
                section=ctx.section,
            )
            ctx.rules_findings = [
                {
                    "rule_id": f.rule_id,
                    "type": f.finding_type.value,
                    "severity": f.severity.value,
                    "field_code": f.field_code,
                    "title": f.title,
                    "detail": f.detail,
                }
                for f in findings
            ]

            # Readiness score
            readiness = self.rules_engine.compute_readiness_score(
                ctx.field_values, ctx.framework
            )
        else:
            readiness = None

        # 2. SLM elaboration
        if self.inference and ctx.rules_findings:
            ctx.slm_response = await self.inference.generate(
                user_message="Please review these findings and provide a summary with recommendations.",
                adapter="reviewer",
                rules_findings=ctx.rules_findings,
                form_context={
                    "framework": ctx.framework,
                    "section": ctx.section,
                    "fy": ctx.fy,
                    "field_values": ctx.field_values,
                },
            )

        ctx.final_response = {
            "suggestions": ctx.rules_findings,
            "readiness": readiness,
            "narrative": ctx.slm_response,
            "intent": "section_review",
        }
        return ctx

    async def _handle_kb_question(self, ctx: OrchestratorContext) -> OrchestratorContext:
        """Answer a compliance/knowledge question with citations."""
        # Retrieve
        if self.retrieval:
            try:
                chunks = self.retrieval.retrieve(
                    query=ctx.user_message,
                    tenant_id=ctx.tenant_id,
                    framework=ctx.framework,
                )
                ctx.retrieved_chunks = [
                    {
                        "text": c.text,
                        "doc_title": c.metadata.doc_title,
                        "section_path": c.metadata.section_path,
                        "version": c.metadata.version,
                        "url": c.metadata.url,
                    }
                    for c in chunks
                ]
            except Exception:
                pass

        # Generate
        if self.inference:
            try:
                ctx.slm_response = await self.inference.generate(
                    user_message=ctx.user_message,
                    adapter="kb_qa",
                    context_chunks=ctx.retrieved_chunks,
                    form_context={
                        "framework": ctx.framework,
                        "fy": ctx.fy,
                    } if ctx.framework else None,
                )
            except Exception:
                ctx.slm_response = self._demo_answer(ctx.user_message)
        else:
            ctx.slm_response = self._demo_answer(ctx.user_message)

        # Guard
        if self.guardrails and ctx.retrieved_chunks:
            try:
                result = self.guardrails.check_all(
                    output=ctx.slm_response,
                    evidence_chunks=ctx.retrieved_chunks,
                    input_text=ctx.user_message,
                )
                ctx.guard_result = {
                    "passed": result.passed,
                    "violations": result.violations,
                }
                if result.sanitised_output:
                    ctx.slm_response = result.sanitised_output

                ctx.slm_response = self.guardrails.add_disclaimer(
                    ctx.slm_response, is_compliance_critical=True
                )
            except Exception:
                pass

        abstained = any(
            phrase in ctx.slm_response.lower()
            for phrase in [
                "i don't have", "not in my sources",
                "insufficient", "cannot answer",
                "don't have enough information",
            ]
        )

        ctx.final_response = {
            "answer": ctx.slm_response,
            "citations": [
                {
                    "doc_title": c.get("doc_title"),
                    "section": c.get("section_path"),
                    "version": c.get("version"),
                    "url": c.get("url"),
                    "excerpt": c.get("text", "")[:200],
                }
                for c in ctx.retrieved_chunks
            ],
            "confidence": 0.0 if abstained else 0.85,
            "abstained": abstained,
            "intent": "kb_question",
        }
        return ctx

    @staticmethod
    def _demo_answer(question: str) -> str:
        """Return a helpful demo answer when no LLM is available."""
        q = question.lower()

        if any(k in q for k in ["scope 1", "scope1"]):
            return (
                "**Scope 1 GHG Emissions** are direct greenhouse gas emissions from sources owned or "
                "controlled by the organisation — such as fuel combustion in boilers, generators, "
                "company vehicles, and process emissions.\n\n"
                "**Unit**: Report in tCO2e (metric tonnes of CO2 equivalent) using IPCC AR5 GWP values.\n\n"
                "**Source**: BRSR Annexure I, Principle 6, Essential Indicator 7a | GRI 305-1 | GHG Protocol Corporate Standard Ch.4\n\n"
                "To calculate: multiply fuel consumption (e.g., kL of diesel) by the relevant IPCC 2006 emission factor."
            )
        elif any(k in q for k in ["scope 2", "scope2", "electricity"]):
            return (
                "**Scope 2 GHG Emissions** are indirect emissions from the generation of purchased electricity, "
                "heat, or steam consumed by the organisation.\n\n"
                "**India grid emission factor (FY2024)**: 0.71 tCO2e/MWh (CEA CO2 Baseline Database v18, 2023).\n\n"
                "Formula: Electricity consumed (MWh) × 0.71 = tCO2e\n\n"
                "**Source**: BRSR Annexure I, P6 EI-7b | GRI 305-2 | CEA CO2 Baseline Database v18"
            )
        elif any(k in q for k in ["brsr", "mandatory", "listed"]):
            return (
                "**BRSR (Business Responsibility and Sustainability Reporting)** is mandatory for the "
                "**top 1,000 listed entities** by market capitalisation from **FY 2022–23** onwards.\n\n"
                "From FY 2023–24, these entities must also provide **BRSR Core KPIs** with "
                "**reasonable assurance** from an accredited third-party assurer.\n\n"
                "For companies outside the top 1,000, BRSR disclosure is voluntary.\n\n"
                "**Source**: SEBI Circular SEBI/HO/CFD/CMD-2/CIR/P/2021/562 (May 2021) | "
                "SEBI BRSR Core Circular (July 2023)"
            )
        elif any(k in q for k in ["csr", "135", "obligation"]):
            return (
                "Under **Section 135 of the Companies Act 2013**, eligible companies must spend "
                "at least **2% of average net profits** of the preceding three financial years on CSR.\n\n"
                "**Eligibility** (any one): Net worth ≥ ₹500 cr | Turnover ≥ ₹1,000 cr | Net profit ≥ ₹5 cr\n\n"
                "Unspent amounts must be transferred to a dedicated Unspent CSR Account within 30 days of FY end.\n\n"
                "**Source**: Companies Act 2013, Section 135 | Companies (CSR Policy) Rules 2014"
            )
        elif any(k in q for k in ["water", "withdrawal", "kl", "kilolitre"]):
            return (
                "**Water Withdrawal** in BRSR (P6 EI-9) covers all water drawn from any source:\n"
                "groundwater, surface water, rainwater harvesting, municipal supply, and tanker water.\n\n"
                "**Unit**: Kilolitres (KL). 1 KL = 1 m³ = 1,000 litres.\n\n"
                "Key check: **Water balance** — Withdrawal = Consumption + Discharge. "
                "The rules engine validates this automatically.\n\n"
                "**Source**: BRSR Annexure I, P6 EI-9 | GRI 303-3 | SDG 6.4"
            )
        elif any(k in q for k in ["sdg", "sustainable development"]):
            return (
                "The **UN Sustainable Development Goals (SDGs)** are 17 global goals adopted in 2015 "
                "as part of the 2030 Agenda for Sustainable Development.\n\n"
                "**Key SDGs for ESG reporting**:\n"
                "• SDG 7 — Affordable and Clean Energy\n"
                "• SDG 8 — Decent Work and Economic Growth\n"
                "• SDG 12 — Responsible Consumption and Production\n"
                "• SDG 13 — Climate Action\n"
                "• SDG 6 — Clean Water and Sanitation\n\n"
                "BRSR encourages mapping your disclosures to relevant SDG goals and targets.\n\n"
                "**Source**: UN 2030 Agenda | Global SDG Indicator Framework 2023"
            )
        elif any(k in q for k in ["improve", "score", "readiness", "suggest"]):
            return (
                "**Top ways to improve your BRSR readiness score**:\n\n"
                "1. **Fill all mandatory fields** — completeness accounts for 45% of the readiness score\n"
                "2. **Attach evidence** — upload meter readings, bills, calculations for GHG/energy/water fields\n"
                "3. **Fix arithmetic errors** — ensure Scope 1 + Scope 2 = Total; energy totals match\n"
                "4. **Add quantitative detail** to narrative fields — replace vague statements with numbers\n"
                "5. **State boundaries** — clarify which plants/sites each disclosure covers\n"
                "6. **Map to SDGs** — tag your initiatives to relevant SDG goals\n\n"
                "The rules engine checks all of these automatically as you fill the form."
            )
        else:
            return (
                f"I understand you're asking about: **{question}**\n\n"
                "I'm running in demo mode (no LLM connected). To get full AI-powered answers with citations, "
                "start Ollama and pull a model:\n\n"
                "```\nollama pull qwen2.5:7b-instruct\n```\n\n"
                "Then set `OLLAMA_BASE_URL=http://localhost:11434` in your `.env` file.\n\n"
                "In the meantime, I can answer questions about:\n"
                "• BRSR mandatory requirements\n"
                "• Scope 1 / Scope 2 / Scope 3 emissions\n"
                "• Water, waste, and energy metrics\n"
                "• CSR obligations under Companies Act\n"
                "• UN SDG mapping"
            )

    async def _handle_compare(self, ctx: OrchestratorContext) -> OrchestratorContext:
        """Handle portfolio comparison requests."""
        if self.inference:
            ctx.slm_response = await self.inference.generate(
                user_message=ctx.user_message,
                adapter="base",
                form_context={
                    "framework": ctx.framework,
                    "fy": ctx.fy,
                    "role": ctx.role,
                },
                json_mode=True,
            )

        ctx.final_response = {
            "query_plan": ctx.slm_response,
            "intent": "compare",
        }
        return ctx

    async def _handle_nl_query(self, ctx: OrchestratorContext) -> OrchestratorContext:
        """Handle natural language queries (NL→SQL)."""
        if self.inference:
            ctx.slm_response = await self.inference.generate(
                user_message=(
                    f"Convert this natural language query to a query plan JSON:\n"
                    f"Query: {ctx.user_message}\n"
                    f"Available metrics: scope1, scope2, energy_intensity, water_intensity, "
                    f"ghg_intensity, waste_generated, csr_expenditure, training_hours, "
                    f"safety_incidents, fatalities\n"
                    f"Available dimensions: entity, project, fy\n"
                    f"Output format: {{\"metric\": \"...\", \"dimensions\": [...], \"filters\": {{}}, \"top_n\": N}}"
                ),
                adapter="base",
                json_mode=True,
            )

        ctx.final_response = {
            "query_plan": ctx.slm_response,
            "intent": "nl_query",
        }
        return ctx

    async def _handle_sdg_map(self, ctx: OrchestratorContext) -> OrchestratorContext:
        """Map text to SDG goals/targets."""
        if self.retrieval:
            chunks = self.retrieval.retrieve(
                query=f"SDG mapping: {ctx.user_message}",
                framework="SDG",
            )
            ctx.retrieved_chunks = [
                {
                    "text": c.text,
                    "doc_title": c.metadata.doc_title,
                    "section_path": c.metadata.section_path,
                }
                for c in chunks
            ]

        if self.inference:
            ctx.slm_response = await self.inference.generate(
                user_message=ctx.user_message,
                adapter="sdg_tagger",
                context_chunks=ctx.retrieved_chunks,
                json_mode=True,
            )

        ctx.final_response = {
            "tags": ctx.slm_response,
            "intent": "sdg_map",
        }
        return ctx

    async def _handle_nudge_elaborate(self, ctx: OrchestratorContext) -> OrchestratorContext:
        """Elaborate on rules findings when user clicks 'Yes' on nudge."""
        # Retrieve context for findings
        if self.retrieval and ctx.rules_findings:
            field_codes = [f["field_code"] for f in ctx.rules_findings[:5]]
            query = f"BRSR guidance for fields: {', '.join(field_codes)}"
            chunks = self.retrieval.retrieve(
                query=query,
                tenant_id=ctx.tenant_id,
                framework=ctx.framework,
            )
            ctx.retrieved_chunks = [
                {
                    "text": c.text,
                    "doc_title": c.metadata.doc_title,
                    "section_path": c.metadata.section_path,
                    "version": c.metadata.version,
                }
                for c in chunks
            ]

        # SLM elaboration
        if self.inference:
            ctx.slm_response = await self.inference.generate(
                user_message=(
                    "Please elaborate on these findings. For each, explain WHY it matters "
                    "and HOW to fix it, with specific references."
                ),
                adapter="reviewer",
                rules_findings=ctx.rules_findings,
                context_chunks=ctx.retrieved_chunks,
                form_context={
                    "framework": ctx.framework,
                    "section": ctx.section,
                },
            )

        ctx.final_response = {
            "suggestions": ctx.rules_findings,
            "elaboration": ctx.slm_response,
            "citations": [
                {
                    "doc_title": c.get("doc_title"),
                    "section": c.get("section_path"),
                    "version": c.get("version"),
                }
                for c in ctx.retrieved_chunks
            ],
            "intent": "nudge_elaborate",
        }
        return ctx
