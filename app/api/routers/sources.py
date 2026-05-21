from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.api.models import SourceResponse
from app.db.base import async_session_factory
from app.db.repositories import SessionSourceRepository

router = APIRouter(prefix="/sources", tags=["Sources"])


@router.get("", response_model=list[SourceResponse])
async def list_sources(
    session_id: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> list[SourceResponse]:
    session_uuid: Optional[uuid.UUID] = None
    if session_id:
        try:
            session_uuid = uuid.UUID(session_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid session ID format") from exc

    async with async_session_factory() as session:
        rows = await SessionSourceRepository(session).list_recent(
            limit=limit,
            session_id=session_uuid,
            query=query,
            source=source,
        )
        return [SourceResponse(**row) for row in rows]
