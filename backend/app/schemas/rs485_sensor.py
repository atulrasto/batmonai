import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Rs485SensorCreate(BaseModel):
    appliance_id: uuid.UUID
    sensor_type: str
    modbus_addr: int = Field(ge=1, le=247)
    name: str
    config: dict[str, Any] | None = None
    client_id: uuid.UUID | None = None


class Rs485SensorUpdate(BaseModel):
    name: str | None = None
    modbus_addr: int | None = Field(default=None, ge=1, le=247)
    config: dict[str, Any] | None = None
    is_active: bool | None = None


class Rs485SensorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    appliance_id: uuid.UUID
    sensor_uid: str
    sensor_type: str
    modbus_addr: int
    name: str
    config: dict[str, Any] | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
