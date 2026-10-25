"""
ESGPilot — SLM Inference Service.

Manages communication with the SLM (vLLM/Ollama).
Handles system prompts, structured JSON output, streaming, and adapter selection.
"""

import json
from typing import Optional, AsyncGenerator

import httpx
from api.core.config import get_settings

settings = get_settings()


# ──────────────────────────────────────────────
# System Prompts
# ──────────────────────────────────────────────

SYSTEM_PROMPT_BASE = """You are ESGPilot, an expert ESG (Environmental, Social, and Governance) reporting assistant specialising in Indian regulatory frameworks (BRSR, NGRBC, Companies Act s.135) and global standards (GRI, UN SDGs, GHG Protocol).

## Core Rules
1. **NEVER invent numbers.** All numeric values come from the rules engine or the user's data. You only EXPLAIN numbers provided to you.
2. **ALWAYS cite sources.** Every claim must reference a specific document, section/clause, and version. If you cannot cite, say "I don't have a source for this."
3. **Abstain when uncertain.** If retrieved evidence is insufficient, say "I don't have enough information to answer this accurately" rather than guessing.
4. **Be practical, not academic.** Focus on HOW to fill forms correctly, not generic ESG lectures.
5. **Respect data boundaries.** Only reference data you've been given. Never speculate about other entities' data.
6. **No legal advice.** Add disclaimer for compliance-critical answers: "This is informational guidance, not legal or assurance advice."

## Output Format
When generating recommendations, use this JSON structure:
{
  "id": "rec_<short_id>",
  "scope": "field|section|form|portfolio",
  "severity": "info|warn|critical",
  "title": "Brief finding title",
  "why": "Explanation of why this matters",
  "how_to_fix": "Specific, actionable guidance",
  "references": [{"doc": "...", "section": "...", "version": "..."}],
  "sdg_tags": ["13.2"],
  "confidence": 0.85,
  "source": "slm|hybrid"
}

## Context
You will receive:
- Form data (field values, units, sections)
- Retrieved knowledge base chunks with citations
- Rules engine findings (numeric checks already done)
- User role and hierarchy context

Your job is to EXPLAIN the findings, ANSWER questions with citations, and RECOMMEND improvements.
"""

SYSTEM_PROMPT_REVIEWER = SYSTEM_PROMPT_BASE + """
## Reviewer Mode
You are reviewing ESG disclosures for quality. Focus on:
- Is the disclosure specific and measurable?
- Does it state time boundaries and scope?
- Is quantitative evidence provided?
- Does it match the framework requirements?
"""

SYSTEM_PROMPT_KB_QA = SYSTEM_PROMPT_BASE + """
## Knowledge Q&A Mode
Answer the user's question using ONLY the provided knowledge base chunks.
Always include citation chips: [doc_title | section | version].
If the answer is not in the provided chunks, say so explicitly.
"""

SYSTEM_PROMPT_SDG_TAGGER = SYSTEM_PROMPT_BASE + """
## SDG Tagging Mode
Map the provided text/activity to UN SDG goals and targets.
Provide rationale for each mapping.
Output as JSON array of {"goal": <int>, "target": "<target_id>", "confidence": <0-1>, "rationale": "..."}.
"""

ADAPTERS = {
    "reviewer": SYSTEM_PROMPT_REVIEWER,
    "kb_qa": SYSTEM_PROMPT_KB_QA,
    "sdg_tagger": SYSTEM_PROMPT_SDG_TAGGER,
    "base": SYSTEM_PROMPT_BASE,
}


