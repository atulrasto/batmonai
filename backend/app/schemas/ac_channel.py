import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AcRole = Literal["inverter_input", "inverter_output", "load"]


class AcChannelCreate(BaseModel):
    appliance_id: uuid.UUID
    name: str
    modbus_addr: int = Field(ge=1, le=247)
    role: AcRole
    client_id: uuid.UUID | None = None


class AcChannelUpdate(BaseModel):
    name: str | None = None
    modbus_addr: int | None = Field(default=None, ge=1, le=247)
    role: AcRole | None = None
    is_active: bool | None = None


class AcChannelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    appliance_id: uuid.UUID
    channel_uid: str
    name: str
    modbus_addr: int
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
