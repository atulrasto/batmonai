"""
Hypertable models — append-only, no UPDATE/DELETE (§2 invariant).
PKs are composite (time + id) so TimescaleDB can partition by time.
"""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, SmallInteger, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DcReading(Base):
    __tablename__ = "dc_readings"

    time: Mapped[datetime] = mapped_column(primary_key=True)
    battery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("batteries.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    voltage: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    current: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    power: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    energy_wh: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    alarm_flags: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    ingested_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AcReading(Base):
    __tablename__ = "ac_readings"

    time: Mapped[datetime] = mapped_column(primary_key=True)
    ac_channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ac_channels.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    voltage: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    current: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    power: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    energy_wh: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    frequency: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    power_factor: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=0, server_default="0")
    ingested_at: Mapped[datetime] = mapped_column(server_default=func.now())


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    time: Mapped[datetime] = mapped_column(primary_key=True)
    sensor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rs485_sensors.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(server_default=func.now())
