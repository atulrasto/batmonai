import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, SmallInteger, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Battery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "batteries"
    __table_args__ = (
        UniqueConstraint("appliance_id", "modbus_addr", name="uq_batteries_appliance_addr"),
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    appliance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appliances.id", ondelete="CASCADE"), nullable=False
    )
    battery_uid: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False, default="", server_default="")
    modbus_addr: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    shunt_rating_a: Mapped[int] = mapped_column(SmallInteger, default=100, server_default="100")
    capacity_ah: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    chemistry: Mapped[str] = mapped_column(
        String, default="flooded_lead_acid", server_default="flooded_lead_acid"
    )
    nominal_v: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=12.0, server_default="12.0")
    low_v_threshold: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=11.5, server_default="11.5")
    high_v_threshold: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=14.5, server_default="14.5")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    appliance: Mapped["Appliance"] = relationship("Appliance", back_populates="batteries")  # noqa: F821
