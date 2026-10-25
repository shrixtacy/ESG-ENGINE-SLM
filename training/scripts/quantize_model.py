"""
ESGPilot — Model Quantization Script.

Quantizes a fine-tuned model for production serving.
Supports:
  - AWQ 4-bit (for vLLM serving — recommended for production GPU)
  - GGUF Q4_K_M (for llama.cpp / Ollama — CPU/on-prem)

Usage:
    # AWQ quantization (for vLLM):
    python quantize_model.py --method awq --model training/checkpoints/dpo_v1 --output models/esgpilot-7b-awq

    # GGUF quantization (for llama.cpp/Ollama):
    python quantize_model.py --method gguf --model training/checkpoints/dpo_v1 --output models/esgpilot-7b-gguf
"""

import argparse
import os
import subprocess
import sys


def quantize_awq(model_path: str, output_path: str, quant_type: str = "w4-g128-asym"):
    """
    Quantize with AWQ (Activation-aware Weight Quantization).
    Produces a model compatible with vLLM.
    Requires: pip install autoawq
    """
    try:
        from awq import AutoAWQForCausalLM
        from transformers import AutoTokenizer
    except ImportError:
        print("autoawq not installed. Run: pip install autoawq")
        sys.exit(1)

    print(f"AWQ quantizing: {model_path} → {output_path}")

    model = AutoAWQForCausalLM.from_pretrained(
        model_path,
        device_map="auto",
        safetensors=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)

    quant_config = {
        "zero_point": True,
        "q_group_size": 128,
        "w_bit": 4,
        "version": "GEMM",
    }

    # Calibration dataset — use ESG Q&A examples
    calib_data = [
        "What is Scope 1 emissions in BRSR? How do I calculate it?",
        "Is water disclosure mandatory for top 1000 companies under BRSR?",
        "What are the Essential Indicators under Principle 6 of BRSR?",
        "How do I report CSR expenditure under Companies Act Section 135?",
        "What SDGs align with renewable energy initiatives?",
        "Explain the difference between Scope 2 location-based and market-based emissions.",
    ] * 10  # Repeat to ensure sufficient calibration

    model.quantize(tokenizer, quant_config=quant_config, calib_data=calib_data)

    os.makedirs(output_path, exist_ok=True)
    model.save_quantized(output_path)
    tokenizer.save_pretrained(output_path)
    print(f"✅ AWQ model saved → {output_path}")
    print("   Load with: vllm serve <output_path> --quantization awq")


def quantize_gguf(model_path: str, output_path: str, quant_type: str = "Q4_K_M"):
    """
    Convert to GGUF format for llama.cpp / Ollama.
    Requires llama.cpp built locally.
    """
    print(f"GGUF converting: {model_path} → {output_path}")
    print(f"Quantization: {quant_type}")

    # Step 1: Convert to GGUF (fp16)
    llama_cpp_path = os.environ.get("LLAMA_CPP_PATH", "./llama.cpp")
    convert_script = os.path.join(llama_cpp_path, "convert_hf_to_gguf.py")

    if not os.path.exists(convert_script):
        print(f"llama.cpp not found at {llama_cpp_path}")
        print("Please clone llama.cpp and set LLAMA_CPP_PATH env var:")
        print("  git clone https://github.com/ggerganov/llama.cpp")
        print("  export LLAMA_CPP_PATH=./llama.cpp")
        sys.exit(1)

    os.makedirs(output_path, exist_ok=True)
    gguf_fp16 = os.path.join(output_path, "model-fp16.gguf")

    # Convert HF → GGUF (fp16)
    cmd = [sys.executable, convert_script, model_path, "--outfile", gguf_fp16, "--outtype", "f16"]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    # Quantize GGUF
    quantize_bin = os.path.join(llama_cpp_path, "build", "bin", "llama-quantize")
    if not os.path.exists(quantize_bin):
        quantize_bin = os.path.join(llama_cpp_path, "quantize")

    gguf_quant = os.path.join(output_path, f"model-{quant_type.lower()}.gguf")
    cmd = [quantize_bin, gguf_fp16, gguf_quant, quant_type]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    # Clean up fp16
    os.remove(gguf_fp16)
    print(f"✅ GGUF model saved → {gguf_quant}")
    print(f"   Load with Ollama: ollama create esgpilot -f Modelfile")
    print(f"   Or with llama.cpp: ./llama-cli -m {gguf_quant} -p 'Your prompt here'")


def main():
    parser = argparse.ArgumentParser(description="ESGPilot model quantization")
    parser.add_argument("--method", choices=["awq", "gguf"], required=True)
    parser.add_argument("--model", required=True, help="Path to fine-tuned model")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--quant-type", default=None,
                        help="AWQ: 'w4-g128-asym' | GGUF: 'Q4_K_M' (default)")
    args = parser.parse_args()

    if args.method == "awq":
        quantize_awq(args.model, args.output, args.quant_type or "w4-g128-asym")
    elif args.method == "gguf":
        quantize_gguf(args.model, args.output, args.quant_type or "Q4_K_M")


if __name__ == "__main__":
    main()
