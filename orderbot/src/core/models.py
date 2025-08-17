from __future__ import annotations

from datetime import datetime, UTC
from enum import Enum
from typing import Optional
from sqlalchemy import String, Text, Integer, ForeignKey, Enum as SAEnum, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utc_now() -> datetime:
    """Timezone-aware datetime for SQLAlchemy default/onupdate."""
    return datetime.now(UTC)


class UserRole(str, Enum):
    admin = "admin"
    operator = "operator"
    member = "member"


class OrderStatus(str, Enum):
    DRAFT = "DRAFT"
    NEW = "NEW"
    CLAIMED = "CLAIMED"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    CANCELED = "CANCELED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_user_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    role: Mapped[str] = mapped_column(SAEnum(UserRole), default=UserRole.member, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    def __repr__(self) -> str:
        return f"User(id={self.id}, tg_user_id={self.tg_user_id})"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Optional[float]] = mapped_column(nullable=True)
    image_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # 图片文件路径
    status: Mapped[str] = mapped_column(SAEnum(OrderStatus), default=OrderStatus.NEW, nullable=False, index=True)

    created_by: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_by_username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    contact_username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    claimed_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    claimed_by_username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    channel_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    histories: Mapped[list["OrderStatusHistory"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    from_status: Mapped[Optional[str]] = mapped_column(SAEnum(OrderStatus), nullable=True)
    to_status: Mapped[str] = mapped_column(SAEnum(OrderStatus), nullable=False)
    actor_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    note: Mapped[Optional[str]] = mapped_column(String(400), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    order: Mapped[Order] = relationship(back_populates="histories")


class ApplicationStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class OrderApplication(Base):
    __tablename__ = "order_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    applicant_tg_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    applicant_username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(SAEnum(ApplicationStatus), default=ApplicationStatus.PENDING, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
