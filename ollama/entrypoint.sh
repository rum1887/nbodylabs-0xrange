#!/bin/sh
set -e

MODEL="${LEE_MODEL:-}"
KEY="${OPENAI_API_KEY:-}"

if [ -n "$MODEL" ] && [ -z "$KEY" ]; then
  echo "[ollama] background pull for model: $MODEL (first run can take a while; watch /tmp/pull.log)"
  ( sleep 3 && ollama pull "$MODEL" ) >/tmp/pull.log 2>&1 &
else
  echo "[ollama] skipping local model pull (OPENAI_API_KEY is set or LEE_MODEL is empty)"
fi

exec ollama serve