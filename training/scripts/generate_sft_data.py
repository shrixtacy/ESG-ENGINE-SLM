"""
ESGPilot — SFT Dataset Generator.

Generates Supervised Fine-Tuning (SFT) training examples for the ESG copilot.

Training example types (per BUILD_SPEC §4.3 Stage 1):
  (a) Document-grounded Q&A with citations
  (b) Form-field explanation
  (c) ESG narrative critique (disclosure quality review)
  (d) SDG tagging (text → JSON array of goals/targets)
  (e) JSON recommendation objects (structured output)
  (f) Refusal/abstain cases (out-of-scope or uncertain)

Output format: JSONL, each line = {"messages": [{"role": ..., "content": ...}]}
Compatible with OpenAI fine-tune format / Unsloth / Axolotl / TRL SFTTrainer.

IMPORTANT: All generated examples must be reviewed by an ESG SME before use.
           Run with --draft to generate without saving; use --save to write to disk.
"""

import argparse
import json
import os
import random
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

# ──────────────────────────────────────────────
# Output path
# ──────────────────────────────────────────────

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ──────────────────────────────────────────────
# System prompt (matches inference.py)
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """You are ESGPilot, an expert ESG reporting assistant specialising in Indian frameworks (BRSR, NGRBC, Companies Act s.135) and global standards (GRI, UN SDGs, GHG Protocol). You help users fill ESG disclosure forms correctly.

Core rules:
1. NEVER invent numbers. Numbers come only from the rules engine or user data.
2. ALWAYS cite sources with document name, section, and version.
3. Abstain if evidence is insufficient — say "I don't have enough information."
4. Be practical: explain HOW to fill forms, not generic ESG theory.
5. No legal advice. Add disclaimer for compliance-critical answers."""


# ──────────────────────────────────────────────
# Template Builders
# ──────────────────────────────────────────────

def make_kb_qa_example(
    question: str,
    answer: str,
    citations: list[dict],
    framework: str = "BRSR",
    abstain: bool = False,
) -> dict:
    """Build a knowledge Q&A training example with citations."""
    citation_text = "\n".join([
        f"[{c['doc']} | {c.get('section', '')} | {c.get('version', '')}]"
        for c in citations
    ])

    assistant_content = answer
    if citations and not abstain:
        assistant_content += f"\n\nSources:\n{citation_text}"

    if abstain:
        assistant_content = (
            "I don't have enough information in my knowledge base to answer this accurately. "
            "The specific guidance you're looking for may not be in my current sources, "
            "or may depend on factors specific to your situation. "
            "I recommend consulting the official SEBI/MCA circular or a qualified ESG consultant."
        )

    return {
        "id": f"kb_qa_{uuid.uuid4().hex[:8]}",
        "type": "kb_qa",
        "framework": framework,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
            {"role": "assistant", "content": assistant_content},
        ],
        "metadata": {
            "citations": citations,
            "abstain": abstain,
            "created_at": datetime.utcnow().isoformat(),
            "sme_reviewed": False,
        },
    }


def make_field_help_example(
    field_code: str,
    field_label: str,
    question: str,
    explanation: str,
    unit: Optional[str],
    citations: list[dict],
) -> dict:
    """Build a form-field explanation example."""
    answer = f"**{field_label}**\n\n{explanation}"
    if unit:
        answer += f"\n\n**Unit**: {unit}"
    if citations:
        citation_text = "\n".join([
            f"• {c['doc']}, {c.get('section', '')}, {c.get('version', '')}"
            for c in citations
        ])
        answer += f"\n\n**Reference**:\n{citation_text}"

    return {
        "id": f"field_{uuid.uuid4().hex[:8]}",
        "type": "field_help",
        "field_code": field_code,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"I'm filling in the BRSR form. "
                    f"Field: {field_label} (code: {field_code})\n\n{question}"
                ),
            },
            {"role": "assistant", "content": answer},
        ],
        "metadata": {
            "citations": citations,
            "sme_reviewed": False,
            "created_at": datetime.utcnow().isoformat(),
        },
    }