class InferenceService:
    """
    Manages SLM inference via vLLM (GPU) or Ollama (dev/CPU).
    """

    def __init__(self, backend: str = "ollama"):
        """
        Args:
            backend: "vllm" for production GPU, "ollama" for dev/CPU
        """
        self.backend = backend
        if backend == "vllm":
            self.base_url = settings.vllm_base_url
        else:
            self.base_url = settings.ollama_base_url
        self.model = settings.model_name

    async def generate(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        adapter: str = "base",
        context_chunks: Optional[list[dict]] = None,
        rules_findings: Optional[list[dict]] = None,
        form_context: Optional[dict] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> str:
        """
        Generate a response from the SLM.
        """
        if not system_prompt:
            system_prompt = ADAPTERS.get(adapter, SYSTEM_PROMPT_BASE)

        # Build context block
        context_parts = []
        if form_context:
            context_parts.append(f"## Form Context\n```json\n{json.dumps(form_context, indent=2)}\n```")

        if rules_findings:
            context_parts.append(f"## Rules Engine Findings\n```json\n{json.dumps(rules_findings, indent=2)}\n```")

        if context_chunks:
            chunks_text = "\n\n".join([
                f"### Source {i+1}: {c.get('doc_title', 'Unknown')} | {c.get('section_path', '')} | {c.get('version', '')}\n{c.get('text', '')}"
                for i, c in enumerate(context_chunks)
            ])
            context_parts.append(f"## Retrieved Knowledge Base\n{chunks_text}")

        full_user_message = user_message
        if context_parts:
            full_user_message = "\n\n".join(context_parts) + f"\n\n## User Question\n{user_message}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": full_user_message},
        ]

        if self.backend == "vllm":
            return await self._generate_vllm(messages, temperature, max_tokens, json_mode)
        else:
            return await self._generate_ollama(messages, temperature, max_tokens, json_mode)

    async def generate_stream(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        adapter: str = "base",
        context_chunks: Optional[list[dict]] = None,
        rules_findings: Optional[list[dict]] = None,
        form_context: Optional[dict] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens."""
        if not system_prompt:
            system_prompt = ADAPTERS.get(adapter, SYSTEM_PROMPT_BASE)

        context_parts = []
        if form_context:
            context_parts.append(f"## Form Context\n```json\n{json.dumps(form_context, indent=2)}\n```")
        if rules_findings:
            context_parts.append(f"## Rules Engine Findings\n```json\n{json.dumps(rules_findings, indent=2)}\n```")
        if context_chunks:
            chunks_text = "\n\n".join([
                f"### Source {i+1}: {c.get('doc_title', 'Unknown')} | {c.get('section_path', '')} | {c.get('version', '')}\n{c.get('text', '')}"
                for i, c in enumerate(context_chunks)
            ])
            context_parts.append(f"## Retrieved Knowledge Base\n{chunks_text}")

        full_user_message = user_message
        if context_parts:
            full_user_message = "\n\n".join(context_parts) + f"\n\n## User Question\n{user_message}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": full_user_message},
        ]

        if self.backend == "vllm":
            async for token in self._stream_vllm(messages, temperature, max_tokens):
                yield token
        else:
            async for token in self._stream_ollama(messages, temperature, max_tokens):
                yield token

    async def _generate_vllm(
        self, messages: list, temperature: float, max_tokens: int, json_mode: bool
    ) -> str:
        """Call vLLM OpenAI-compatible endpoint."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def _generate_ollama(
        self, messages: list, temperature: float, max_tokens: int, json_mode: bool
    ) -> str:
        """Call Ollama API."""
        payload = {
            "model": self.model,
            "messages": messages,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "stream": False,
        }
        if json_mode:
            payload["format"] = "json"

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "")

    async def _stream_vllm(
        self, messages: list, temperature: float, max_tokens: int
    ) -> AsyncGenerator[str, None]:
        """Stream from vLLM."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST", f"{self.base_url}/chat/completions", json=payload
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue

    async def _stream_ollama(
        self, messages: list, temperature: float, max_tokens: int
    ) -> AsyncGenerator[str, None]:
        """Stream from Ollama."""
        payload = {
            "model": self.model,
            "messages": messages,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST", f"{self.base_url}/api/chat", json=payload
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
