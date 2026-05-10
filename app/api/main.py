from __future__ import annotations

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.config.settings import Settings, get_settings
from app.scheduler.service import NewsletterOrchestrator


class GenerateRequest(BaseModel):
    topics: list[str] | None = None
    send_email: bool = True


class ConfigResponse(BaseModel):
    newsletter_title: str
    topics: list[str]
    schedule_times: list[str]
    recipients_count: int = Field(ge=0)


def create_app(
    orchestrator: NewsletterOrchestrator | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    app = FastAPI(
        title="tech-watch-agent API",
        version="0.1.0",
        description="Minimal API for triggering and monitoring tech-watch-agent",
    )
    resolved_settings = settings or get_settings()
    resolved_orchestrator = orchestrator or NewsletterOrchestrator(resolved_settings)

    app.state.settings = resolved_settings
    app.state.orchestrator = resolved_orchestrator

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/status")
    async def status() -> dict[str, object]:
        runtime = app.state.orchestrator.runtime
        return {
            "state": runtime.state,
            "last_run_at": runtime.last_run_at,
            "last_error": runtime.last_error,
            "last_subject": runtime.last_subject,
            "last_article_count": runtime.last_article_count,
            "newsletters_sent": runtime.newsletters_sent,
            "last_delivery_success": runtime.last_delivery_success,
            "next_runs": app.state.orchestrator.get_schedule_info(),
        }

    @app.post("/generate")
    async def generate(payload: GenerateRequest, background_tasks: BackgroundTasks) -> dict[str, object]:
        try:
            # BackgroundTasks gives us a minimal fire-and-forget trigger without
            # introducing a queueing system before the product shape is validated.
            background_tasks.add_task(
                app.state.orchestrator.generate_newsletter,
                payload.topics,
                payload.send_email,
            )
            return {"accepted": True, "state": "queued"}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/generate/sync")
    async def generate_sync(payload: GenerateRequest) -> dict[str, object]:
        try:
            result = await app.state.orchestrator.generate_newsletter(
                topics=payload.topics,
                send_email=payload.send_email,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return {
            "subject": result.subject,
            "article_count": len(result.articles),
            "preview": result.markdown_content[:500],
        }

    @app.get("/history")
    async def history() -> dict[str, object]:
        return {"items": app.state.orchestrator.runtime.history}

    @app.get("/config", response_model=ConfigResponse)
    async def config() -> ConfigResponse:
        return ConfigResponse(
            newsletter_title=app.state.settings.newsletter_title,
            topics=app.state.settings.newsletter_topics,
            schedule_times=app.state.settings.schedule_times,
            recipients_count=len(app.state.settings.recipient_emails),
        )

    return app


app = create_app()
