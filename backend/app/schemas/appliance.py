import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ApplianceCreate(BaseModel):
    site_id: uuid.UUID
    name: str
    device_secret: str
    client_id: uuid.UUID | None = None


class ApplianceUpdate(BaseModel):
    name: str | None = None
    fw_version: str | None = None
    is_active: bool | None = None


class ApplianceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    site_id: uuid.UUID
    appliance_uid: str
    name: str
    fw_version: str | None
    last_seen_at: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
