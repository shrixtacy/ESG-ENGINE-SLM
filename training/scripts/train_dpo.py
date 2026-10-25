"""
ESGPilot — DPO/ORPO Preference Training Script.

Stage 2: Preference tuning after SFT.
Uses TRL DPOTrainer (or ORPOTrainer) with pairs of:
  - chosen: good answer (cited, accurate, appropriately abstained)
  - rejected: bad answer (hallucinated number, no citation, overclaiming)

Dataset format (JSONL):
{
  "prompt": "<user question>",
  "chosen": "<good answer with citations>",
  "rejected": "<bad answer — hallucinated / uncited / overconfident>"
}

Usage:
    python train_dpo.py --sft-model training/checkpoints/lora_v1 --output training/checkpoints/dpo_v1
"""

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class DPOConfig:
    """DPO training configuration."""
    sft_model_path: str = "training/checkpoints/lora_v1"
    train_file: str = "training/data/dpo_pairs.jsonl"
    output_dir: str = "training/checkpoints/dpo_v1"
    method: str = "dpo"  # "dpo" | "orpo"

    # DPO hyperparams
    beta: float = 0.1  # KL penalty (0.1 = standard; lower = more deviation from SFT)
    learning_rate: float = 5e-5
    num_train_epochs: int = 1
    per_device_train_batch_size: int = 2
    gradient_accumulation_steps: int = 8
    max_length: int = 2048
    max_prompt_length: int = 512
    seed: int = 42


# ──────────────────────────────────────────────
# Seed DPO Pairs (DRAFT — must be SME reviewed)
# ──────────────────────────────────────────────

SEED_DPO_PAIRS = [
    {
        "prompt": "What is the mandatory deadline for BRSR disclosure for top 1,000 companies?",
        "chosen": (
            "The top 1,000 listed entities by market capitalisation must submit BRSR "
            "disclosures from FY 2022–23 onwards (i.e., in their annual reports published "
            "in 2023). This was mandated by SEBI Circular No. SEBI/HO/CFD/CMD-2/CIR/P/2021/562 "
            "dated May 10, 2021.\n\n"
            "Source: [SEBI BRSR Circular | Para 1 | SEBI/HO/CFD/CMD-2/CIR/P/2021/562]"
        ),
        "rejected": (
            "BRSR is mandatory from April 2023 for all listed companies in India. "
            "You must submit it every quarter to SEBI along with your financial results."
            # Hallucinated: wrong timing, wrong frequency, wrong scope
        ),
    },
    {
        "prompt": "My Scope 2 emissions went from 3,500 tCO2e to 12,000 tCO2e. Is that a problem?",
        "chosen": (
            "A 243% year-on-year increase in Scope 2 emissions is flagged by the rules engine "
            "as a significant anomaly that warrants verification before submission. "
            "Common causes include:\n\n"
            "1. **Unit error**: Entering electricity in MWh instead of kWh — a 1,000x difference\n"
            "2. **Emission factor change**: FY2024 CEA grid EF is 0.71 tCO2e/MWh vs 0.79 in prior years\n"
            "3. **Genuine expansion**: New facilities added to reporting boundary\n\n"
            "Please verify your electricity consumption data against meter readings/bills "
            "and confirm the emission factor used.\n\n"
            "Source: [BRSR Annexure I | P6 EI-7 | 2023], [CEA CO2 Baseline Database | v18 | 2023]"
        ),
        "rejected": (
            "Yes, your Scope 2 emissions of 12,000 tCO2e are too high. "
            "The industry average is around 5,000 tCO2e for companies your size. "
            "You should reduce your electricity consumption by 60% to meet benchmarks."
            # Hallucinated numbers ("5,000 average"), made-up benchmark, told user what to do without evidence
        ),
    },
    {
        "prompt": "Can you write an assurance statement for our BRSR report?",
        "chosen": (
            "I'm not able to provide an assurance statement. Assurance statements must be "
            "issued by an independent, accredited third-party assurance provider (such as a "
            "qualified CA firm or specialist ESG assurer) — not by an AI tool.\n\n"
            "For BRSR Core KPIs, SEBI mandates 'reasonable assurance' from a BRSR assurance "
            "provider from FY 2023–24 onwards for the top 1,000 listed entities. "
            "I recommend engaging an accredited assurer from ICAI's or NABCB's listed providers.\n\n"
            "*This is informational guidance, not legal or assurance advice.*"
        ),
        "rejected": (
            "Sure! Here is an assurance statement for your BRSR report:\n\n"
            "'We have examined the BRSR disclosures of [Company Name] and confirm that "
            "all material disclosures are accurate and in compliance with SEBI requirements.'"
            # Dangerous: providing fake assurance statement
        ),
    },
    {
        "prompt": "What is the water intensity formula for BRSR?",
        "chosen": (
            "Water intensity in BRSR is calculated as:\n\n"
            "**Water Intensity = Total Water Consumption (KL) ÷ Denominator**\n\n"
            "BRSR uses turnover (₹ crore) as the standard denominator, but companies "
            "may also use physical output (e.g., KL per MT of product) if more meaningful "
            "for their sector. You must state the denominator clearly.\n\n"
            "The actual calculation is performed by the rules engine — enter your water "
            "consumption and turnover, and the intensity will be computed automatically.\n\n"
            "Source: [BRSR Annexure I | P6 EI-9 | 2023]"
        ),
        "rejected": (
            "Water intensity = total water / turnover × 1000. "
            "For a company with ₹500 crore turnover and 2 million KL consumption, "
            "intensity = 2,000,000 / 500 × 1000 = 4,000,000. "
            "That's the industry standard formula used globally."
            # Hallucinated: wrong formula, invented "industry standard" claim, made-up calculation
        ),
    },
]


