"""
ESGPilot — Evaluation Harness.

Evaluates the full pipeline against a gold set of Q&A pairs.
Metrics (per BUILD_SPEC §11):
  - Retrieval: Recall@5, MRR (gold chunk must appear in top-5)
  - Answer quality: Faithfulness, Citation precision (RAGAS-inspired)
  - Abstain accuracy: Does the model correctly abstain on out-of-corpus questions?
  - Latency: p50/p95 end-to-end

Usage:
    python eval/harness/evaluator.py --gold-set eval/gold_sets/brsr_qa.jsonl
    python eval/harness/evaluator.py --gold-set eval/gold_sets/brsr_qa.jsonl --report
"""

import argparse
import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, median, quantiles
from typing import Optional


# ──────────────────────────────────────────────
# Data Structures
# ──────────────────────────────────────────────

@dataclass
class GoldExample:
    """A single gold evaluation example."""
    id: str
    question: str
    ground_truth_answer: str
    gold_citations: list[dict]           # [{doc, section, version}]
    relevant_chunk_ids: list[str]        # Gold chunk IDs that must be retrieved
    framework: str = "BRSR"
    should_abstain: bool = False         # True if model should refuse/abstain
    entity_class: str = "top_1000"
    category: str = "kb_qa"             # kb_qa | field_help | section_review | sdg_map


@dataclass
class EvalResult:
    """Result for a single eval example."""
    example_id: str
    question: str
    predicted_answer: str
    predicted_citations: list[dict]
    retrieved_chunk_ids: list[str]
    latency_ms: float
    abstained: bool

    # Computed metrics
    recall_at_5: float = 0.0
    mrr: float = 0.0
    faithfulness: float = 0.0
    citation_precision: float = 0.0
    abstain_correct: Optional[bool] = None
    error: Optional[str] = None


@dataclass
class EvalReport:
    """Aggregate evaluation report."""
    total: int = 0
    recall_at_5: float = 0.0
    mrr: float = 0.0
    faithfulness: float = 0.0
    citation_precision: float = 0.0
    abstain_accuracy: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    errors: int = 0
    results: list[EvalResult] = field(default_factory=list)

    def passed(self, thresholds: dict) -> bool:
        """Check if all metrics meet thresholds."""
        return (
            self.recall_at_5 >= thresholds.get("recall_at_5", 0.90)
            and self.mrr >= thresholds.get("mrr", 0.80)
            and self.faithfulness >= thresholds.get("faithfulness", 0.92)
            and self.citation_precision >= thresholds.get("citation_precision", 0.95)
            and self.abstain_accuracy >= thresholds.get("abstain_accuracy", 0.90)
        )


# ──────────────────────────────────────────────
# Gold Set Loader
# ──────────────────────────────────────────────

class GoldSetLoader:
    """Load and validate gold evaluation examples from JSONL."""

    @staticmethod
    def load(filepath: str) -> list[GoldExample]:
        examples = []
        with open(filepath, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    ex = GoldExample(
                        id=data.get("id", f"ex_{i}"),
                        question=data["question"],
                        ground_truth_answer=data["ground_truth_answer"],
                        gold_citations=data.get("gold_citations", []),
                        relevant_chunk_ids=data.get("relevant_chunk_ids", []),
                        framework=data.get("framework", "BRSR"),
                        should_abstain=data.get("should_abstain", False),
                        entity_class=data.get("entity_class", "top_1000"),
                        category=data.get("category", "kb_qa"),
                    )
                    examples.append(ex)
                except (KeyError, json.JSONDecodeError) as e:
                    print(f"Skipping malformed example at line {i+1}: {e}")

        print(f"Loaded {len(examples)} gold examples from {filepath}")
        return examples


# ──────────────────────────────────────────────
# Metric Calculators
# ──────────────────────────────────────────────

def compute_recall_at_k(
    retrieved_ids: list[str],
    relevant_ids: list[str],
    k: int = 5,
) -> float:
    """Recall@K: fraction of relevant chunks retrieved in top-K."""
    if not relevant_ids:
        return 1.0  # Nothing to recall
    top_k = retrieved_ids[:k]
    hits = sum(1 for r in relevant_ids if r in top_k)
    return hits / len(relevant_ids)


def compute_mrr(
    retrieved_ids: list[str],
    relevant_ids: list[str],
) -> float:
    """Mean Reciprocal Rank: 1/rank of first relevant result."""
    for i, chunk_id in enumerate(retrieved_ids):
        if chunk_id in relevant_ids:
            return 1.0 / (i + 1)
    return 0.0


def compute_faithfulness(
    answer: str,
    context_chunks: list[str],
) -> float:
    """
    Simplified faithfulness: fraction of answer sentences that are
    supported by at least one context chunk.

    Production version would use an NLI model (e.g., DeBERTa-NLI).
    This is a lightweight heuristic using keyword overlap.
    """
    if not answer or not context_chunks:
        return 0.0

    sentences = [s.strip() for s in answer.split(".") if s.strip() and len(s.split()) > 5]
    if not sentences:
        return 1.0  # No substantive claims

    context_text = " ".join(context_chunks).lower()
    supported = 0

    for sentence in sentences:
        # Extract key content words (skip stopwords)
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "of", "and", "or",
                     "in", "on", "at", "to", "for", "with", "this", "that", "it"}
        words = set(sentence.lower().split()) - stopwords
        meaningful_words = [w for w in words if len(w) > 4]

        if not meaningful_words:
            supported += 1
            continue

        # Check if majority of key words appear in context
        hits = sum(1 for w in meaningful_words if w in context_text)
        if hits / len(meaningful_words) >= 0.5:
            supported += 1

    return supported / len(sentences)


