import uuid

from sqlalchemy import Boolean, ForeignKey, SmallInteger, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Rs485Sensor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rs485_sensors"
    __table_args__ = (
        UniqueConstraint("appliance_id", "modbus_addr", name="uq_rs485_sensors_appliance_addr"),
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    appliance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appliances.id", ondelete="CASCADE"), nullable=False
    )
    sensor_uid: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    sensor_type: Mapped[str] = mapped_column(String, nullable=False)
    modbus_addr: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    appliance: Mapped["Appliance"] = relationship("Appliance", back_populates="rs485_sensors")  # noqa: F821