def create_dpo_dataset(filepath: str) -> None:
    """Write seed DPO pairs to JSONL file."""
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        for pair in SEED_DPO_PAIRS:
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")
    print(f"Wrote {len(SEED_DPO_PAIRS)} DPO pairs → {filepath}")
    print("⚠️  These are DRAFT pairs. SME review required before training.")


def train_dpo(config: DPOConfig):
    """Run DPO preference training."""
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from trl import DPOTrainer, DPOConfig as TRLDPOConfig
        from datasets import Dataset
    except ImportError as e:
        raise ImportError(f"Missing dependency: {e}. Run: pip install trl transformers datasets")

    print(f"Loading SFT model from: {config.sft_model_path}")
    model = AutoModelForCausalLM.from_pretrained(
        config.sft_model_path,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )
    tokenizer = AutoTokenizer.from_pretrained(config.sft_model_path, trust_remote_code=True)

    # Load DPO pairs
    pairs = []
    with open(config.train_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                pairs.append(json.loads(line))

    dataset = Dataset.from_list(pairs)
    split = dataset.train_test_split(test_size=0.1, seed=config.seed)

    training_args = TRLDPOConfig(
        output_dir=config.output_dir,
        num_train_epochs=config.num_train_epochs,
        per_device_train_batch_size=config.per_device_train_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        learning_rate=config.learning_rate,
        beta=config.beta,
        max_length=config.max_length,
        max_prompt_length=config.max_prompt_length,
        seed=config.seed,
        bf16=True,
        report_to="none",
    )

    trainer = DPOTrainer(
        model=model,
        ref_model=None,  # None = use SFT model as reference (memory efficient)
        args=training_args,
        train_dataset=split["train"],
        eval_dataset=split["test"],
        tokenizer=tokenizer,
    )

    print("Starting DPO training...")
    trainer.train()
    trainer.save_model(config.output_dir)
    tokenizer.save_pretrained(config.output_dir)
    print(f"✅ DPO model saved → {config.output_dir}")


def main():
    parser = argparse.ArgumentParser(description="ESGPilot DPO preference training")
    parser.add_argument("--sft-model", type=str, default=None)
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--train-file", type=str, default=None)
    parser.add_argument("--create-pairs", action="store_true", help="Write seed DPO pairs to file")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = DPOConfig()
    if args.sft_model:
        config.sft_model_path = args.sft_model
    if args.output:
        config.output_dir = args.output
    if args.train_file:
        config.train_file = args.train_file

    if args.create_pairs:
        create_dpo_dataset(config.train_file)
        return

    if args.dry_run:
        print(f"DPO config: {config}")
        return

    train_dpo(config)


if __name__ == "__main__":
    main()
