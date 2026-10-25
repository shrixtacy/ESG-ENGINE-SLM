"""
ESGPilot — Guardrails Module.

Implements safety checks per ARCHITECTURE.md §2.7:
  1. Cite-or-abstain: every claim must reference a retrieved chunk or rule
  2. No-number policy: numbers in output must exist in evidence
  3. Scope policy: only ESG/reporting topics
  4. PII filter
  5. Prompt-injection defence
"""

import re
import json
from typing import Optional
from dataclasses import dataclass


@dataclass
class GuardResult:
    """Result of guardrail checks."""
    passed: bool
    violations: list[str]
    sanitised_output: Optional[str] = None
    action: str = "pass"  # pass | warn | block | regenerate


class Guardrails:
    """Post-generation guardrails for SLM output."""

    # PII patterns
    PII_PATTERNS = [
        (r"\b\d{12}\b", "Aadhaar number"),
        (r"\b[A-Z]{5}\d{4}[A-Z]\b", "PAN number"),
        (r"\b\d{2}/\d{2}/\d{4}\b.*birth", "Date of birth"),
        (r"\b[\w.+-]+@[\w-]+\.[\w.]+\b", "Email address"),
        (r"\b\d{10}\b", "Phone number"),
        (r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "Card number"),
    ]

    # Out-of-scope topics
    OUT_OF_SCOPE = [
        "legal advice", "legal opinion", "assurance statement",
        "audit opinion", "investment advice", "stock recommendation",
        "medical advice", "personal advice",
    ]

    # Prompt injection patterns
    INJECTION_PATTERNS = [
        r"ignore\s+(previous|above|all)\s+(instructions|prompts|rules)",
        r"forget\s+(your|all)\s+(instructions|rules|training)",
        r"you\s+are\s+now\s+",
        r"new\s+instructions?\s*:",
        r"system\s*prompt\s*:",
        r"act\s+as\s+(?:if|though)\s+you",
        r"pretend\s+(?:you|to)\s+",
        r"disregard\s+",
        r"override\s+",
    ]

    def __init__(self):
        self._injection_re = re.compile(
            "|".join(self.INJECTION_PATTERNS), re.IGNORECASE
        )

    def check_all(
        self,
        output: str,
        evidence_chunks: list[dict] = None,
        rules_findings: list[dict] = None,
        input_text: str = None,
    ) -> GuardResult:
        """Run all guardrail checks on model output."""
        violations = []

        # 1. Check input for injection
        if input_text:
            injection_result = self.check_injection(input_text)
            if not injection_result.passed:
                return GuardResult(
                    passed=False,
                    violations=injection_result.violations,
                    action="block",
                )

        # 2. Scope check
        scope_result = self.check_scope(output)
        violations.extend(scope_result.violations)

        # 3. Number check
        if evidence_chunks or rules_findings:
            number_result = self.check_numbers(output, evidence_chunks, rules_findings)
            violations.extend(number_result.violations)

        # 4. PII check
        pii_result = self.check_pii(output)
        violations.extend(pii_result.violations)
        if pii_result.sanitised_output:
            output = pii_result.sanitised_output

        # 5. Citation check
        if evidence_chunks:
            citation_result = self.check_citations(output, evidence_chunks)
            violations.extend(citation_result.violations)

        # Determine action
        if any("BLOCK" in v for v in violations):
            action = "block"
        elif any("REGENERATE" in v for v in violations):
            action = "regenerate"
        elif violations:
            action = "warn"
        else:
            action = "pass"

        return GuardResult(
            passed=len(violations) == 0,
            violations=violations,
            sanitised_output=output,
            action=action,
        )

    def check_injection(self, text: str) -> GuardResult:
        """Check input for prompt injection attempts."""
        violations = []
        if self._injection_re.search(text):
            violations.append(
                "[BLOCK] Prompt injection detected in input. "
                "Form values and uploaded content are treated as data, not instructions."
            )
        return GuardResult(passed=len(violations) == 0, violations=violations)

    def check_scope(self, output: str) -> GuardResult:
        """Check if output stays within ESG/reporting scope."""
        violations = []
        output_lower = output.lower()

        for topic in self.OUT_OF_SCOPE:
            if topic in output_lower:
                # Check if it's a refusal (good) or providing (bad)
                if not any(
                    phrase in output_lower
                    for phrase in ["cannot provide", "not qualified", "i don't provide", "seek professional"]
                ):
                    violations.append(
                        f"[WARN] Output may contain {topic}. "
                        f"ESGPilot should not provide {topic}."
                    )

        return GuardResult(passed=len(violations) == 0, violations=violations)

    def check_numbers(
        self,
        output: str,
        evidence_chunks: list[dict] = None,
        rules_findings: list[dict] = None,
    ) -> GuardResult:
        """
        No-number policy: any number in output must exist in evidence.
        Numbers should come from rules engine or user data, not the SLM.
        """
        violations = []

        # Extract numbers from output
        output_numbers = set(re.findall(r"\b\d+\.?\d*\b", output))

        # Extract numbers from evidence
        evidence_numbers = set()
        if evidence_chunks:
            for chunk in evidence_chunks:
                text = chunk.get("text", "")
                evidence_numbers.update(re.findall(r"\b\d+\.?\d*\b", text))

        if rules_findings:
            findings_text = json.dumps(rules_findings)
            evidence_numbers.update(re.findall(r"\b\d+\.?\d*\b", findings_text))

        # Allow common numbers (years, small integers, percentages)
        common_numbers = {str(i) for i in range(0, 100)} | {"100", "1000"}
        year_pattern = re.compile(r"^(19|20)\d{2}$")

        hallucinated = []
        for num in output_numbers:
            if num in common_numbers:
                continue
            if year_pattern.match(num):
                continue
            if num not in evidence_numbers:
                hallucinated.append(num)

        if hallucinated:
            violations.append(
                f"[REGENERATE] Numbers not found in evidence: {hallucinated[:5]}. "
                f"The SLM must not generate numbers not present in rules findings or retrieved data."
            )

        return GuardResult(passed=len(violations) == 0, violations=violations)

    def check_pii(self, text: str) -> GuardResult:
        """Check and redact PII from output."""
        violations = []
        sanitised = text

        for pattern, label in self.PII_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                violations.append(f"[WARN] Potential {label} found in output — redacted.")
                sanitised = re.sub(pattern, f"[REDACTED-{label.upper()}]", sanitised, flags=re.IGNORECASE)

        return GuardResult(
            passed=len(violations) == 0,
            violations=violations,
            sanitised_output=sanitised if violations else None,
        )

    def check_citations(
        self,
        output: str,
        evidence_chunks: list[dict],
    ) -> GuardResult:
        """
        Cite-or-abstain: verify the output references actual retrieved chunks.
        Checks that doc titles or section references from evidence appear in output.
        """
        violations = []

        # If output contains factual claims, it should reference sources
        # Simple heuristic: look for assertion patterns without citations
        assertion_patterns = [
            r"(?:requires|mandates|stipulates|states that|according to)\s+",
            r"(?:as per|under|per)\s+(?:regulation|section|clause|rule)\s+",
        ]

        has_assertions = any(re.search(p, output, re.IGNORECASE) for p in assertion_patterns)

        if has_assertions:
            # Check if any evidence doc titles appear in output
            doc_titles = [c.get("doc_title", "") for c in evidence_chunks if c.get("doc_title")]
            sections = [c.get("section_path", "") for c in evidence_chunks if c.get("section_path")]

            referenced = False
            for title in doc_titles:
                if title and title.lower() in output.lower():
                    referenced = True
                    break
            if not referenced:
                for section in sections:
                    if section and section in output:
                        referenced = True
                        break

            if not referenced and doc_titles:
                violations.append(
                    "[WARN] Output makes factual claims but does not reference "
                    "any retrieved source documents. Consider adding citations."
                )

        return GuardResult(passed=len(violations) == 0, violations=violations)

    def add_disclaimer(self, output: str, is_compliance_critical: bool = False) -> str:
        """Add soft disclaimer for compliance-critical answers."""
        if is_compliance_critical:
            disclaimer = (
                "\n\n---\n*⚠️ This is informational guidance based on regulatory documents in our knowledge base. "
                "It does not constitute legal advice, assurance, or audit opinion. "
                "Please consult a qualified professional for compliance decisions.*"
            )
            return output + disclaimer
        return output
