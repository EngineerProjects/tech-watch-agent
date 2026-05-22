"""Email group API — CRUD endpoints for reusable delivery recipients."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.api.security import require_admin_access
from app.db.base import async_session_factory
from app.db.models import EmailGroup
from app.db.repositories import EmailGroupRepository

router = APIRouter(prefix="/email-groups", tags=["Email Groups"], dependencies=[Depends(require_admin_access)])


class EmailGroupRecipientInput(BaseModel):
    email: EmailStr
    label: Optional[str] = Field(None, max_length=120)


class LinkedWatchProfileSummary(BaseModel):
    id: str
    name: str


class EmailGroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    is_active: bool = True
    recipients: list[EmailGroupRecipientInput] = Field(default_factory=list)


class EmailGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    recipients: Optional[list[EmailGroupRecipientInput]] = None


class EmailGroupResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    is_active: bool
    recipients: list[EmailGroupRecipientInput]
    recipient_count: int
    linked_watch_profiles: list[LinkedWatchProfileSummary]
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, group: EmailGroup) -> "EmailGroupResponse":
        return cls(
            id=str(group.id),
            name=group.name,
            description=group.description,
            is_active=group.is_active,
            recipients=[
                EmailGroupRecipientInput(email=recipient.email, label=recipient.label)
                for recipient in (group.recipients or [])
            ],
            recipient_count=len(group.recipients or []),
            linked_watch_profiles=[
                LinkedWatchProfileSummary(id=str(profile.id), name=profile.name)
                for profile in (group.watch_profiles or [])
            ],
            created_at=group.created_at.isoformat() if group.created_at else "",
            updated_at=group.updated_at.isoformat() if group.updated_at else "",
        )


@router.get("/", response_model=list[EmailGroupResponse])
async def list_email_groups(active_only: bool = False) -> list[EmailGroupResponse]:
    async with async_session_factory() as db:
        repo = EmailGroupRepository(db)
        groups = await repo.list_all(active_only=active_only)
        return [EmailGroupResponse.from_model(group) for group in groups]


@router.post("/", response_model=EmailGroupResponse, status_code=201)
async def create_email_group(body: EmailGroupCreate) -> EmailGroupResponse:
    async with async_session_factory() as db:
        repo = EmailGroupRepository(db)
        group = EmailGroup(
            id=uuid.uuid4(),
            name=body.name,
            description=body.description,
            is_active=body.is_active,
        )
        created = await repo.create(group)
        await repo.replace_recipients(created, [item.model_dump() for item in body.recipients])
        await db.commit()
        refreshed = await repo.get_by_id(created.id)
        return EmailGroupResponse.from_model(refreshed or created)


@router.get("/{group_id}", response_model=EmailGroupResponse)
async def get_email_group(group_id: str) -> EmailGroupResponse:
    async with async_session_factory() as db:
        repo = EmailGroupRepository(db)
        group = await repo.get_by_id(uuid.UUID(group_id))
        if not group:
            raise HTTPException(status_code=404, detail="Email group not found")
        return EmailGroupResponse.from_model(group)


@router.patch("/{group_id}", response_model=EmailGroupResponse)
async def update_email_group(group_id: str, body: EmailGroupUpdate) -> EmailGroupResponse:
    async with async_session_factory() as db:
        repo = EmailGroupRepository(db)
        group = await repo.get_by_id(uuid.UUID(group_id))
        if not group:
            raise HTTPException(status_code=404, detail="Email group not found")

        updates = body.model_dump(exclude_none=True, exclude={"recipients"})
        for field, value in updates.items():
            setattr(group, field, value)

        if body.recipients is not None:
            await repo.replace_recipients(group, [item.model_dump() for item in body.recipients])

        updated = await repo.update(group)
        await db.commit()
        return EmailGroupResponse.from_model(updated)


@router.delete("/{group_id}", status_code=204)
async def delete_email_group(group_id: str) -> None:
    async with async_session_factory() as db:
        repo = EmailGroupRepository(db)
        deleted = await repo.delete(uuid.UUID(group_id))
        if not deleted:
            raise HTTPException(status_code=404, detail="Email group not found")
        await db.commit()
