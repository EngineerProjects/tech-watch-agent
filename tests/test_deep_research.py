"""
Smoke test for the DeepResearch workflow.

Runs a minimal research cycle to validate the full pipeline works end-to-end:
 - LLM connectivity
 - Web search fallback chain (Tavily → DuckDuckGo)
 - Research brief generation
 - Supervisor → researcher loop
 - Final report generation

Usage:
    uv run python test_deep_research.py
    uv run python test_deep_research.py --model mistralai/mistral-7b-instruct:free
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

# --- Load .env FIRST so all downstream imports see the vars ---
from dotenv import load_dotenv
load_dotenv(override=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Test DeepResearch agent end-to-end.")
    p.add_argument("--model", default=None, help="Override LLM_MODEL for this run.")
    p.add_argument(
        "--query",
        default="What are the latest advancements in small language models (SLMs) for edge devices?",
        help="Research query.",
    )
    p.add_argument("--depth", default="shallow", choices=["shallow", "medium", "deep"])
    p.add_argument("--max-iter", type=int, default=2, help="Max researcher iterations (keep low for smoke test).")
    return p.parse_args()


async def main() -> None:
    args = parse_args()

    # Allow CLI to override the model without touching .env
    if args.model:
        os.environ["LLM_MODEL"] = args.model
        print(f"[override] LLM_MODEL = {args.model}")

    # Import AFTER env is loaded so lru_cache picks up the right values.
    # If model was overridden, bust the cache so the new value is used.
    from app.config.settings import get_settings
    from app.core.logging import configure_logging
    if args.model:
        get_settings.cache_clear()

    from app.agents.deep_research.agent import create_deep_research_agent
    from app.agents.deep_research.config import DeepResearchConfig

    settings = get_settings()
    configure_logging(level="DEBUG")
    print(f"LLM Primary  : {settings.llm_model}")
    print(f"LLM Fallbacks: {settings.llm_fallback_models}")
    print(f"Provider     : {settings.llm_provider}")

    # Tight config for smoke test — avoid burning too many API calls
    config = DeepResearchConfig(
        name="smoke_test",
        research_model=settings.llm_model,
        max_researcher_iterations=args.max_iter,
        max_concurrent_research_units=1,   # sequential to avoid concurrent 429s
        max_react_tool_calls=2,
        allow_clarification=False,          # skip the clarification round-trip
        research_depth=args.depth,
        final_report_model_max_tokens=1500,
    )

    agent = create_deep_research_agent(config=config, settings=settings)
    await agent.setup()

    print(f"\nQuery: {args.query!r}\n" + "=" * 60)
    result = await agent.execute(args.query)

    print("=" * 60)
    if result.success:
        report: str = result.output.get("report", "")
        print("✅  SUCCESS")
        print(f"Report length : {len(report):,} chars")
        print(f"Notes count   : {result.metadata.get('notes_count', 0)}")
        print(f"Brief length  : {result.metadata.get('research_brief_length', 0)}")
        print("\n--- Report snippet (first 800 chars) ---")
        print(report[:800])
        print("...")
    else:
        print("❌  FAILED")
        print("Errors:", result.errors)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
