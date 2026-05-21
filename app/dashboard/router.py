from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import markdown2
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.config.settings import get_settings
from app.core.logging import get_logger
from app.services.session_manager import normalize_plan_payload

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


async def _get_watch_profiles() -> list[dict]:
    try:
        from app.db.base import async_session_factory
        from app.db.repositories import WatchProfileRepository

        async with async_session_factory() as db:
            repo = WatchProfileRepository(db)
            rows = await repo.list_all(active_only=False)
            return [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "topics": list(p.topics or []),
                    "depth": p.depth,
                    "format": p.format,
                    "angle": p.angle,
                    "sources": list(p.sources or []),
                    "language": p.language,
                    "audience": p.audience,
                    "focus": p.focus,
                    "schedule_time": p.schedule_time,
                    "schedule_days": list(p.schedule_days or []),
                    "is_active": p.is_active,
                    "last_run_at": p.last_run_at.isoformat() if p.last_run_at else None,
                    "created_at": p.created_at.isoformat() if p.created_at else "",
                    "updated_at": p.updated_at.isoformat() if p.updated_at else "",
                }
                for p in rows
            ]
    except Exception as exc:
        logger.warning("Watch profiles unavailable: %s", exc)
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
        request=request,
        name="index.html",
        context={
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
        request=request,
        name="sessions.html",
        context={
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

            raw_results = s.research_results or []
            sources_count = 0
            for item in raw_results:
                if not isinstance(item, dict):
                    continue
                if isinstance(item.get("data"), list):
                    sources_count += sum(1 for entry in item["data"] if isinstance(entry, dict) and entry.get("url"))
                elif item.get("url"):
                    sources_count += 1

            session_data = {
                "id": str(s.id),
                "brief": s.research_brief,
                "status": s.status,
                "phase": s.phase or "—",
                "plan": normalize_plan_payload(s.plan),
                "research_results": raw_results,
                "sources_count": sources_count,
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
        request=request,
        name="session_detail.html",
        context={"s": session_data, "active": "sessions"},
    )


@router.get("/newsletter", response_class=HTMLResponse)
async def newsletter_page(request: Request) -> HTMLResponse:
    settings = get_settings()
    history = await _get_newsletter_history()
    return templates.TemplateResponse(
        request=request,
        name="newsletter.html",
        context={
            "history": history,
            "default_topics": ", ".join(settings.newsletter_topics),
            "active": "newsletter",
        },
    )


@router.get("/watch-profiles", response_class=HTMLResponse)
async def watch_profiles_page(request: Request) -> HTMLResponse:
    profiles = await _get_watch_profiles()
    return templates.TemplateResponse(
        request=request,
        name="watch_profiles.html",
        context={"profiles": profiles, "active": "profiles"},
    )


async def _get_scheduled_profiles() -> tuple[list[dict], list[dict]]:
    profiles = await _get_watch_profiles()
    now = datetime.now()
    scheduled, unscheduled = [], []
    for p in profiles:
        if p["schedule_time"]:
            try:
                h, m = map(int, p["schedule_time"].split(":"))
                next_run = now.replace(hour=h, minute=m, second=0, microsecond=0)
                if next_run <= now:
                    next_run += timedelta(days=1)
                delta = next_run - now
                hours, rem = divmod(int(delta.total_seconds()), 3600)
                minutes = rem // 60
                p["next_run"] = next_run.strftime("%d/%m %H:%M")
                p["next_run_in"] = f"{hours}h {minutes}min" if hours else f"{minutes} min"
            except Exception:
                p["next_run"] = None
                p["next_run_in"] = None
            scheduled.append(p)
        else:
            p["next_run"] = None
            p["next_run_in"] = None
            unscheduled.append(p)
    return sorted(scheduled, key=lambda x: x["schedule_time"]), unscheduled


@router.get("/scheduler", response_class=HTMLResponse)
async def scheduler_page(request: Request) -> HTMLResponse:
    scheduled, unscheduled = await _get_scheduled_profiles()
    return templates.TemplateResponse(
        request=request,
        name="scheduler.html",
        context={"scheduled": scheduled, "unscheduled": unscheduled, "active": "scheduler"},
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request) -> HTMLResponse:
    s = get_settings()
    tools_status = [
        {"name": "SearXNG", "ok": bool(s.searxng_url), "status": s.searxng_url or "Non configuré"},
        {"name": "Tavily", "ok": bool(s.tavily_api_key), "status": "Configuré" if s.tavily_api_key else "Clé manquante"},
        {"name": "Exa", "ok": bool(s.exa_api_key), "status": "Configuré" if s.exa_api_key else "Clé manquante"},
        {"name": "LangSearch", "ok": bool(s.langsearch_api_key), "status": "Configuré" if s.langsearch_api_key else "Clé manquante"},
        {"name": "Jina Reader", "ok": True, "status": "Libre (sans clé)"},
        {"name": "Gmail", "ok": bool(s.sender_email), "status": s.sender_email or "Non configuré"},
        {"name": "LLM", "ok": bool(s.llm_api_key), "status": s.llm_model or "Modèle non défini"},
    ]
    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={"s": s, "tools_status": tools_status, "active": "settings"},
    )


# ── HTMX partials ──────────────────────────────────────────────────────────────

@router.get("/_stats", response_class=HTMLResponse)
async def stats_partial(request: Request) -> HTMLResponse:
    stats = await _get_stats()
    return templates.TemplateResponse(
        request=request, name="partials/stats.html", context={"stats": stats}
    )


@router.get("/_sessions", response_class=HTMLResponse)
async def sessions_partial(
    request: Request, status: Optional[str] = None
) -> HTMLResponse:
    sessions = await _get_sessions(limit=50, status=status)
    return templates.TemplateResponse(
        request=request, name="partials/session_rows.html", context={"sessions": sessions}
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
        request=request,
        name="partials/run_result.html",
        context={"result": result, "task": task},
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
        request=request,
        name="partials/newsletter_result.html",
        context={
            "result": result,
            "email_sent": email_sent,
            "error": error,
        },
    )


@router.post("/_settings")
async def save_setting(request: Request) -> JSONResponse:
    data = await request.json()
    key = data.get("key", "")
    value = data.get("value", "")
    if not key:
        return JSONResponse({"ok": False, "error": "Missing key"})
    try:
        from app.db.base import async_session_factory
        from app.db.repositories import AppConfigRepository

        async with async_session_factory() as db:
            repo = AppConfigRepository(db)
            await repo.set(key, str(value))
            await db.commit()
            all_overrides = await repo.get_all()

        from app.config.settings import set_db_overrides
        set_db_overrides(all_overrides)
        return JSONResponse({"ok": True})
    except Exception as exc:
        logger.error("Save setting failed: %s", exc)
        return JSONResponse({"ok": False, "error": str(exc)})


@router.post("/_test-searxng")
async def test_searxng(request: Request) -> JSONResponse:
    data = await request.json()
    url = data.get("url", "") or get_settings().searxng_url
    try:
        import httpx

        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(f"{url}/search", params={"q": "test", "format": "json"})
            results = r.json().get("results", [])
            return JSONResponse({"ok": True, "results": len(results)})
    except Exception as exc:
        logger.warning("SearXNG test failed: %s", exc)
        return JSONResponse({"ok": False, "error": str(exc), "results": 0})
