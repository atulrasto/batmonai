import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin

EventKind = Enum(
    "discharge_start",
    "discharge_end",
    "mains_outage",
    "charging",
    "float",
    "low_voltage",
    "high_voltage",
    "device_offline",
    "high_temperature",
    "high_humidity",
    "h2_gas_alarm",
    name="event_kind",
)

EventSeverity = Enum("info", "warning", "critical", name="event_severity")


class Event(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "events"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    appliance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appliances.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(EventKind, nullable=False)
    severity: Mapped[str] = mapped_column(
        EventSeverity, nullable=False, default="info", server_default="info"
    )
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
