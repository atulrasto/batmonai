import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_rls_session, require_superuser
from app.auth.password import hash_password
from app.models.client import Client
from app.models.user import User
from app.schemas.client import ClientCreate, ClientOut, ClientUpdate
from app.services.email import send_client_welcome

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("/", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
async def create_client(
    data: ClientCreate,
    _su: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_rls_session),
) -> ClientOut:
    # Check email not already taken
    existing = await session.execute(
        select(Client).where(Client.primary_email == data.primary_email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    client = Client(name=data.name, primary_email=data.primary_email)
    session.add(client)
    await session.flush()

    temp_password = secrets.token_urlsafe(12)
    client_user = User(
        email=data.primary_email,
        password_hash=hash_password(temp_password),
        role="client",
        client_id=client.id,
        must_change_password=True,
        is_active=True,
    )
    session.add(client_user)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    await session.refresh(client)

    await send_client_welcome(data.primary_email, temp_password, data.name)
    return ClientOut.model_validate(client)


@router.get("/", response_model=list[ClientOut])
async def list_clients(
    session: AsyncSession = Depends(get_rls_session),
) -> list[ClientOut]:
    result = await session.execute(select(Client).order_by(Client.created_at.desc()))
    return [ClientOut.model_validate(c) for c in result.scalars().all()]


@router.get("/{client_id}", response_model=ClientOut)
async def get_client(
    client_id: uuid.UUID,
    session: AsyncSession = Depends(get_rls_session),
) -> ClientOut:
    result = await session.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return ClientOut.model_validate(client)


@router.patch("/{client_id}", response_model=ClientOut)
async def update_client(
    client_id: uuid.UUID,
    data: ClientUpdate,
    session: AsyncSession = Depends(get_rls_session),
) -> ClientOut:
    result = await session.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(client, field, value)
    session.add(client)
    await session.flush()
    await session.refresh(client)
    return ClientOut.model_validate(client)
