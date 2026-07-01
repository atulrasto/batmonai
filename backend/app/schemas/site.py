import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SiteCreate(BaseModel):
    name: str
    location: str | None = None
    client_id: uuid.UUID | None = None


class SiteUpdate(BaseModel):
    name: str | None = None
    location: str | None = None


class SiteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    name: str
    slug: str
    location: str | None
    created_at: datetime
    updated_at: datetime
