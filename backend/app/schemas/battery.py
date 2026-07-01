import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class BatteryCreate(BaseModel):
    appliance_id: uuid.UUID
    name: str = ""
    modbus_addr: int = Field(ge=1, le=247)
    shunt_rating_a: int = Field(default=100, ge=1)
    capacity_ah: Decimal | None = None
    chemistry: str = "flooded_lead_acid"
    nominal_v: Decimal = Decimal("12.0")
    client_id: uuid.UUID | None = None


class BatteryUpdate(BaseModel):
    name: str | None = None
    modbus_addr: int | None = Field(default=None, ge=1, le=247)
    shunt_rating_a: int | None = Field(default=None, ge=1)
    capacity_ah: Decimal | None = None
    chemistry: str | None = None
    nominal_v: Decimal | None = None
    is_active: bool | None = None


class BatteryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    appliance_id: uuid.UUID
    battery_uid: str
    name: str
    modbus_addr: int
    shunt_rating_a: int
    capacity_ah: Decimal | None
    chemistry: str
    nominal_v: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime
