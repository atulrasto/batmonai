import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ClientCreate(BaseModel):
    name: str
    primary_email: str  # plain str so .local / .internal dev domains work


class ClientUpdate(BaseModel):
    name: str | None = None
    primary_email: str | None = None
    webhook_url: str | None = None
    is_active: bool | None = None


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    primary_email: str
    webhook_url: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