def make_reviewer_example(
    section: str,
    field_values: dict,
    rules_findings: list[dict],
    narrative_review: str,
) -> dict:
    """Build a section reviewer example (rules → narrative)."""
    context = (
        f"## Form Context\n"
        f"Section: {section}\n"
        f"Field values: {json.dumps(field_values, indent=2)}\n\n"
        f"## Rules Engine Findings\n"
        f"{json.dumps(rules_findings, indent=2)}"
    )

    return {
        "id": f"review_{uuid.uuid4().hex[:8]}",
        "type": "section_review",
        "section": section,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"{context}\n\n"
                    "Please review these findings and provide a concise summary "
                    "with prioritised recommendations."
                ),
            },
            {"role": "assistant", "content": narrative_review},
        ],
        "metadata": {"sme_reviewed": False, "created_at": datetime.utcnow().isoformat()},
    }


def make_sdg_tagger_example(
    activity_text: str,
    sdg_tags: list[dict],
) -> dict:
    """Build an SDG tagging example (text → JSON)."""
    return {
        "id": f"sdg_{uuid.uuid4().hex[:8]}",
        "type": "sdg_tagger",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Map this activity/initiative to UN SDG goals and targets:\n\n"
                    f"{activity_text}"
                ),
            },
            {"role": "assistant", "content": json.dumps(sdg_tags, indent=2)},
        ],
        "metadata": {"sme_reviewed": False, "created_at": datetime.utcnow().isoformat()},
    }


def make_recommendation_example(
    context: str,
    recommendation: dict,
) -> dict:
    """Build a structured recommendation JSON output example."""
    return {
        "id": f"rec_{uuid.uuid4().hex[:8]}",
        "type": "recommendation",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": context},
            {"role": "assistant", "content": json.dumps(recommendation, indent=2)},
        ],
        "metadata": {"sme_reviewed": False, "created_at": datetime.utcnow().isoformat()},
    }


# ──────────────────────────────────────────────
# Seed Examples
# These are DRAFT examples — must be SME reviewed before training.
# ──────────────────────────────────────────────

SEED_KB_QA = [
    {
        "question": "Is BRSR mandatory for all listed companies in India?",
        "answer": (
            "BRSR is mandatory for the top 1,000 listed entities by market capitalisation "
            "from FY 2022–23 onwards. From FY 2023–24, the top 1,000 listed entities must "
            "also provide BRSR Core KPIs with reasonable assurance.\n\n"
            "For companies outside the top 1,000, BRSR disclosure is voluntary but encouraged. "
            "SEBI's phased timeline for value chain assurance begins from FY 2024–25."
        ),
        "citations": [
            {"doc": "SEBI BRSR Circular", "section": "Para 1–3", "version": "SEBI/HO/CFD/CMD-2/CIR/P/2021/562"},
            {"doc": "SEBI BRSR Core Circular", "section": "Phase-in timeline", "version": "2023-07-12"},
        ],
        "framework": "BRSR",
    },
    {
        "question": "What is Scope 3 emissions? Is it mandatory in BRSR?",
        "answer": (
            "Scope 3 emissions are all indirect GHG emissions that occur in a company's "
            "value chain, including both upstream (e.g., purchased goods, business travel) "
            "and downstream (e.g., use of sold products, end-of-life treatment).\n\n"
            "In BRSR v1 (2021), Scope 3 disclosure is a Leadership Indicator (voluntary). "
            "BRSR Core (2023) includes Scope 3 as part of the enhanced KPIs but it is "
            "not yet subject to mandatory assurance. Companies are encouraged to report "
            "at least top 3–5 Scope 3 categories by materiality."
        ),
        "citations": [
            {"doc": "BRSR Annexure I", "section": "Principle 6, Leadership Indicator 2", "version": "2023"},
            {"doc": "GHG Protocol Corporate Value Chain (Scope 3) Standard", "section": "Chapter 1", "version": "2011"},
        ],
        "framework": "BRSR",
    },
    {
        "question": "What does 'water stress area' mean in BRSR?",
        "answer": (
            "A water-stressed area is a region where demand for water exceeds the available "
            "amount, or where water quality is poor. In BRSR, companies are asked to disclose "
            "water withdrawal specifically from water-stressed areas to highlight concentration "
            "of risk.\n\n"
            "The globally used reference for identifying water-stressed areas is the "
            "WRI Aqueduct Water Risk Atlas (available at aqueduct.wri.org). Areas classified "
            "as 'High' or 'Extremely High' baseline water stress are typically reported."
        ),
        "citations": [
            {"doc": "BRSR Annexure I", "section": "Principle 6 EI-9", "version": "2023"},
            {"doc": "WRI Aqueduct Water Risk Atlas", "section": "Methodology", "version": "3.0"},
        ],
        "framework": "BRSR",
    },
    {
        "question": "How do I calculate GHG intensity in BRSR?",
        "answer": (
            "GHG intensity is calculated as:\n\n"
            "**GHG Intensity = Total GHG Emissions (tCO2e) ÷ Denominator**\n\n"
            "BRSR allows flexibility on the denominator — common choices include:\n"
            "• Turnover (₹ crore) → tCO2e/₹ crore\n"
            "• Revenue from operations → tCO2e/₹ crore\n"
            "• Physical output (e.g., tCO2e/MT of product, tCO2e/kWh generated)\n\n"
            "You must state the denominator and its unit clearly. "
            "GHG intensity covers Scope 1 + Scope 2 emissions. "
            "The rules engine computes the actual intensity value — enter your total GHG "
            "and turnover figures and it will calculate automatically."
        ),
        "citations": [
            {"doc": "BRSR Annexure I", "section": "Principle 6 EI-8", "version": "2023"},
            {"doc": "GHG Protocol Corporate Standard", "section": "Chapter 11", "version": "2015"},
        ],
        "framework": "BRSR",
    },
    {
        "question": "What is the CSR spending obligation under the Companies Act?",
        "answer": (
            "Under Section 135 of the Companies Act 2013 (as amended), companies meeting "
            "the eligibility threshold must spend at least 2% of average net profits of "
            "the preceding three financial years on CSR activities.\n\n"
            "Eligibility thresholds (any one):\n"
            "• Net worth ≥ ₹500 crore, OR\n"
            "• Turnover ≥ ₹1,000 crore, OR\n"
            "• Net profit ≥ ₹5 crore\n\n"
            "Unspent CSR amounts must be transferred to a special Unspent CSR Account "
            "within 30 days of the end of FY, and utilised within 3 years. "
            "Ongoing projects have different rules — unspent funds must be transferred "
            "within 6 months of FY end."
        ),
        "citations": [
            {"doc": "Companies Act 2013", "section": "Section 135", "version": "2013-amended-2021"},
            {"doc": "Companies (CSR Policy) Rules 2014", "section": "Rule 4", "version": "2022"},
        ],
        "framework": "CSR",
    },
]

