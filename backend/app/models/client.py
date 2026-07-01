from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Client(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "clients"

    name: Mapped[str] = mapped_column(String, nullable=False)
    primary_email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    webhook_url: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    users: Mapped[list["User"]] = relationship("User", back_populates="client")  # noqa: F821
    sites: Mapped[list["Site"]] = relationship("Site", back_populates="client")  # noqa: F821
