"""
Orchestrator-aware scheduler service.

This module replaces the legacy NewsletterOrchestrator with a unified
orchestrator that supports both V1 (newsletter) and V2 (full research pipeline)
execution modes. The orchestrator is the central coordinator for all tasks.

V2 mode: Full orchestrator agent with plan -> parallel research -> analysis -> synthesis -> email
V1 mode: Legacy newsletter workflow (backwards compatible)

Modes:
- Autonomous (default for scheduler): Fully automated, no human approval
- Interactive (default for API): Human-in-the-loop for approval/revision
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.agents.orchestrator.agent import OrchestratorAgent, create_orchestrator_agent
from app.agents.orchestrator.config import OrchestratorConfig
from app.agents.newsletter.graph import NewsletterWorkflow
from app.config.settings import Settings, get_settings
from app.core.logging import get_logger
from app.core.models import NewsletterRunResult
from app.delivery.service import ReportDeliveryService
from app.delivery.gmail_client import GmailDeliveryClient
from app.delivery.newsletter_renderer import NewsletterRenderer
from app.services.article_service import ArticleService


try:
    import schedule
except ImportError:

    class _FallbackJob:
        def __init__(self) -> None:
            self.next_run = "schedule package not installed"

    class _FallbackEvery:
        @property
        def day(self) -> "_FallbackEvery":
            return self

        def at(self, _: str) -> "_FallbackEvery":
            return self

        def do(self, __):
            job = _FallbackJob()
            _FALLBACK_JOBS.append(job)
            return job

    class _FallbackScheduleModule:
        jobs = []

        @staticmethod
        def every() -> _FallbackEvery:
            return _FallbackEvery()

        @staticmethod
        def clear() -> None:
            _FALLBACK_JOBS.clear()
            _FallbackScheduleModule.jobs = _FALLBACK_JOBS

        @staticmethod
        def run_pending() -> None:
            return None

    _FALLBACK_JOBS: list[_FallbackJob] = []
    _FallbackScheduleModule.jobs = _FALLBACK_JOBS
    schedule = _FallbackScheduleModule()


logger = get_logger(__name__)


@dataclass(slots=True)
class RuntimeStatus:
    state: str = "idle"
    last_run_at: str | None = None
    last_error: str | None = None
    newsletters_sent: int = 0
    last_subject: str | None = None
    last_article_count: int = 0
    last_delivery_success: bool | None = None
    history: list[dict[str, object]] = field(default_factory=list)
    mode: str = "v2"


def create_autonomous_config(settings: Settings) -> OrchestratorConfig:
    """Create config for fully autonomous execution (scheduler mode).

    Autonomous mode:
    - No human approval required
    - Automatic retry with quality-based routing
    - Checkpointing enabled for resume capability
    """
    return OrchestratorConfig(
        autonomous=True,
        human_approval_enabled=False,
        send_email=True,
        enable_checkpointing=True,
        checkpoint_backend="memory",
        max_iterations=5,
    )


def create_interactive_config(settings: Settings) -> OrchestratorConfig:
    """Create config for interactive/chat mode (API mode).

    Interactive mode:
    - Human approval required for final output
    - Quality threshold determines auto-approval
    - Checkpointing for session persistence
    """
    return OrchestratorConfig(
        autonomous=False,
        human_approval_enabled=True,
        send_email=True,
        enable_checkpointing=True,
        checkpoint_backend="memory",
        approval_threshold=0.7,
        max_iterations=3,
    )


class OrchestratorScheduler:
    """Unified orchestrator scheduler supporting V1 (newsletter) and V2 (research) modes.

    V2 mode uses the new OrchestratorAgent with plan-based parallel research.
    V1 mode uses the legacy NewsletterWorkflow for backwards compatibility.

    Usage:
        scheduler = OrchestratorScheduler(mode="v2")
        result = scheduler.run_once(task="Research AI trends")
        scheduler.start_scheduler()
    """

    def __init__(
        self,
        mode: str = "v2",
        settings: Optional[Settings] = None,
        orchestrator_agent: Optional[OrchestratorAgent] = None,
        newsletter_workflow: Optional[NewsletterWorkflow] = None,
        article_service: Optional[ArticleService] = None,
        renderer: Optional[NewsletterRenderer] = None,
        gmail_client: Optional[GmailDeliveryClient] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.mode = mode
        self.runtime = RuntimeStatus(mode=mode)

        self._orchestrator = orchestrator_agent
        self._newsletter_workflow = newsletter_workflow
        self._article_service = article_service
        self._renderer = renderer or NewsletterRenderer(self.settings)
        self._gmail_client = gmail_client or GmailDeliveryClient(self.settings)
        self._delivery_service = ReportDeliveryService(
            settings=self.settings,
            renderer=self._renderer,
            gmail_client=self._gmail_client,
        )
        self.is_running = False

    async def setup(self, autonomous: bool = True) -> None:
        """Lazily initialize agents.

        Args:
            autonomous: If True (default for scheduler), use fully autonomous mode.
                       If False, use interactive mode with human approval.
        """
        if self.mode == "v2" and self._orchestrator is None:
            if autonomous:
                config = create_autonomous_config(self.settings)
                logger.info("Using AUTONOMOUS mode for scheduler")
            else:
                config = create_interactive_config(self.settings)
                logger.info("Using INTERACTIVE mode with human approval")

            self._orchestrator = OrchestratorAgent(config=config, settings=self.settings)
            await self._orchestrator.setup()
            logger.info("OrchestratorAgent initialized (V2 mode)")
        elif self.mode == "v1" and self._newsletter_workflow is None:
            self._newsletter_workflow = NewsletterWorkflow()
            logger.info("NewsletterWorkflow initialized (V1 mode)")

    async def run_task(
        self,
        task: Optional[str] = None,
        topics: Optional[list[str]] = None,
        send_email: bool = True,
        autonomous: bool = True,
        watch_context: Optional[object] = None,
        recipients_override: Optional[list[str]] = None,
    ) -> dict:
        """Run a research task through the orchestrator.

        V2: Uses OrchestratorAgent with plan-based parallel research.
        V1: Uses legacy newsletter workflow.

        Args:
            task: The research task description
            topics: Optional list of topics to focus on
            send_email: Whether to send email after completion
            autonomous: If True, runs fully automated (no human approval).
                      If False, requires human approval before sending email.
            recipients_override: Optional explicit recipients for this run.
        """
        await self.setup(autonomous=autonomous)
        start = datetime.now()

        self.runtime.state = "running"
        self.runtime.last_error = None

        if self.mode == "v2":
            return await self._run_v2(task or "", topics, send_email, start, watch_context, recipients_override)
        else:
            return await self._run_v1(topics, send_email, start, recipients_override)

    async def _run_v2(
        self,
        task: str,
        topics: Optional[list[str]],
        send_email: bool,
        start: datetime,
        watch_context: Optional[object] = None,
        recipients_override: Optional[list[str]] = None,
    ) -> dict:
        if not task:
            task = f"Weekly tech watch: {', '.join(topics or self.settings.newsletter_topics)}"

        payload: dict = {
            "task": task,
            "topics": topics or self.settings.newsletter_topics,
            "send_email": send_email,
        }
        if watch_context is not None:
            payload["watch_context"] = watch_context
        if recipients_override is not None:
            payload["email_recipients"] = recipients_override

        try:
            result = await self._orchestrator.execute(payload)

            execution_time = (datetime.now() - start).total_seconds()

            if result.success:
                output = result.output or {}
                report = output.get("report", "")
                subject = self._extract_subject(report) if report else "Tech Watch Report"
                research_count = len(output.get("research_results", []))
                plan_count = len(output.get("plan", []))

                self.runtime.state = "idle"
                self.runtime.last_run_at = datetime.now().isoformat()
                self.runtime.last_subject = subject
                self.runtime.last_article_count = research_count
                self.runtime.last_delivery_success = output.get("email_sent", False)
                if output.get("email_sent"):
                    self.runtime.newsletters_sent += 1

                self._append_history(
                    status="completed",
                    subject=subject,
                    article_count=research_count,
                    plan_steps=plan_count,
                    mode="v2",
                    execution_time=execution_time,
                )

                return {
                    "success": True,
                    "session_id": output.get("session_id") or (str(result.session_id) if result.session_id else None),
                    "report": report,
                    "subject": subject,
                    "email_sent": output.get("email_sent", False),
                    "research_results": output.get("research_results", []),
                    "plan": output.get("plan", []),
                    "execution_time": execution_time,
                }
            else:
                self.runtime.state = "error"
                self.runtime.last_error = "; ".join(result.errors)
                self.runtime.last_run_at = datetime.now().isoformat()
                self._append_history(status="failed", error=result.errors, mode="v2")
                logger.error("V2 orchestrator failed: %s", result.errors)
                return {
                    "success": False,
                    "errors": result.errors,
                    "execution_time": (datetime.now() - start).total_seconds(),
                }

        except Exception as exc:
            logger.error("V2 orchestrator exception: %s", exc)
            self.runtime.state = "error"
            self.runtime.last_error = str(exc)
            self.runtime.last_run_at = datetime.now().isoformat()
            self._append_history(status="failed", error=str(exc), mode="v2")
            return {
                "success": False,
                "errors": [str(exc)],
                "execution_time": (datetime.now() - start).total_seconds(),
            }

    async def _run_v1(
        self,
        topics: Optional[list[str]],
        send_email: bool,
        start: datetime,
        recipients_override: Optional[list[str]] = None,
    ) -> dict:
        try:
            if self._article_service is None:
                self._article_service = ArticleService(self.settings)

            articles = await self._article_service.fetch_articles_for_topics(topics)
            if not articles:
                raise ValueError("No relevant articles were collected")

            workflow_state = self._newsletter_workflow.run(articles)
            markdown_content = workflow_state.get("final_newsletter", "").strip()
            if not markdown_content:
                raise ValueError("Newsletter workflow returned empty content")

            subject = self._extract_subject(markdown_content)
            delivery = self._delivery_service.deliver(
                report=markdown_content,
                subject=subject,
                send=send_email,
                recipients=recipients_override,
            )
            delivery_success = delivery.sent if send_email else False

            execution_time = (datetime.now() - start).total_seconds()

            self.runtime.state = "idle"
            self.runtime.last_run_at = datetime.now().isoformat()
            self.runtime.last_subject = subject
            self.runtime.last_article_count = len(articles)
            self.runtime.last_delivery_success = delivery_success
            if delivery_success:
                self.runtime.newsletters_sent += 1

            self._append_history(
                status="completed",
                subject=subject,
                article_count=len(articles),
                mode="v1",
                execution_time=execution_time,
            )

            return {
                "success": True,
                "report": markdown_content,
                "subject": subject,
                "email_sent": bool(delivery_success),
                "execution_time": execution_time,
            }

        except Exception as exc:
            logger.error("V1 newsletter failed: %s", exc)
            self.runtime.state = "error"
            self.runtime.last_error = str(exc)
            self.runtime.last_run_at = datetime.now().isoformat()
            self._append_history(status="failed", error=str(exc), mode="v1")
            return {
                "success": False,
                "errors": [str(exc)],
                "execution_time": (datetime.now() - start).total_seconds(),
            }

    def run_once(
        self,
        task: Optional[str] = None,
        topics: Optional[list[str]] = None,
        send_email: bool = True,
    ) -> dict:
        """Sync wrapper for run_task."""
        return asyncio.run(self.run_task(task=task, topics=topics, send_email=send_email))

    def start_scheduler(self) -> None:
        self._schedule_jobs()
        self.is_running = True
        self.runtime.state = "scheduled"
        logger.info(
            "Scheduler started (mode=%s) with times: %s",
            self.mode,
            ", ".join(self.settings.schedule_times),
        )

        try:
            while self.is_running:
                schedule.run_pending()
                time.sleep(30)
        finally:
            self.stop_scheduler()

    def stop_scheduler(self) -> None:
        self.is_running = False
        schedule.clear()
        if self.runtime.state == "scheduled":
            self.runtime.state = "idle"

    def get_schedule_info(self) -> list[str]:
        return [str(job.next_run) for job in schedule.jobs if job.next_run is not None]

    def _schedule_jobs(self) -> None:
        schedule.clear()
        for schedule_time in self.settings.schedule_times:
            schedule.every().day.at(schedule_time).do(self._run_scheduled_job)

    def _run_scheduled_job(self) -> None:
        try:
            asyncio.run(self.run_task())
        except Exception as exc:
            logger.error("Scheduled run failed: %s", exc)

    def _append_history(self, status: str, **extra: object) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "status": status,
        }
        entry.update(extra)
        self.runtime.history.append(entry)
        self.runtime.history = self.runtime.history[-50:]

    @staticmethod
    def _extract_subject(report: str) -> str:
        for line in report.split("\n"):
            lowered = line.lower().strip()
            if lowered.startswith("# "):
                return line[2:].strip()
            if lowered.startswith("## "):
                return line[3:].strip()
            if "subject:" in lowered:
                parts = line.split(":", 1)
                if len(parts) > 1 and parts[1].strip():
                    return parts[1].strip()
        return "Tech Watch Report"