SEED_FIELD_HELP = [
    {
        "field_code": "brsr_p6_ei7_scope1",
        "field_label": "Scope 1 GHG Emissions",
        "question": "What should I enter here? What unit?",
        "explanation": (
            "Enter the total direct greenhouse gas (GHG) emissions from sources your company "
            "owns or controls. This includes:\n"
            "• Combustion of fuels (diesel, coal, LPG, CNG, furnace oil) in owned vehicles, "
            "boilers, generators, and process equipment\n"
            "• Process emissions (e.g., cement calcination, lime production)\n"
            "• Fugitive emissions (leakage from refrigerants, SF6 in transformers)\n\n"
            "Exclude Scope 2 (purchased electricity) and Scope 3 (value chain) here.\n\n"
            "Use the emission calculator to convert fuel consumption data to tCO2e: "
            "activity data (kL of diesel, MT of coal, etc.) × appropriate emission factor."
        ),
        "unit": "tCO2e (metric tonnes of CO2 equivalent, using IPCC AR5 GWP values)",
        "citations": [
            {"doc": "BRSR Annexure I", "section": "Principle 6, Essential Indicator 7a", "version": "2023"},
            {"doc": "GHG Protocol Corporate Standard", "section": "Chapter 4 — Direct GHG Emissions", "version": "2015"},
        ],
    },
    {
        "field_code": "brsr_p6_ei9_withdrawal",
        "field_label": "Total Water Withdrawal",
        "question": "What sources should I include in water withdrawal?",
        "explanation": (
            "Total water withdrawal = ALL water drawn from any source for use in your operations:\n\n"
            "• **Groundwater** — borewells, tube wells, open wells\n"
            "• **Surface water** — rivers, lakes, canals, ponds\n"
            "• **Rainwater harvested** — rooftop collection, check dams\n"
            "• **Municipal/treated water** — water purchased from utilities or tankers\n"
            "• **Seawater** — if used for cooling (report separately)\n\n"
            "Do NOT include water that is recycled and reused within the plant boundary "
            "(that goes in the recycled/reused line item). "
            "Report for the full financial year across all facilities in the reporting boundary."
        ),
        "unit": "Kilolitres (KL). 1 KL = 1 m³ = 1,000 litres.",
        "citations": [
            {"doc": "BRSR Annexure I", "section": "Principle 6, Essential Indicator 9", "version": "2023"},
            {"doc": "GRI 303 Water and Effluents", "section": "Disclosure 303-3", "version": "2018"},
        ],
    },
]

