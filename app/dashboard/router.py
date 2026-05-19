from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Optional

import markdown2
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config.settings import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
router = APIRouter(prefix="/ui", tags=["Dashboard"])


def _md(text: str) -> str:
    if not text:
        return ""
    return markdown2.markdown(
        text,
        extras=["fenced-code-blocks", "tables", "strike", "header-ids"],
    )


async def _get_stats() -> dict[str, Any]:
    try:
        from sqlalchemy import func, select

        from app.db.base import async_session_factory
        from app.db.models import Article, NewsletterRun, ResearchSession

        async with async_session_factory() as session:
            articles = await session.scalar(select(func.count()).select_from(Article)) or 0
            runs = await session.scalar(select(func.count()).select_from(NewsletterRun)) or 0
            total_sessions = await session.scalar(select(func.count()).select_from(ResearchSession)) or 0
            completed = (
                await session.scalar(
                    select(func.count())
                    .select_from(ResearchSession)
                    .where(ResearchSession.status == "completed")
                )
                or 0
            )
        return {
            "articles": articles,
            "newsletter_runs": runs,
            "sessions": total_sessions,
            "completed_sessions": completed,
            "db_ok": True,
        }
    except Exception as exc:
        logger.warning("Stats unavailable: %s", exc)
        return {
            "articles": "—",
            "newsletter_runs": "—",
            "sessions": "—",
            "completed_sessions": "—",
            "db_ok": False,
        }


async def _get_sessions(limit: int = 50, status: Optional[str] = None) -> list[dict]:
    try:
        from app.db.base import async_session_factory
        from app.db.repositories import ResearchSessionRepository

        async with async_session_factory() as db:
            repo = ResearchSessionRepository(db)
            rows = await repo.get_by_status(status, limit) if status else await repo.get_recent(None, limit)
            return [
                {
                    "id": str(s.id),
                    "brief": (s.research_brief[:90] + "…") if len(s.research_brief) > 90 else s.research_brief,
                    "status": s.status,
                    "phase": s.phase or "—",
                    "created_at": s.created_at.strftime("%d/%m %H:%M") if s.created_at else "—",
                    "completed_at": s.completed_at.strftime("%d/%m %H:%M") if s.completed_at else "—",
                }
                for s in rows
            ]
    except Exception as exc:
        logger.warning("Sessions unavailable: %s", exc)
        return []


async def _get_newsletter_history(limit: int = 30) -> list[dict]:
    try:
        from app.db.base import async_session_factory
        from app.db.repositories import NewsletterRunRepository

        async with async_session_factory() as db:
            repo = NewsletterRunRepository(db)
            rows = await repo.get_recent(None, limit)
            return [
                {
                    "id": str(r.id),
                    "subject": r.subject or "—",
                    "status": r.status,
                    "articles_count": r.articles_count or 0,
                    "delivery_success": r.delivery_success,
                    "started_at": r.started_at.strftime("%d/%m %H:%M") if r.started_at else "—",
                }
                for r in rows
            ]
    except Exception as exc:
        logger.warning("Newsletter history unavailable: %s", exc)
        return []


# ── Pages ──────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request) -> HTMLResponse:
    settings = get_settings()
    stats = await _get_stats()
    sessions = await _get_sessions(limit=6)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "stats": stats,
            "sessions": sessions,
            "default_topics": ", ".join(settings.newsletter_topics),
            "active": "home",
        },
    )


@router.get("/sessions", response_class=HTMLResponse)
async def sessions_page(request: Request, status: Optional[str] = None) -> HTMLResponse:
    sessions = await _get_sessions(limit=50, status=status)
    return templates.TemplateResponse(
        "sessions.html",
        {
            "request": request,
            "sessions": sessions,
            "current_status": status or "all",
            "active": "sessions",
        },
    )


