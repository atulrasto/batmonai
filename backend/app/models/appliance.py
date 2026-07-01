import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Appliance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "appliances"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    appliance_uid: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    device_secret_hash: Mapped[str] = mapped_column(String, nullable=False)
    fw_version: Mapped[str | None] = mapped_column(String, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    site: Mapped["Site"] = relationship("Site", back_populates="appliances")  # noqa: F821
    batteries: Mapped[list["Battery"]] = relationship("Battery", back_populates="appliance")  # noqa: F821
    ac_channels: Mapped[list["AcChannel"]] = relationship("AcChannel", back_populates="appliance")  # noqa: F821
    rs485_sensors: Mapped[list["Rs485Sensor"]] = relationship("Rs485Sensor", back_populates="appliance")  # noqa: F821
