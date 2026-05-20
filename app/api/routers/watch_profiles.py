"""Watch Profile API — CRUD and run endpoints."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.base import async_session_factory
from app.db.models import WatchProfile
from app.db.repositories import WatchProfileRepository

logger = get_logger(__name__)
router = APIRouter(prefix="/watch-profiles", tags=["Watch Profiles"])


# ── Pydantic schemas ─────────────────────────────────────────────────────────

class WatchProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    topics: list[str] = Field(default_factory=list)
    depth: str = Field("standard", pattern="^(brief|standard|deep)$")
    format: str = Field("report", pattern="^(digest|report|newsletter)$")
    angle: str = Field("both", pattern="^(technical|business|both)$")
    sources: list[str] = Field(default_factory=list)
    language: str = Field("fr", pattern="^(fr|en)$")
    audience: str = Field("solo developer", max_length=200)
    focus: Optional[str] = None
    schedule_time: Optional[str] = None
    schedule_days: list[str] = Field(default_factory=list)
    schedule_type: Optional[str] = Field(None)   # weekly|once|monthly|custom
    schedule_date: Optional[str] = None           # "2025-06-15"
    schedule_interval_months: Optional[int] = Field(None, ge=1, le=60)
    is_active: bool = True


class WatchProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    topics: Optional[list[str]] = None
    depth: Optional[str] = Field(None, pattern="^(brief|standard|deep)$")
    format: Optional[str] = Field(None, pattern="^(digest|report|newsletter)$")
    angle: Optional[str] = Field(None, pattern="^(technical|business|both)$")
    sources: Optional[list[str]] = None
    language: Optional[str] = Field(None, pattern="^(fr|en)$")
    audience: Optional[str] = Field(None, max_length=200)
    focus: Optional[str] = None
    schedule_time: Optional[str] = None
    schedule_days: Optional[list[str]] = None
    schedule_type: Optional[str] = None
    schedule_date: Optional[str] = None
    schedule_interval_months: Optional[int] = Field(None, ge=1, le=60)
    is_active: Optional[bool] = None


class WatchProfileResponse(BaseModel):
    id: str
    name: str
    topics: list[str]
    depth: str
    format: str
    angle: str
    sources: list[str]
    language: str
    audience: str
    focus: Optional[str]
    schedule_time: Optional[str]
    schedule_days: list[str]
    schedule_type: Optional[str]
    schedule_date: Optional[str]
    schedule_interval_months: Optional[int]
    is_active: bool
    last_run_at: Optional[str]
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, p: WatchProfile) -> "WatchProfileResponse":
        return cls(
            id=str(p.id),
            name=p.name,
            topics=list(p.topics or []),
            depth=p.depth,
            format=p.format,
            angle=p.angle,
            sources=list(p.sources or []),
            language=p.language,
            audience=p.audience,
            focus=p.focus,
            schedule_time=p.schedule_time,
            schedule_days=list(p.schedule_days or []),
            schedule_type=p.schedule_type,
            schedule_date=p.schedule_date,
            schedule_interval_months=p.schedule_interval_months,
            is_active=p.is_active,
            last_run_at=p.last_run_at.isoformat() if p.last_run_at else None,
            created_at=p.created_at.isoformat() if p.created_at else "",
            updated_at=p.updated_at.isoformat() if p.updated_at else "",
        )


class RunProfileRequest(BaseModel):
    send_email: bool = False
    task_override: Optional[str] = None


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[WatchProfileResponse])
async def list_profiles(active_only: bool = False) -> list[WatchProfileResponse]:
    async with async_session_factory() as db:
        repo = WatchProfileRepository(db)
        profiles = await repo.list_all(active_only=active_only)
        return [WatchProfileResponse.from_model(p) for p in profiles]


@router.post("/", response_model=WatchProfileResponse, status_code=201)
async def create_profile(body: WatchProfileCreate) -> WatchProfileResponse:
    async with async_session_factory() as db:
        repo = WatchProfileRepository(db)
        profile = WatchProfile(
            id=uuid.uuid4(),
            **body.model_dump(),
        )
        created = await repo.create(profile)
        await db.commit()
        return WatchProfileResponse.from_model(created)


@router.get("/{profile_id}", response_model=WatchProfileResponse)
async def get_profile(profile_id: str) -> WatchProfileResponse:
    async with async_session_factory() as db:
        repo = WatchProfileRepository(db)
        profile = await repo.get_by_id(uuid.UUID(profile_id))
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        return WatchProfileResponse.from_model(profile)


@router.patch("/{profile_id}", response_model=WatchProfileResponse)
async def update_profile(profile_id: str, body: WatchProfileUpdate) -> WatchProfileResponse:
    async with async_session_factory() as db:
        repo = WatchProfileRepository(db)
        profile = await repo.get_by_id(uuid.UUID(profile_id))
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(profile, field, value)
        updated = await repo.update(profile)
        await db.commit()
        return WatchProfileResponse.from_model(updated)


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(profile_id: str) -> None:
    async with async_session_factory() as db:
        repo = WatchProfileRepository(db)
        deleted = await repo.delete(uuid.UUID(profile_id))
        if not deleted:
            raise HTTPException(status_code=404, detail="Profile not found")
        await db.commit()


@router.post("/{profile_id}/run")
async def run_profile(profile_id: str, body: RunProfileRequest) -> dict[str, Any]:
    """Launch the orchestrator with this profile's configuration."""
    async with async_session_factory() as db:
        repo = WatchProfileRepository(db)
        profile = await repo.get_by_id(uuid.UUID(profile_id))
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        await repo.touch_last_run(uuid.UUID(profile_id))
        await db.commit()

    from app.core.watch_context import WatchContext
    from app.scheduler.service import OrchestratorScheduler
    from app.config.settings import get_settings

    ctx = WatchContext.from_profile(profile)
    task = body.task_override or (
        f"Tech watch: {', '.join(ctx.topics)}" if ctx.topics else "Weekly tech watch"
    )

    try:
        scheduler = OrchestratorScheduler(mode="v2", settings=get_settings())
        result = await scheduler.run_task(
            task=task,
            topics=ctx.topics or None,
            send_email=body.send_email,
            autonomous=True,
            watch_context=ctx,
        )
        return {"success": True, "profile": profile.name, "task": task, "result": result}
    except Exception as exc:
        logger.error("Profile run failed: %s", exc)
        return {"success": False, "profile": profile.name, "error": str(exc)}
