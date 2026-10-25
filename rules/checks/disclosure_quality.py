"""
ESGPilot — Disclosure Quality Checks.

Evaluates narrative/text ESG disclosures for:
  - Specificity (measurable claims vs vague language)
  - Time-boundedness (year/period stated)
  - Boundary clarity (scope/entity defined)
  - Quantitative evidence (numbers present)
  - Action orientation (concrete commitments)

These checks fire on text/textarea fields in BRSR forms.
Score: 0–1 per dimension, overall quality tier: poor/fair/good/excellent.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class QualityDimension:
    """Single dimension of disclosure quality."""
    name: str
    score: float  # 0-1
    passed: bool
    feedback: str
    examples: list[str] = field(default_factory=list)


@dataclass
class DisclosureQualityResult:
    """Full quality assessment of a narrative disclosure."""
    field_code: str
    text: str
    overall_score: float           # 0-1
    quality_tier: str              # poor | fair | good | excellent
    dimensions: list[QualityDimension] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    word_count: int = 0


# ──────────────────────────────────────────────
# Pattern Libraries
# ──────────────────────────────────────────────

# Vague / boilerplate phrases that signal poor quality
VAGUE_PHRASES = [
    r"\bwe\s+are\s+committed\s+to\b",
    r"\bwe\s+strive\s+to\b",
    r"\bwe\s+endeavour\s+to\b",
    r"\bbest\s+efforts?\b",
    r"\bvarious\s+initiatives?\b",
    r"\bnumerous\s+steps?\b",
    r"\bin\s+due\s+course\b",
    r"\bas\s+applicable\b",
    r"\bwhere\s+feasible\b",
    r"\bwe\s+believe\b",
    r"\bsignificant\s+progress\b",
    r"\brobust\s+framework\b",
    r"\bholistic\s+approach\b",
    r"\bseamlessly\b",
]

# Time-bound indicators
TIME_PATTERNS = [
    r"\bFY\s*\d{2,4}\b",
    r"\b20\d{2}[-–]\d{2,4}\b",
    r"\bby\s+20\d{2}\b",
    r"\bby\s+(?:March|April|December|end\s+of)\s+20\d{2}\b",
    r"\bwithin\s+\d+\s+(?:years?|months?)\b",
    r"\bQ[1-4]\s+20\d{2}\b",
    r"\bbaseline\s+year\b",
    r"\btarget\s+year\b",
    r"\b(?:annual|yearly|quarterly)\b",
]

# Quantitative indicators — numbers with optional units
QUANTITATIVE_PATTERNS = [
    r"\b\d+\.?\d*\s*(?:%|percent|tCO2e?|MT|GJ|kWh|MWh|kL|m[²³]|crore|lakh|INR|MW|km)\b",
    r"\b\d+\.?\d*\s*(?:metric\s+ton|tonne|kilolitre|megawatt|gigajoule)\b",
    r"\b\d+\s*(?:employees?|workers?|plants?|sites?|units?)\b",
    r"\bincreased?\s+by\s+\d+",
    r"\bdecreased?\s+by\s+\d+",
    r"\breduced?\s+by\s+\d+",
    r"\bimproved?\s+by\s+\d+",
]

# Boundary/scope indicators
BOUNDARY_PATTERNS = [
    r"\b(?:all\s+)?(?:manufacturing\s+)?(?:plants?|sites?|units?|facilities)\b",
    r"\bconsolidated\b",
    r"\bgroup\s+level\b",
    r"\bentity[-\s]level\b",
    r"\bincluding\s+(?:subsidiaries|associates)\b",
    r"\bexcluding\b",
    r"\bscope\s+[123]\b",
    r"\boperational\s+control\b",
    r"\bfinancial\s+control\b",
    r"\boundary\b",
    r"\bperimeter\b",
]

# Action/commitment indicators
ACTION_PATTERNS = [
    r"\bhave\s+(?:installed|implemented|deployed|adopted|established)\b",
    r"\binstalled\b",
    r"\bimplemented\b",
    r"\bcommissioned\b",
    r"\bset\s+(?:up|a\s+target)\b",
    r"\btarget\s+of\b",
    r"\bplan\s+to\b",
    r"\bcommitted\s+to\s+\d+",  # committed to X% — specific commitment
    r"\bprocured\s+\d+",
    r"\bgenerated\s+\d+",
    r"\bconsumed\s+\d+",
    r"\brecycled\s+\d+",
]


class DisclosureQualityChecker:
    """
    Checks narrative disclosure quality across 5 dimensions.
    Used for text fields like environmental commitments, policy descriptions, etc.
    """

    TIER_THRESHOLDS = {
        "excellent": 0.80,
        "good": 0.60,
        "fair": 0.40,
        "poor": 0.0,
    }

    def __init__(self):
        self._vague_re = [re.compile(p, re.IGNORECASE) for p in VAGUE_PHRASES]
        self._time_re = [re.compile(p, re.IGNORECASE) for p in TIME_PATTERNS]
        self._quant_re = [re.compile(p, re.IGNORECASE) for p in QUANTITATIVE_PATTERNS]
        self._boundary_re = [re.compile(p, re.IGNORECASE) for p in BOUNDARY_PATTERNS]
        self._action_re = [re.compile(p, re.IGNORECASE) for p in ACTION_PATTERNS]

    def check(self, field_code: str, text: str, min_words: int = 20) -> DisclosureQualityResult:
        """
        Run full quality check on a narrative disclosure.

        Args:
            field_code: BRSR/framework field identifier
            text: Narrative text entered by user
            min_words: Minimum acceptable word count
        """
        word_count = len(text.split()) if text else 0
        dimensions = []
        suggestions = []

        # --- Dimension 1: Specificity ---
        specificity = self._check_specificity(text)
        dimensions.append(specificity)
        if not specificity.passed:
            suggestions.append(
                "Replace vague phrases like 'we are committed to' with specific, "
                "measurable statements. E.g., 'Reduced Scope 1 emissions by 15% in FY2024'."
            )

        # --- Dimension 2: Time-boundedness ---
        time_bound = self._check_time_bound(text)
        dimensions.append(time_bound)
        if not time_bound.passed:
            suggestions.append(
                "Add a time reference — specify the financial year (e.g., FY2024), "
                "target year, or reporting period."
            )

        # --- Dimension 3: Quantitative evidence ---
        quantitative = self._check_quantitative(text)
        dimensions.append(quantitative)
        if not quantitative.passed:
            suggestions.append(
                "Include specific numbers with units (e.g., '2,450 tCO2e', '15%', '3.2 GJ/unit'). "
                "Quantified disclosures are significantly more credible."
            )

        # --- Dimension 4: Boundary clarity ---
        boundary = self._check_boundary(text)
        dimensions.append(boundary)
        if not boundary.passed:
            suggestions.append(
                "Clarify the scope/boundary — state which plants, sites, or entities "
                "this disclosure covers (e.g., 'all manufacturing facilities', 'consolidated group')."
            )

        # --- Dimension 5: Minimum length ---
        length_dim = self._check_length(text, min_words)
        dimensions.append(length_dim)
        if not length_dim.passed:
            suggestions.append(
                f"Disclosure is too brief ({word_count} words). "
                f"Aim for at least {min_words} words to provide adequate context."
            )

        # --- Overall score (weighted) ---
        weights = [0.30, 0.20, 0.25, 0.15, 0.10]
        overall = sum(d.score * w for d, w in zip(dimensions, weights))
        overall = round(min(overall, 1.0), 3)

        # Tier
        tier = "poor"
        for t, threshold in self.TIER_THRESHOLDS.items():
            if overall >= threshold:
                tier = t
                break

        return DisclosureQualityResult(
            field_code=field_code,
            text=text,
            overall_score=overall,
            quality_tier=tier,
            dimensions=dimensions,
            suggestions=suggestions,
            word_count=word_count,
        )

    def _check_specificity(self, text: str) -> QualityDimension:
        """Check for vague language — lower score = more vague phrases."""
        vague_hits = sum(1 for p in self._vague_re if p.search(text))
        word_count = max(len(text.split()), 1)

        # Penalise proportion of vague phrases
        vague_density = vague_hits / (word_count / 50)  # per 50 words
        score = max(0.0, 1.0 - min(vague_density, 1.0))

        found = [p.pattern for p in self._vague_re if p.search(text)]

        return QualityDimension(
            name="specificity",
            score=round(score, 2),
            passed=score >= 0.5,
            feedback=(
                f"Found {vague_hits} vague phrase(s): {found[:3]}"
                if vague_hits > 0
                else "No vague boilerplate detected."
            ),
        )

    def _check_time_bound(self, text: str) -> QualityDimension:
        """Check if disclosure references a specific time period."""
        hits = [p for p in self._time_re if p.search(text)]
        score = min(1.0, len(hits) * 0.4)

        return QualityDimension(
            name="time_boundedness",
            score=round(score, 2),
            passed=len(hits) >= 1,
            feedback=(
                f"Found {len(hits)} time reference(s)."
                if hits
                else "No time reference found. Add a specific FY or target year."
            ),
        )

    def _check_quantitative(self, text: str) -> QualityDimension:
        """Check for presence of numbers with units."""
        hits = [p for p in self._quant_re if p.search(text)]
        score = min(1.0, len(hits) * 0.35)

        return QualityDimension(
            name="quantitative_evidence",
            score=round(score, 2),
            passed=len(hits) >= 1,
            feedback=(
                f"Found {len(hits)} quantitative statement(s)."
                if hits
                else "No quantified data found. Add measurements with units."
            ),
        )

    def _check_boundary(self, text: str) -> QualityDimension:
        """Check for scope/boundary clarity."""
        hits = [p for p in self._boundary_re if p.search(text)]
        score = min(1.0, len(hits) * 0.5)

        return QualityDimension(
            name="boundary_clarity",
            score=round(score, 2),
            passed=len(hits) >= 1,
            feedback=(
                f"Found {len(hits)} boundary/scope reference(s)."
                if hits
                else "Boundary not stated. Specify which sites/entities are covered."
            ),
        )

    def _check_length(self, text: str, min_words: int) -> QualityDimension:
        """Check minimum word count."""
        word_count = len(text.split()) if text else 0
        score = min(1.0, word_count / min_words)

        return QualityDimension(
            name="disclosure_length",
            score=round(score, 2),
            passed=word_count >= min_words,
            feedback=f"{word_count} words (minimum: {min_words}).",
        )
