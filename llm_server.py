"""
ESGPilot — Minimal OpenAI-compatible LLM server using llama-cpp-python.
Runs Qwen2.5-0.5B-Instruct GGUF on CPU.

Endpoints:
  GET  /v1/models
  POST /v1/chat/completions   (OpenAI-compatible, used by ESGPilot)
  GET  /api/tags              (Ollama-compatible, used by health check)

Usage:
    python llm_server.py
    
Listens on http://127.0.0.1:11434
"""

import json
import time
import uuid
from typing import List, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn

MODEL_PATH = "C:/Users/shriy/.ollama/gguf/qwen2.5-0.5b-instruct-q4_k_m.gguf"
MODEL_NAME = "qwen2.5:0.5b"

app = FastAPI(title="ESGPilot LLM Server")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Load model once at startup ────────────────────────────
_llm = None

def get_llm():
    global _llm
    if _llm is None:
        from llama_cpp import Llama
        print(f"Loading model: {MODEL_PATH}")
        _llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=4096,
            n_threads=4,
            n_gpu_layers=0,   # CPU only
            verbose=False,
            chat_format="chatml",
        )
        print("Model loaded.")
    return _llm


# ── Schemas ───────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str = MODEL_NAME
    messages: List[ChatMessage]
    temperature: float = 0.1
    max_tokens: int = 1024
    stream: bool = False


# ── Routes ────────────────────────────────────────────────

@app.get("/v1/models")
def list_models():
    return {
        "object": "list",
        "data": [{"id": MODEL_NAME, "object": "model", "created": int(time.time()), "owned_by": "local"}]
    }

@app.get("/api/tags")
def ollama_tags():
    """Ollama-compatible tags endpoint (used by health check)."""
    return {
        "models": [{"name": MODEL_NAME, "size": 491520000}]
    }

@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_NAME}

@app.post("/v1/chat/completions")
def chat_completions(req: ChatRequest):
    llm = get_llm()

    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    if req.stream:
        def generate():
            result_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
            for chunk in llm.create_chat_completion(
                messages=messages,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
                stream=True,
            ):
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                finish = chunk.get("choices", [{}])[0].get("finish_reason")
                data = {
                    "id": result_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": req.model,
                    "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": finish}],
                }
                yield f"data: {json.dumps(data)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    result = llm.create_chat_completion(
        messages=messages,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        stream=False,
    )

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": result["choices"][0]["message"]["content"],
            },
            "finish_reason": result["choices"][0].get("finish_reason", "stop"),
        }],
        "usage": result.get("usage", {}),
    }


if __name__ == "__main__":
    # Pre-load model before serving
    print("Pre-loading model...")
    get_llm()
    print("Starting LLM server on http://127.0.0.1:11434")
    uvicorn.run(app, host="127.0.0.1", port=11434, log_level="warning")
