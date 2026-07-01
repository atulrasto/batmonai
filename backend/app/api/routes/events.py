"""Events API — read-only; events are written by the ingestion service."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_rls_session, require_password_changed
from app.models.event import Event
from app.models.user import User

router = APIRouter(prefix="/events", tags=["events"])


class EventOut(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    appliance_id: uuid.UUID
    kind: str
    severity: str
    detail: dict | None
    started_at: datetime
    resolved_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[EventOut])
async def list_events(
    appliance_id: uuid.UUID | None = Query(None),
    open_only: bool = Query(False),
    limit: int = Query(50, le=200),
    _user: User = Depends(require_password_changed),
    session: AsyncSession = Depends(get_rls_session),
) -> list[EventOut]:
    q = select(Event).order_by(Event.started_at.desc()).limit(limit)
    if appliance_id:
        q = q.where(Event.appliance_id == appliance_id)
    if open_only:
        q = q.where(Event.resolved_at.is_(None))
    result = await session.execute(q)
    return [EventOut.model_validate(e) for e in result.scalars().all()]


@router.get("/counts")
async def event_counts(
    _user: User = Depends(require_password_changed),
    session: AsyncSession = Depends(get_rls_session),
) -> dict:
    """Open event counts per appliance — used for dashboard badges."""
    rows = await session.execute(
        text("""
            SELECT appliance_id::text, severity, COUNT(*) as n
            FROM events
            WHERE resolved_at IS NULL
            GROUP BY appliance_id, severity
        """)
    )
    result: dict[str, dict] = {}
    for row in rows:
        aid = row.appliance_id
        if aid not in result:
            result[aid] = {"warning": 0, "critical": 0, "info": 0, "total": 0}
        result[aid][row.severity] = int(row.n)
        result[aid]["total"] += int(row.n)
    return result