SEED_SDG_TAGS = [
    {
        "activity": (
            "In FY2024, we installed 15 MW of rooftop solar across 8 manufacturing plants, "
            "generating 21 million kWh of clean energy, reducing grid electricity consumption "
            "by 22% and avoiding 15,000 tCO2e of Scope 2 emissions."
        ),
        "tags": [
            {"goal": 7, "target": "7.2", "confidence": 0.95,
             "rationale": "Substantially increases share of renewable energy in total energy mix"},
            {"goal": 13, "target": "13.2", "confidence": 0.90,
             "rationale": "Integrates climate change measures — directly reduces GHG emissions"},
            {"goal": 9, "target": "9.4", "confidence": 0.70,
             "rationale": "Upgrades infrastructure to make it sustainable and resource-efficient"},
        ],
    },
    {
        "activity": (
            "We conducted health and safety training for 2,450 employees and 1,200 contractual "
            "workers covering fire safety, chemical handling, and emergency evacuation. "
            "Lost Time Injury Rate reduced from 0.42 to 0.18 per 100 workers."
        ),
        "tags": [
            {"goal": 3, "target": "3.9", "confidence": 0.85,
             "rationale": "Substantially reduces health risks from occupational hazards"},
            {"goal": 8, "target": "8.8", "confidence": 0.95,
             "rationale": "Directly protects labour rights and promotes safe working environments"},
        ],
    },
]

SEED_ABSTAIN = [
    "What is the share price of Reliance Industries?",
    "Can you give me legal advice on our ESG compliance liability?",
    "What will India's GDP growth be next year?",
    "Provide an assurance statement for our BRSR report.",
    "Tell me which investment funds are best for ESG?",
    "Is the audit opinion for our ESG report included in BRSR?",
]


# ──────────────────────────────────────────────
# Dataset Builder
# ──────────────────────────────────────────────