@router.get("/sessions/{session_id}", response_class=HTMLResponse)
async def session_detail(request: Request, session_id: str) -> HTMLResponse:
    try:
        from app.db.base import async_session_factory
        from app.db.repositories import ResearchSessionRepository

        async with async_session_factory() as db:
            repo = ResearchSessionRepository(db)
            s = await repo.get_by_id(uuid.UUID(session_id))
            if not s:
                return HTMLResponse("<p>Session introuvable.</p>", status_code=404)

            session_data = {
                "id": str(s.id),
                "brief": s.research_brief,
                "status": s.status,
                "phase": s.phase or "—",
                "plan": s.plan or [],
                "research_results": s.research_results or [],
                "report_html": _md(s.final_report or ""),
                "has_report": bool(s.final_report),
                "created_at": s.created_at.strftime("%d/%m/%Y %H:%M") if s.created_at else "—",
                "completed_at": s.completed_at.strftime("%d/%m/%Y %H:%M") if s.completed_at else "—",
                "iterations": s.iterations_count or 0,
                "plan_version": s.plan_version or 1,
            }
    except Exception as exc:
        logger.error("Session detail failed: %s", exc)
        return HTMLResponse(f"<p>Erreur : {exc}</p>", status_code=500)

    return templates.TemplateResponse(
        "session_detail.html",
        {"request": request, "s": session_data, "active": "sessions"},
    )


@router.get("/newsletter", response_class=HTMLResponse)
async def newsletter_page(request: Request) -> HTMLResponse:
    settings = get_settings()
    history = await _get_newsletter_history()
    return templates.TemplateResponse(
        "newsletter.html",
        {
            "request": request,
            "history": history,
            "default_topics": ", ".join(settings.newsletter_topics),
            "active": "newsletter",
        },
    )


# ── HTMX partials ──────────────────────────────────────────────────────────────

@router.get("/_stats", response_class=HTMLResponse)
async def stats_partial(request: Request) -> HTMLResponse:
    stats = await _get_stats()
    return templates.TemplateResponse(
        "partials/stats.html", {"request": request, "stats": stats}
    )


@router.get("/_sessions", response_class=HTMLResponse)
async def sessions_partial(
    request: Request, status: Optional[str] = None
) -> HTMLResponse:
    sessions = await _get_sessions(limit=50, status=status)
    return templates.TemplateResponse(
        "partials/session_rows.html", {"request": request, "sessions": sessions}
    )


@router.post("/_launch", response_class=HTMLResponse)
async def launch_run(
    request: Request,
    task: str = Form("Weekly tech watch"),
    topics: str = Form(""),
    mode: str = Form("v2"),
    send_email: str = Form(""),
) -> HTMLResponse:
    topics_list = [t.strip() for t in topics.split(",") if t.strip()] or None
    do_send = send_email.lower() in ("true", "on", "1", "yes")
    try:
        from app.scheduler.service import OrchestratorScheduler

        scheduler = OrchestratorScheduler(mode=mode, settings=get_settings())
        result = await scheduler.run_task(
            task=task,
            topics=topics_list,
            send_email=do_send,
            autonomous=True,
        )
    except Exception as exc:
        logger.error("Dashboard launch failed: %s", exc)
        result = {"success": False, "errors": [str(exc)]}

    return templates.TemplateResponse(
        "partials/run_result.html",
        {"request": request, "result": result, "task": task},
    )


@router.post("/_newsletter", response_class=HTMLResponse)
async def launch_newsletter(
    request: Request,
    topics: str = Form(""),
    send_email: str = Form(""),
) -> HTMLResponse:
    topics_list = [t.strip() for t in topics.split(",") if t.strip()] or None
    do_send = send_email.lower() in ("true", "on", "1", "yes")
    error: Optional[str] = None
    result = None
    email_sent = False

    try:
        from app.agents.newsletter.agent import create_newsletter_agent
        from app.delivery.service import ReportDeliveryService

        settings = get_settings()
        agent = create_newsletter_agent(settings)
        result = await agent.execute({"topics": topics_list})

        if result.success and do_send:
            newsletter = result.output.get("newsletter", "")
            subject = result.output.get("subject", "Tech Watch Newsletter")
            delivery = ReportDeliveryService(settings).deliver(newsletter, subject, send=True)
            email_sent = delivery.sent
    except Exception as exc:
        logger.error("Dashboard newsletter failed: %s", exc)
        error = str(exc)

    return templates.TemplateResponse(
        "partials/newsletter_result.html",
        {
            "request": request,
            "result": result,
            "email_sent": email_sent,
            "error": error,
        },
    )
