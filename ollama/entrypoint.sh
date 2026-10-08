#!/bin/sh
set -e

MODEL="${NBODY_MODEL:-}"
KEY="${OPENAI_API_KEY:-}"
BASE="${NBODY_OPENAI_BASE_URL:-}"

is_hosted=0
if [ -n "$BASE" ] && [ "$BASE" != "http://ollama:11434/v1" ] && [ "$BASE" != "http://ollama:11434" ]; then
  is_hosted=1
fi
if [ -n "$KEY" ] && [ "$KEY" != "ollama" ]; then
  is_hosted=1
fi

if [ "$is_hosted" -eq 1 ]; then
  echo "[ollama] hosted model configured (NBODY_OPENAI_BASE_URL=$BASE). Skipping local model pull."
elif [ -n "$MODEL" ]; then
  echo "[ollama] background pull for model: $MODEL (first run can take a while; watch /tmp/pull.log)"
  ( sleep 3 && ollama pull "$MODEL" ) >/tmp/pull.log 2>&1 &
else
  echo "[ollama] skipping local model pull (NBODY_MODEL is empty)"
fi

exec ollama serve