def compute_citation_precision(
    predicted_citations: list[dict],
    gold_citations: list[dict],
) -> float:
    """
    Fraction of predicted citations that appear in the gold set.
    Checks by doc name match (case-insensitive).
    """
    if not predicted_citations:
        # No citations predicted — precision is 0 if gold expects citations
        return 0.0 if gold_citations else 1.0

    gold_docs = {c.get("doc", "").lower() for c in gold_citations}
    hits = sum(
        1 for pc in predicted_citations
        if any(
            gold_doc in pc.get("doc_title", "").lower()
            or gold_doc in pc.get("doc", "").lower()
            for gold_doc in gold_docs
        )
    )
    return hits / len(predicted_citations)


# ──────────────────────────────────────────────
# Pipeline Runner
# ──────────────────────────────────────────────

class Evaluator:
    """
    Runs the ESGPilot pipeline against gold examples.
    Can run against live API or offline (for retrieval-only eval).
    """

    ACCEPTANCE_THRESHOLDS = {
        "recall_at_5": 0.90,
        "mrr": 0.80,
        "faithfulness": 0.92,
        "citation_precision": 0.95,
        "abstain_accuracy": 0.90,
    }

    def __init__(
        self,
        api_base_url: str = "http://localhost:8000",
        api_token: str = "",
        mode: str = "api",  # "api" | "offline"
    ):
        self.api_base_url = api_base_url.rstrip("/")
        self.api_token = api_token
        self.mode = mode

    async def evaluate_example(self, example: GoldExample) -> EvalResult:
        """Run a single example through the pipeline."""
        start = time.time()
        error = None
        predicted_answer = ""
        predicted_citations = []
        retrieved_chunk_ids = []
        abstained = False

        try:
            if self.mode == "api":
                result = await self._call_api(example)
                predicted_answer = result.get("answer", "")
                predicted_citations = result.get("citations", [])
                retrieved_chunk_ids = result.get("chunk_ids", [])
                abstained = result.get("abstained", False)
            else:
                # Offline mode: skip model call, evaluate retrieval only
                predicted_answer = "[offline mode - no model call]"
                abstained = example.should_abstain

        except Exception as e:
            error = str(e)

        latency_ms = (time.time() - start) * 1000

        # Compute metrics
        recall = compute_recall_at_k(retrieved_chunk_ids, example.relevant_chunk_ids)
        mrr = compute_mrr(retrieved_chunk_ids, example.relevant_chunk_ids)
        faithfulness = compute_faithfulness(
            predicted_answer,
            [c.get("excerpt", "") for c in predicted_citations],
        )
        cit_precision = compute_citation_precision(predicted_citations, example.gold_citations)

        # Abstain accuracy
        abstain_correct = None
        if example.should_abstain:
            abstain_correct = abstained
        elif not example.should_abstain and abstained:
            abstain_correct = False

        return EvalResult(
            example_id=example.id,
            question=example.question,
            predicted_answer=predicted_answer,
            predicted_citations=predicted_citations,
            retrieved_chunk_ids=retrieved_chunk_ids,
            latency_ms=latency_ms,
            abstained=abstained,
            recall_at_5=recall,
            mrr=mrr,
            faithfulness=faithfulness,
            citation_precision=cit_precision,
            abstain_correct=abstain_correct,
            error=error,
        )

    async def _call_api(self, example: GoldExample) -> dict:
        """Call the ESGPilot /v1/kb/ask endpoint."""
        import httpx

        payload = {
            "question": example.question,
            "framework": example.framework,
            "entity_class": example.entity_class,
        }
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.api_base_url}/v1/kb/ask",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    async def run(self, examples: list[GoldExample]) -> EvalReport:
        """Run full evaluation."""
        print(f"Running evaluation on {len(examples)} examples...")
        results = []

        for i, example in enumerate(examples):
            result = await self.evaluate_example(example)
            results.append(result)
            if (i + 1) % 10 == 0:
                print(f"  Progress: {i+1}/{len(examples)}")

        return self._aggregate(results)

    @staticmethod
    def _aggregate(results: list[EvalResult]) -> EvalReport:
        """Aggregate individual results into a report."""
        valid = [r for r in results if not r.error]
        errors = len(results) - len(valid)

        if not valid:
            return EvalReport(total=len(results), errors=errors, results=results)

        # Retrieval metrics (only for examples with gold chunk IDs)
        retrieval_results = [r for r in valid if r.recall_at_5 is not None]
        recall = mean([r.recall_at_5 for r in retrieval_results]) if retrieval_results else 0.0
        mrr = mean([r.mrr for r in retrieval_results]) if retrieval_results else 0.0

        # Answer quality
        faith = mean([r.faithfulness for r in valid])
        cit_prec = mean([r.citation_precision for r in valid])

        # Abstain accuracy
        abstain_results = [r for r in valid if r.abstain_correct is not None]
        abstain_acc = (
            mean([float(r.abstain_correct) for r in abstain_results])
            if abstain_results else 1.0
        )

        # Latency
        latencies = sorted([r.latency_ms for r in valid])
        p50 = median(latencies) if latencies else 0.0
        p95 = quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies, default=0.0)

        return EvalReport(
            total=len(results),
            recall_at_5=round(recall, 4),
            mrr=round(mrr, 4),
            faithfulness=round(faith, 4),
            citation_precision=round(cit_prec, 4),
            abstain_accuracy=round(abstain_acc, 4),
            p50_latency_ms=round(p50, 1),
            p95_latency_ms=round(p95, 1),
            errors=errors,
            results=results,
        )

    def print_report(self, report: EvalReport) -> None:
        """Print a formatted eval report."""
        print("\n" + "=" * 60)
        print("ESGPilot Evaluation Report")
        print("=" * 60)
        print(f"Total examples : {report.total}")
        print(f"Errors         : {report.errors}")
        print()
        print("RETRIEVAL")
        print(f"  Recall@5     : {report.recall_at_5:.3f}  (target ≥ 0.90)")
        print(f"  MRR          : {report.mrr:.3f}  (target ≥ 0.80)")
        print()
        print("ANSWER QUALITY")
        print(f"  Faithfulness : {report.faithfulness:.3f}  (target ≥ 0.92)")
        print(f"  Citation P   : {report.citation_precision:.3f}  (target ≥ 0.95)")
        print(f"  Abstain Acc  : {report.abstain_accuracy:.3f}  (target ≥ 0.90)")
        print()
        print("LATENCY")
        print(f"  p50          : {report.p50_latency_ms:.0f} ms")
        print(f"  p95          : {report.p95_latency_ms:.0f} ms")
        print()
        passed = report.passed(self.ACCEPTANCE_THRESHOLDS)
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"Overall gate   : {status}")
        print("=" * 60)

        if not passed:
            print("\nFailing metrics:")
            for metric, threshold in self.ACCEPTANCE_THRESHOLDS.items():
                val = getattr(report, metric)
                if val < threshold:
                    print(f"  {metric}: {val:.3f} < {threshold}")

    def save_report(self, report: EvalReport, output_path: str) -> None:
        """Save full report to JSON."""
        data = {
            "summary": {
                "total": report.total,
                "errors": report.errors,
                "recall_at_5": report.recall_at_5,
                "mrr": report.mrr,
                "faithfulness": report.faithfulness,
                "citation_precision": report.citation_precision,
                "abstain_accuracy": report.abstain_accuracy,
                "p50_latency_ms": report.p50_latency_ms,
                "p95_latency_ms": report.p95_latency_ms,
                "passed": report.passed(self.ACCEPTANCE_THRESHOLDS),
            },
            "results": [
                {
                    "id": r.example_id,
                    "question": r.question[:100],
                    "recall_at_5": r.recall_at_5,
                    "mrr": r.mrr,
                    "faithfulness": r.faithfulness,
                    "citation_precision": r.citation_precision,
                    "abstain_correct": r.abstain_correct,
                    "latency_ms": r.latency_ms,
                    "error": r.error,
                }
                for r in report.results
            ],
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"\nReport saved → {output_path}")


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ESGPilot Evaluation Harness")
    parser.add_argument("--gold-set", required=True, help="Path to gold JSONL file")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--token", default="", help="API bearer token")
    parser.add_argument("--mode", choices=["api", "offline"], default="offline")
    parser.add_argument("--report", action="store_true", help="Save JSON report")
    parser.add_argument("--output", default=None, help="Output path for JSON report")
    args = parser.parse_args()

    loader = GoldSetLoader()
    examples = loader.load(args.gold_set)

    evaluator = Evaluator(
        api_base_url=args.api_url,
        api_token=args.token,
        mode=args.mode,
    )

    report = asyncio.run(evaluator.run(examples))
    evaluator.print_report(report)

    if args.report:
        output_path = args.output or args.gold_set.replace(".jsonl", "_report.json")
        evaluator.save_report(report, output_path)


if __name__ == "__main__":
    main()
