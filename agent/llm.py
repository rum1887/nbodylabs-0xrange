"""Tiny OpenAI-compatible LLM wrapper.

Works with:
  - Ollama   (default: NBODY_OPENAI_BASE_URL=http://ollama:11434/v1)
  - OpenAI   (NBODY_OPENAI_BASE_URL=https://api.openai.com/v1 + OPENAI_API_KEY)
  - any other OpenAI-compatible server (vLLM, LM Studio, ...)

Errors are retried a few times because the Ollama model may still be pulling
when the first mission is launched.

Note: for qwen3 models on Ollama we disable their "thinking" mode on purpose.
Thinking makes the model deliberative and much more resistant to the goal
hijacking that this account data demonstrates.
"""
from __future__ import annotations

import os
import time

from openai import OpenAI


class LLMError(Exception):
    pass


def _effective_base_url() -> str:
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    base_url = (os.environ.get("NBODY_OPENAI_BASE_URL") or "").strip()
    if not base_url or (base_url in ("http://ollama:11434/v1", "http://ollama:11434") and api_key and api_key != "ollama"):
        if api_key and api_key != "ollama":
            return "https://api.openai.com/v1"
        return "http://ollama:11434/v1"
    return base_url


def _build_client():
    api_key = os.environ.get("OPENAI_API_KEY", "ollama")
    base_url = _effective_base_url()
    return OpenAI(base_url=base_url, api_key=api_key, timeout=300)


def chat(messages, tools=None, model=None, temperature=0.2, max_retries=4):
    model = model or os.environ.get("NBODY_MODEL") or "qwen3:8b"
    last_exc = None
    for attempt in range(max_retries):
        try:
            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }
            if tools:
                kwargs["tools"] = tools
            base = _effective_base_url()
            if tools and model.startswith("qwen3") and ("ollama" in base or ":11434" in base):
                # Ollama qwen3 models think by default; switch it off for this demo.
                kwargs["extra_body"] = {"think": False}
            return _build_client().chat.completions.create(**kwargs)
        except Exception as exc:  # connection refused, model still loading, 5xx...
            last_exc = exc
            time.sleep(min(30, 3 * (attempt + 1)))
    raise LLMError(f"LLM request failed after {max_retries} attempts: {last_exc}")