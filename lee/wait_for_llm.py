"""Readiness probe for the configured LLM backend (and model, for local Ollama).

`probe_ready()` is a single non-blocking check. The web app polls it in the
background so the UI can come up immediately and show "downloading model"
instead of refusing connections while a multi-GB model pulls.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

DEADLINE_SECONDS = 900


def _base() -> str:
    return (os.environ.get("LEE_OPENAI_BASE_URL") or "http://ollama:11434/v1").rstrip("/")


def _get(url: str, timeout: int = 5):
    key = os.environ.get("OPENAI_API_KEY") or ""
    req = urllib.request.Request(url)
    if key and key not in ("", "ollama"):
        req.add_header("Authorization", "Bearer " + key)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def endpoint_ready() -> bool:
    try:
        return _get(_base() + "/models", timeout=5)[0] == 200
    except Exception:
        return False


def model_ready() -> bool:
    base = _base()
    if "ollama" not in base:
        return True   # remote OpenAI-style endpoints are ready when /models responds
    root = base[:-3] if base.endswith("/v1") else base   # Ollama's native API is at the root
    try:
        _, body = _get(root + "/api/tags", timeout=5)
        tags = json.loads(body)
    except Exception:
        return False
    wanted = os.environ.get("LEE_MODEL") or ""
    names = [m.get("name", "") for m in tags.get("models", [])]
    if ":" in wanted:
        return any(n == wanted for n in names)      # exact tag must match
    return any(n.split(":")[0] == wanted for n in names)


def probe_ready() -> bool:
    return endpoint_ready() and model_ready()


def wait_for(timeout: int = DEADLINE_SECONDS) -> bool:
    print(f"[lee] waiting for LLM backend at {_base()} "
          f"(model: {os.environ.get('LEE_MODEL', '?')})", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if probe_ready():
            print("[lee] LLM backend + model are ready.", flush=True)
            return True
        time.sleep(5)
    print("[lee] WARNING: LLM backend not ready within the timeout.", flush=True)
    return False


if __name__ == "__main__":
    wait_for()