"""Login history ORM model."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

LOGIN_STATUS_SUCCESS = "success"
LOGIN_STATUS_FAILED = "failed"


class LoginHistory(Base):
    """Record of user sign-in attempts and active sessions."""

    __tablename__ = "login_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    logout_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    browser: Mapped[str | None] = mapped_column(String(100), nullable=True)
    operating_system: Mapped[str | None] = mapped_column(String(100), nullable=True)
    device_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    login_status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    jwt_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<LoginHistory id={self.id} user_id={self.user_id} "
            f"status={self.login_status!r} active={self.is_active}>"
        )
