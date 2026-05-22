#!/bin/sh
set -eu

OLLAMA_HOST="${OLLAMA_HOST:-http://ollama:11434}"
export OLLAMA_HOST

models="llama3.2 nemotron-3-nano embeddinggemma all-minilm"

echo "Waiting for Ollama at ${OLLAMA_HOST}..."
until ollama list >/dev/null 2>&1; do
  sleep 2
 done

echo "Pulling Ollama models..."
for model in $models; do
  echo "-> $model"
  ollama pull "$model"
done

echo "Ollama model pull complete."
