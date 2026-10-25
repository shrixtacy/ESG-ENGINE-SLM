"""
ESGPilot — LoRA/QLoRA Fine-Tuning Script.

Stage 1: SFT via LoRA on Qwen2.5-7B-Instruct (or Llama-3.1-8B-Instruct).
Uses the TRL SFTTrainer + Unsloth for fast 4-bit training on a single GPU.

Usage:
    python train_lora.py --config configs/sft_qwen7b.yaml

Requirements:
    pip install trl unsloth peft transformers datasets accelerate bitsandbytes

Hardware:
    Minimum: 24 GB VRAM (RTX 3090 / 4090 / A10 / L4)
    Recommended: A10G or L4 (24 GB) for 7B 4-bit QLoRA

Training time:
    ~2–4 hours for 10k examples on A10G with r=16, batch=4, 3 epochs
"""

import argparse
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

# ──────────────────────────────────────────────
# Config Dataclass
# ──────────────────────────────────────────────

@dataclass
class TrainingConfig:
    """Training configuration loaded from YAML."""
    # Model
    model_name: str = "Qwen/Qwen2.5-7B-Instruct"
    load_in_4bit: bool = True
    dtype: str = "bfloat16"  # bfloat16 | float16

    # LoRA
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    target_modules: list = field(default_factory=lambda: [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ])

    # Training
    train_file: str = "training/data/sft_reviewed.jsonl"
    output_dir: str = "training/checkpoints/lora_v1"
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 4
    gradient_accumulation_steps: int = 4
    learning_rate: float = 2e-4
    warmup_ratio: float = 0.05
    lr_scheduler_type: str = "cosine"
    weight_decay: float = 0.01
    max_seq_length: int = 4096
    seed: int = 42

    # Logging
    logging_steps: int = 10
    save_steps: int = 100
    eval_steps: int = 100
    report_to: str = "none"  # "wandb" | "tensorboard" | "none"

    # HuggingFace
    push_to_hub: bool = False
    hub_model_id: str = ""

    @classmethod
    def from_yaml(cls, path: str) -> "TrainingConfig":
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})


# ──────────────────────────────────────────────
# Dataset Loader
# ──────────────────────────────────────────────

def load_jsonl_dataset(filepath: str):
    """Load JSONL SFT dataset."""
    try:
        from datasets import Dataset
    except ImportError:
        raise ImportError("Run: pip install datasets")

    examples = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                ex = json.loads(line)
                # Filter out unreviewed in strict mode
                if ex.get("metadata", {}).get("sme_reviewed") is False:
                    continue  # Skip unreviewed examples in production
                examples.append(ex)

    print(f"Loaded {len(examples)} reviewed examples from {filepath}")
    return Dataset.from_list(examples)


def format_messages(example: dict) -> dict:
    """Format messages to chat template string."""
    messages = example.get("messages", [])
    # Build a simple text representation; tokenizer.apply_chat_template handles this properly
    text = ""
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "system":
            text += f"<|system|>\n{content}\n"
        elif role == "user":
            text += f"<|user|>\n{content}\n"
        elif role == "assistant":
            text += f"<|assistant|>\n{content}\n"
    return {"text": text}


# ──────────────────────────────────────────────
# Main Training Function
# ──────────────────────────────────────────────

