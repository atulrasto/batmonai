import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

UserRole = Enum("superuser", "client", name="user_role")


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(UserRole, nullable=False)
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=True,
    )
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    client: Mapped["Client | None"] = relationship("Client", back_populates="users")  # noqa: F821
