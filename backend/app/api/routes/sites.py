import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_rls_session, require_password_changed
from app.core.uid import unique_site_slug
from app.models.site import Site
from app.models.user import User
from app.schemas.site import SiteCreate, SiteOut, SiteUpdate

router = APIRouter(prefix="/sites", tags=["sites"])


def _resolve_client_id(data_client_id: uuid.UUID | None, user: User) -> uuid.UUID:
    if user.role == "superuser":
        if data_client_id is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="client_id required for superuser")
        return data_client_id
    return user.client_id  # type: ignore[return-value]


@router.post("/", response_model=SiteOut, status_code=status.HTTP_201_CREATED)
async def create_site(
    data: SiteCreate,
    user: User = Depends(require_password_changed),
    session: AsyncSession = Depends(get_rls_session),
) -> SiteOut:
    client_id = _resolve_client_id(data.client_id, user)
    slug = await unique_site_slug(session, client_id, data.name)
    site = Site(client_id=client_id, name=data.name, slug=slug, location=data.location)
    session.add(site)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already exists for this client")
    await session.refresh(site)
    return SiteOut.model_validate(site)


@router.get("/", response_model=list[SiteOut])
async def list_sites(
    session: AsyncSession = Depends(get_rls_session),
) -> list[SiteOut]:
    result = await session.execute(select(Site).order_by(Site.created_at.desc()))
    return [SiteOut.model_validate(s) for s in result.scalars().all()]


@router.get("/{site_id}", response_model=SiteOut)
async def get_site(
    site_id: uuid.UUID,
    session: AsyncSession = Depends(get_rls_session),
) -> SiteOut:
    result = await session.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    return SiteOut.model_validate(site)


@router.patch("/{site_id}", response_model=SiteOut)
async def update_site(
    site_id: uuid.UUID,
    data: SiteUpdate,
    session: AsyncSession = Depends(get_rls_session),
) -> SiteOut:
    result = await session.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(site, field, value)
    session.add(site)
    await session.flush()
    await session.refresh(site)
    return SiteOut.model_validate(site)


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site(
    site_id: uuid.UUID,
    session: AsyncSession = Depends(get_rls_session),
) -> None:
    result = await session.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    await session.delete(site)
