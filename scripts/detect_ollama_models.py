#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from app.services.llm.model_catalog import discover_ollama_catalog


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect chat and embedding models exposed by an Ollama instance.")
    parser.add_argument("--base-url", default="http://localhost:11434/v1", help="Ollama base URL. Default: http://localhost:11434/v1")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = parser.parse_args()

    catalog = discover_ollama_catalog(args.base_url)
    payload = {
        "base_url": args.base_url,
        "chat_models": [item.to_dict() for item in catalog.get("chat_models", [])],
        "embedding_models": [item.to_dict() for item in catalog.get("embedding_models", [])],
        "error": catalog.get("error"),
    }
    print(json.dumps(payload, indent=2 if args.pretty else None))


if __name__ == "__main__":
    main()
