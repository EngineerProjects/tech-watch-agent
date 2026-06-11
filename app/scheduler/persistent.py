"""
Persistent APScheduler-based scheduler for WatchProfiles.

Replaces the polling loop with real cron jobs persisted in PostgreSQL.
Each active WatchProfile gets an APScheduler job keyed by its UUID.
Jobs survive API restarts and fire at exact scheduled times.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

_scheduler: Optional["ProfileScheduler"] = None


def get_profile_scheduler() -> "ProfileScheduler":
    global _scheduler
    if _scheduler is None:
        _scheduler = ProfileScheduler()
    return _scheduler


class ProfileScheduler:
    """APScheduler wrapper that persists jobs in PostgreSQL."""

    _JOB_PREFIX = "profile_"

    def __init__(self) -> None:
        self._scheduler = None
        self._ready = False

    def _build_scheduler(self, sync_db_url: str):
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
        except ImportError:
            logger.warning("apscheduler not installed — falling back to polling loop")
            return None

        jobstores = {"default": SQLAlchemyJobStore(url=sync_db_url)}
        return AsyncIOScheduler(jobstores=jobstores, timezone="UTC")

    async def start(self) -> None:
        """Start the scheduler and load all active profiles from DB."""
        from app.config.settings import get_settings
        settings = get_settings()

        self._scheduler = self._build_scheduler(settings.database_sync_url)
        if self._scheduler is None:
            return

        self._scheduler.start()
        self._ready = True
        logger.info("APScheduler started with PostgreSQL jobstore")

        # Load all active profiles and schedule them
        await self._reload_all_profiles()

    async def stop(self) -> None:
        if self._scheduler and self._ready:
            self._scheduler.shutdown(wait=False)
            self._ready = False
            logger.info("APScheduler stopped")

    async def _reload_all_profiles(self) -> None:
        """Load all active WatchProfiles from DB and schedule their jobs."""
        if not self._ready:
            return
        try:
            from app.db.base import async_session_factory
            from app.db.repositories import WatchProfileRepository
            async with async_session_factory() as db:
                repo = WatchProfileRepository(db)
                profiles = await repo.list_all(active_only=True)

            count = 0
            for profile in profiles:
                if profile.schedule_time and profile.schedule_type:
                    self._upsert_job(profile)
                    count += 1
            logger.info("Scheduled %d watch profile jobs", count)
        except Exception as exc:
            logger.warning("Could not reload profile jobs: %s", exc)

    def _upsert_job(self, profile) -> None:
        """Add or replace the APScheduler job for a WatchProfile."""
        if not self._ready or self._scheduler is None:
            return

        job_id = f"{self._JOB_PREFIX}{profile.id}"
        trigger = self._build_trigger(profile)
        if trigger is None:
            self._remove_job(str(profile.id))
            return

        try:
            if self._scheduler.get_job(job_id):
                self._scheduler.reschedule_job(job_id, trigger=trigger)
                logger.debug("Rescheduled job for profile '%s'", profile.name)
            else:
                self._scheduler.add_job(
                    _run_profile_job,
                    trigger=trigger,
                    id=job_id,
                    name=f"WatchProfile: {profile.name}",
                    args=[str(profile.id), profile.name],
                    replace_existing=True,
                    misfire_grace_time=300,  # 5 min grace for missed fires
                )
                logger.info("Scheduled job for profile '%s' (type=%s, time=%s)",
                            profile.name, profile.schedule_type, profile.schedule_time)
        except Exception as exc:
            logger.warning("Could not schedule profile '%s': %s", profile.name, exc)

    def _build_trigger(self, profile):
        """Build APScheduler trigger from profile schedule config."""
        try:
            from apscheduler.triggers.cron import CronTrigger
            from apscheduler.triggers.date import DateTrigger
        except ImportError:
            return None

        if not profile.schedule_time:
            return None

        try:
            hour, minute = profile.schedule_time.split(":")
            hour_int, minute_int = int(hour), int(minute)
        except (ValueError, AttributeError):
            logger.warning("Invalid schedule_time '%s' for profile '%s'",
                           profile.schedule_time, profile.name)
            return None

        stype = (profile.schedule_type or "weekly").lower()

        if stype == "once":
            if not profile.schedule_date:
                return None
            try:
                run_date = datetime.strptime(
                    f"{profile.schedule_date} {profile.schedule_time}", "%Y-%m-%d %H:%M"
                )
                return DateTrigger(run_date=run_date)
            except ValueError:
                return None

        if stype == "weekly":
            days = profile.schedule_days or []
            day_map = {
                "monday": "mon", "tuesday": "tue", "wednesday": "wed",
                "thursday": "thu", "friday": "fri", "saturday": "sat", "sunday": "sun",
                "lundi": "mon", "mardi": "tue", "mercredi": "wed",
                "jeudi": "thu", "vendredi": "fri", "samedi": "sat", "dimanche": "sun",
            }
            cron_days = ",".join(day_map.get(d.lower(), d[:3]) for d in days) if days else "mon-fri"
            return CronTrigger(day_of_week=cron_days, hour=hour_int, minute=minute_int)

        if stype == "monthly":
            return CronTrigger(day=1, hour=hour_int, minute=minute_int)

        if stype == "custom":
            interval = max(1, profile.schedule_interval_months or 1)
            # APScheduler doesn't have a native N-month interval, use IntervalTrigger in weeks
            from apscheduler.triggers.interval import IntervalTrigger
            return IntervalTrigger(weeks=interval * 4)

        # Fallback to daily
        return CronTrigger(hour=hour_int, minute=minute_int)

    def _remove_job(self, profile_id: str) -> None:
        if not self._ready or self._scheduler is None:
            return
        job_id = f"{self._JOB_PREFIX}{profile_id}"
        try:
            if self._scheduler.get_job(job_id):
                self._scheduler.remove_job(job_id)
                logger.debug("Removed APScheduler job for profile %s", profile_id)
        except Exception as exc:
            logger.debug("Could not remove job %s: %s", job_id, exc)

    def on_profile_created(self, profile) -> None:
        if profile.is_active and profile.schedule_time and profile.schedule_type:
            self._upsert_job(profile)

    def on_profile_updated(self, profile) -> None:
        if profile.is_active and profile.schedule_time and profile.schedule_type:
            self._upsert_job(profile)
        else:
            self._remove_job(str(profile.id))

    def on_profile_deleted(self, profile_id: str) -> None:
        self._remove_job(profile_id)

    def get_jobs_info(self) -> list[dict]:
        if not self._ready or self._scheduler is None:
            return []
        jobs = []
        for job in self._scheduler.get_jobs():
            if job.id.startswith(self._JOB_PREFIX):
                jobs.append({
                    "job_id": job.id,
                    "profile_id": job.id[len(self._JOB_PREFIX):],
                    "name": job.name,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                })
        return jobs

    @property
    def is_ready(self) -> bool:
        return self._ready


async def _run_profile_job(profile_id: str, profile_name: str) -> None:
    """APScheduler job function: runs a WatchProfile through the orchestrator."""
    logger.info("APScheduler firing profile '%s'", profile_name)
    try:
        from app.core.watch_context import WatchContext
        from app.db.base import async_session_factory
        from app.db.repositories import EmailGroupRepository, WatchProfileRepository
        from app.scheduler.service import OrchestratorScheduler
        from app.config.settings import get_settings
        from app.core.research_brief import build_research_brief

        async with async_session_factory() as db:
            repo = WatchProfileRepository(db)
            group_repo = EmailGroupRepository(db)
            profile = await repo.get_by_id(uuid.UUID(profile_id))
            if not profile or not profile.is_active:
                logger.info("Profile '%s' not active or not found, skipping", profile_name)
                return

            recipients = await group_repo.resolve_recipients_for_profile(profile)
            await repo.touch_last_run(uuid.UUID(profile_id))
            await db.commit()

        ctx = WatchContext.from_profile(profile)
        task = build_research_brief(
            profile.subject or profile.name,
            ctx.topics or None,
            profile.focus,
        )

        scheduler = OrchestratorScheduler(mode="v2", settings=get_settings())
        result = await scheduler.run_task(
            task=task,
            topics=ctx.topics or None,
            send_email=bool(recipients),
            autonomous=True,
            watch_context=ctx,
            recipients_override=recipients or None,
        )

        if result.get("success"):
            logger.info("APScheduler: profile '%s' completed (session=%s)",
                        profile_name, result.get("session_id"))
        else:
            logger.error("APScheduler: profile '%s' failed: %s",
                         profile_name, result.get("errors"))

        # Deactivate once-profiles after firing
        if (profile.schedule_type or "").lower() == "once":
            async with async_session_factory() as db:
                repo = WatchProfileRepository(db)
                p = await repo.get_by_id(uuid.UUID(profile_id))
                if p:
                    p.is_active = False
                    await repo.update(p)
                    await db.commit()

    except Exception as exc:
        logger.error("APScheduler profile '%s' raised: %s", profile_name, exc)
