import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Site(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sites"
    __table_args__ = (UniqueConstraint("client_id", "slug", name="uq_sites_client_slug"),)

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str | None] = mapped_column(String, nullable=True)

    client: Mapped["Client"] = relationship("Client", back_populates="sites")  # noqa: F821
    appliances: Mapped[list["Appliance"]] = relationship("Appliance", back_populates="site")  # noqa: F821