def build_dataset() -> list[dict]:
    """Build the complete SFT dataset from seed examples."""
    examples = []

    # (a) KB Q&A examples
    for seed in SEED_KB_QA:
        ex = make_kb_qa_example(
            question=seed["question"],
            answer=seed["answer"],
            citations=seed["citations"],
            framework=seed.get("framework", "BRSR"),
        )
        examples.append(ex)

    # (b) Field help examples
    for seed in SEED_FIELD_HELP:
        ex = make_field_help_example(
            field_code=seed["field_code"],
            field_label=seed["field_label"],
            question=seed["question"],
            explanation=seed["explanation"],
            unit=seed.get("unit"),
            citations=seed["citations"],
        )
        examples.append(ex)

    # (c) Reviewer example
    reviewer_ex = make_reviewer_example(
        section="Principle 6 — Environment",
        field_values={
            "brsr_p6_ei7_scope1": {"value": 5200, "unit": "tCO2e"},
            "brsr_p6_ei7_scope2": {"value": 12000, "unit": "tCO2e"},
            "brsr_p6_ei7_total": {"value": 17200, "unit": "tCO2e"},
        },
        rules_findings=[
            {
                "rule_id": "YOY_UP_brsr_p6_ei7_scope2",
                "type": "yoy_delta",
                "severity": "warn",
                "field_code": "brsr_p6_ei7_scope2",
                "title": "Large YoY increase (240%): Scope 2 GHG Emissions",
                "detail": "Value changed from 3,500 to 12,000 tCO2e (+243%). Please verify.",
            }
        ],
        narrative_review=(
            "**Summary**: Your Scope 1 entry of 5,200 tCO2e and total of 17,200 tCO2e "
            "are arithmetically consistent. However, your Scope 2 emissions show a large "
            "year-on-year increase of 243% (from 3,500 to 12,000 tCO2e).\n\n"
            "**Priority Recommendation**: Before submitting, please verify:\n"
            "1. **Emission factor year** — Did you use the FY2024 CEA grid EF (0.71 tCO2e/MWh) "
            "vs the prior year factor (0.79 tCO2e/MWh)? A higher factor would increase Scope 2.\n"
            "2. **Unit consistency** — Confirm electricity consumption is in kWh, not MWh. "
            "A unit error of 1,000x would explain the ~240% jump.\n"
            "3. **Boundary expansion** — Did you add new facilities this year? "
            "If yes, note this in the disclosure.\n\n"
            "This finding is **warn** severity, meaning it may be correct but warrants "
            "verification before final submission."
        ),
    )
    examples.append(reviewer_ex)

    # (d) SDG tagging examples
    for seed in SEED_SDG_TAGS:
        ex = make_sdg_tagger_example(
            activity_text=seed["activity"],
            sdg_tags=seed["tags"],
        )
        examples.append(ex)

    # (e) Structured recommendation example
    rec_ex = make_recommendation_example(
        context=(
            "BRSR review for Project Alpha, FY2024.\n"
            "Rules engine finding: Scope 2 emissions (15,000 tCO2e) are 340% higher YoY. "
            "Emission factor used: 0.72 (FY2023 CEA). "
            "Electricity consumption: 21,000 MWh (up from 4,900 MWh).\n\n"
            "Generate a structured recommendation JSON."
        ),
        recommendation={
            "id": "rec_a7b2c3",
            "scope": "field",
            "severity": "critical",
            "title": "Scope 2 emissions 340% higher YoY — verify electricity data",
            "why": (
                "Electricity consumption jumped from 4,900 MWh to 21,000 MWh (+329%). "
                "This could indicate a genuine business expansion (new facilities) or "
                "a data entry error (MWh vs kWh confusion is common). "
                "At the current CEA grid EF, 21,000 MWh = ~15,120 tCO2e."
            ),
            "how_to_fix": (
                "1. Verify electricity bills/meter readings sum to 21,000 MWh. "
                "2. Confirm unit is MWh throughout (not kWh). "
                "3. If new facilities added, state this in the disclosure narrative. "
                "4. Attach electricity bills as evidence (source_type = 'utility_bill')."
            ),
            "references": [
                {"doc": "BRSR Annexure I", "section": "P6 EI-7b", "version": "2023"},
                {"doc": "CEA CO2 Baseline Database", "section": "Grid EF FY2024", "version": "v18-2023"},
            ],
            "sdg_tags": ["7.2", "13.2"],
            "confidence": 0.91,
            "source": "hybrid",
        },
    )
    examples.append(rec_ex)

    # (f) Abstain examples
    for out_of_scope in SEED_ABSTAIN:
        ex = make_kb_qa_example(
            question=out_of_scope,
            answer="",
            citations=[],
            abstain=True,
        )
        examples.append(ex)

    return examples


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate SFT training data for ESGPilot")
    parser.add_argument("--save", action="store_true", help="Write output to disk")
    parser.add_argument("--draft", action="store_true", help="Print examples only (no save)")
    parser.add_argument("--output", type=str, default=None, help="Output JSONL file path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    random.seed(args.seed)

    print("Generating SFT dataset...")
    examples = build_dataset()
    print(f"Generated {len(examples)} examples")

    # Type breakdown
    types = {}
    for ex in examples:
        t = ex["type"]
        types[t] = types.get(t, 0) + 1
    print("\nBreakdown:")
    for t, count in sorted(types.items()):
        print(f"  {t}: {count}")

    if args.draft or (not args.save):
        print("\n--- SAMPLE (first example) ---")
        print(json.dumps(examples[0], indent=2)[:1500])
        print("\n⚠️  DRAFT mode: not saved. Use --save to write to disk.")
        print("⚠️  All examples require SME review before training.")
        return

    if args.save:
        output_path = args.output or os.path.join(
            OUTPUT_DIR, f"sft_draft_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.jsonl"
        )
        with open(output_path, "w", encoding="utf-8") as f:
            for ex in examples:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")

        print(f"\n✅ Saved {len(examples)} examples → {output_path}")
        print("⚠️  IMPORTANT: These are DRAFT examples. SME review required before training.")


if __name__ == "__main__":
    main()