def train(config: TrainingConfig):
    """Run LoRA fine-tuning."""
    print(f"Loading model: {config.model_name}")
    print(f"4-bit quantization: {config.load_in_4bit}")
    print(f"LoRA rank: {config.lora_r}, alpha: {config.lora_alpha}")

    # Try Unsloth first (faster), fall back to standard PEFT
    use_unsloth = False
    try:
        from unsloth import FastLanguageModel
        use_unsloth = True
        print("Using Unsloth for optimized training")
    except ImportError:
        print("Unsloth not available — using standard PEFT + BitsAndBytes")

    if use_unsloth:
        from unsloth import FastLanguageModel
        import torch

        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=config.model_name,
            max_seq_length=config.max_seq_length,
            dtype=None,  # Auto-detect
            load_in_4bit=config.load_in_4bit,
        )

        model = FastLanguageModel.get_peft_model(
            model,
            r=config.lora_r,
            target_modules=config.target_modules,
            lora_alpha=config.lora_alpha,
            lora_dropout=config.lora_dropout,
            bias="none",
            use_gradient_checkpointing="unsloth",
            random_state=config.seed,
        )

    else:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from peft import LoraConfig, get_peft_model, TaskType

        bnb_config = None
        if config.load_in_4bit:
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
            )

        model = AutoModelForCausalLM.from_pretrained(
            config.model_name,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
        )
        tokenizer = AutoTokenizer.from_pretrained(config.model_name, trust_remote_code=True)

        lora_config = LoraConfig(
            r=config.lora_r,
            lora_alpha=config.lora_alpha,
            target_modules=config.target_modules,
            lora_dropout=config.lora_dropout,
            bias="none",
            task_type=TaskType.CAUSAL_LM,
        )
        model = get_peft_model(model, lora_config)
        model.print_trainable_parameters()

    # Load dataset
    if not os.path.exists(config.train_file):
        raise FileNotFoundError(
            f"Training data not found: {config.train_file}\n"
            "Run generate_sft_data.py --save first, then have SME review examples."
        )

    dataset = load_jsonl_dataset(config.train_file)
    dataset = dataset.map(format_messages)

    # Split train/eval (90/10)
    split = dataset.train_test_split(test_size=0.1, seed=config.seed)
    train_dataset = split["train"]
    eval_dataset = split["test"]

    print(f"Train: {len(train_dataset)} | Eval: {len(eval_dataset)}")

    # TRL SFTTrainer
    from trl import SFTTrainer, SFTConfig

    training_args = SFTConfig(
        output_dir=config.output_dir,
        num_train_epochs=config.num_train_epochs,
        per_device_train_batch_size=config.per_device_train_batch_size,
        per_device_eval_batch_size=config.per_device_train_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        learning_rate=config.learning_rate,
        warmup_ratio=config.warmup_ratio,
        lr_scheduler_type=config.lr_scheduler_type,
        weight_decay=config.weight_decay,
        fp16=False,
        bf16=True,
        logging_steps=config.logging_steps,
        save_steps=config.save_steps,
        eval_strategy="steps",
        eval_steps=config.eval_steps,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        report_to=config.report_to,
        seed=config.seed,
        dataset_text_field="text",
        max_seq_length=config.max_seq_length,
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        args=training_args,
    )

    # Train
    print("\nStarting training...")
    trainer.train()

    # Save
    os.makedirs(config.output_dir, exist_ok=True)
    trainer.save_model(config.output_dir)
    tokenizer.save_pretrained(config.output_dir)
    print(f"\n✅ Model saved → {config.output_dir}")

    if config.push_to_hub and config.hub_model_id:
        trainer.push_to_hub(config.hub_model_id)
        print(f"✅ Pushed to HuggingFace Hub: {config.hub_model_id}")


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ESGPilot LoRA fine-tuning")
    parser.add_argument("--config", type=str, help="Path to YAML config file")
    parser.add_argument("--model", type=str, default=None, help="Override model name")
    parser.add_argument("--train-file", type=str, default=None, help="Override train file path")
    parser.add_argument("--output-dir", type=str, default=None, help="Override output dir")
    parser.add_argument("--dry-run", action="store_true", help="Print config and exit")
    args = parser.parse_args()

    if args.config:
        config = TrainingConfig.from_yaml(args.config)
    else:
        config = TrainingConfig()

    # CLI overrides
    if args.model:
        config.model_name = args.model
    if args.train_file:
        config.train_file = args.train_file
    if args.output_dir:
        config.output_dir = args.output_dir

    print("\n=== ESGPilot LoRA Training Config ===")
    print(f"  Model: {config.model_name}")
    print(f"  Train file: {config.train_file}")
    print(f"  Output: {config.output_dir}")
    print(f"  LoRA r={config.lora_r}, alpha={config.lora_alpha}")
    print(f"  Epochs: {config.num_train_epochs}, LR: {config.learning_rate}")
    print("=====================================\n")

    if args.dry_run:
        print("Dry run — exiting without training.")
        return

    train(config)


if __name__ == "__main__":
    main()
