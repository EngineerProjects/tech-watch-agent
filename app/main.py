from __future__ import annotations

import argparse
import sys

import uvicorn

from app.config.settings import get_settings
from app.core.logging import configure_logging, get_logger
from app.scheduler.service import NewsletterOrchestrator


logger = get_logger(__name__)


def validate_config() -> list[str]:
    settings = get_settings()
    errors: list[str] = []

    if not settings.has_llm_credentials:
        errors.append("LLM_API_KEY is not configured")
    if not settings.newsletter_topics:
        errors.append("NEWSLETTER_TOPICS is empty")

    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="tech-watch-agent")
    parser.add_argument(
        "--mode",
        choices=["once", "schedule", "api"],
        default="once",
        help="Execution mode",
    )
    parser.add_argument(
        "--config-check",
        action="store_true",
        help="Validate configuration and exit",
    )
    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Generate the newsletter without sending an email",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    errors = validate_config()
    if errors:
        for error in errors:
            logger.error(error)
        if args.config_check or args.mode != "api":
            sys.exit(1)

    if args.config_check:
        logger.info("Configuration is valid")
        return

    orchestrator = NewsletterOrchestrator(settings=settings)

    if args.mode == "once":
        # `--no-email` is useful for validating crawl + agent output before
        # Gmail credentials are configured.
        result = orchestrator.run_once(send_email=not args.no_email)
        logger.info("Generated newsletter: %s", result.subject)
        return

    if args.mode == "schedule":
        orchestrator.start_scheduler()
        return

    uvicorn.run(
        "app.api.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
