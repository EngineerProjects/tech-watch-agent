from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime

from app.agents.newsletter.graph import NewsletterWorkflow
from app.config.settings import Settings, get_settings
from app.core.logging import get_logger
from app.core.models import NewsletterRunResult
from app.delivery.gmail_client import GmailDeliveryClient
from app.delivery.newsletter_renderer import NewsletterRenderer
from app.services.article_service import ArticleService

try:
    import schedule
except ImportError:  # pragma: no cover - fallback for partial local environments
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


class NewsletterOrchestrator:
    def __init__(
        self,
        settings: Settings | None = None,
        article_service: ArticleService | None = None,
        workflow: NewsletterWorkflow | None = None,
        renderer: NewsletterRenderer | None = None,
        gmail_client: GmailDeliveryClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.article_service = article_service or ArticleService(self.settings)
        self.workflow = workflow or NewsletterWorkflow()
        self.renderer = renderer or NewsletterRenderer(self.settings)
        self.gmail_client = gmail_client or GmailDeliveryClient(self.settings)
        self.runtime = RuntimeStatus()
        self.is_running = False

    async def generate_newsletter(
        self,
        topics: list[str] | None = None,
        send_email: bool = True,
    ) -> NewsletterRunResult:
        # This method is the runtime seam of the V1: collect articles, run the
        # graph, render the newsletter, then optionally deliver it.
        self.runtime.state = "running"
        self.runtime.last_error = None

        try:
            articles = await self.article_service.fetch_articles_for_topics(topics)
            if not articles:
                raise ValueError("No relevant articles were collected")

            workflow_state = self.workflow.run(articles)
            markdown_content = workflow_state.get("final_newsletter", "").strip()
            if not markdown_content:
                raise ValueError("Newsletter workflow returned empty content")

            subject = self._extract_subject(markdown_content)
            html_content = self.renderer.render_html(markdown_content, subject)

            delivery_success = None
            if send_email and self.settings.has_email_delivery:
                delivery_success = self.gmail_client.send_email(
                    subject=subject,
                    body_html=html_content,
                    body_text=self.renderer.render_text(markdown_content),
                )

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
                delivery_success=delivery_success,
            )

            return NewsletterRunResult(
                subject=subject,
                markdown_content=markdown_content,
                html_content=html_content,
                articles=articles,
            )
        except Exception as exc:
            self.runtime.state = "error"
            self.runtime.last_error = str(exc)
            self.runtime.last_run_at = datetime.now().isoformat()
            self._append_history(status="failed", error=str(exc))
            logger.error("Newsletter generation failed: %s", exc)
            raise

    def run_once(self, topics: list[str] | None = None, send_email: bool = True) -> NewsletterRunResult:
        return asyncio.run(self.generate_newsletter(topics=topics, send_email=send_email))

    def start_scheduler(self) -> None:
        self._schedule_jobs()
        self.is_running = True
        self.runtime.state = "scheduled"
        logger.info("Scheduler started with times: %s", ", ".join(self.settings.schedule_times))

        try:
            # A simple blocking loop is enough for V1 CLI mode. We can swap this
            # layer later for Celery, Temporal or a dedicated worker process.
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
            asyncio.run(self.generate_newsletter())
        except Exception as exc:
            logger.error("Scheduled run failed: %s", exc)

    def _append_history(self, status: str, **extra: object) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "status": status,
        }
        entry.update(extra)
        self.runtime.history.append(entry)
        # Keep runtime history bounded until we persist runs in a database.
        self.runtime.history = self.runtime.history[-20:]

    def _extract_subject(self, newsletter_content: str) -> str:
        for line in newsletter_content.splitlines():
            lowered = line.lower()
            if "subject" not in lowered:
                continue
            if ":" not in line:
                continue
            subject = line.split(":", 1)[1].strip().strip('"').strip("'")
            if subject:
                return subject

        return f"{self.settings.newsletter_title} - {datetime.now().strftime('%B %d, %Y')}"
