from datetime import date, datetime

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_id, utcnow

BOOKING_STATUSES = ("confirmed", "completed", "cancelled")
PAYMENT_METHODS = ("arrival", "card", "transfer")


class Addon(Base):
    __tablename__ = "addons"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    price: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    booking_ref: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    attraction_id: Mapped[str] = mapped_column(ForeignKey("attractions.id"), index=True)

    visit_date: Mapped[date] = mapped_column(Date, nullable=False)
    time_slot: Mapped[str] = mapped_column(String(40), nullable=False)
    adults_count: Mapped[int] = mapped_column(Integer, default=1)
    children_count: Mapped[int] = mapped_column(Integer, default=0)

    base_amount: Mapped[int] = mapped_column(Integer, default=0)
    addons_amount: Mapped[int] = mapped_column(Integer, default=0)
    total_amount: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[str] = mapped_column(String(20), default="confirmed", index=True)
    payment_method: Mapped[str] = mapped_column(String(20), default="arrival")

    contact_name: Mapped[str] = mapped_column(String(120), default="")
    contact_email: Mapped[str] = mapped_column(String(255), default="")
    contact_phone: Mapped[str] = mapped_column(String(40), default="")

    # Snapshots keep an old pass readable if a landmark is renamed or re-photographed.
    attraction_name_snapshot: Mapped[str] = mapped_column(String(160), default="")
    attraction_image_snapshot: Mapped[str] = mapped_column(String(500), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user = relationship("User", back_populates="bookings")
    attraction = relationship("Attraction")
    addons = relationship(
        "BookingAddon", back_populates="booking",
        cascade="all, delete-orphan", lazy="selectin",
    )

    __table_args__ = (
        Index("ix_bookings_user_status", "user_id", "status"),
        Index("ix_bookings_slot", "attraction_id", "visit_date", "time_slot"),
    )

    @property
    def visitors_total(self) -> int:
        return self.adults_count + self.children_count


class BookingAddon(Base):
    __tablename__ = "booking_addons"

    booking_id: Mapped[str] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), primary_key=True
    )
    addon_id: Mapped[str] = mapped_column(ForeignKey("addons.id"), primary_key=True)
    # Price is copied at booking time so later price changes do not rewrite history.
    unit_price: Mapped[int] = mapped_column(Integer, default=0)
    name_snapshot: Mapped[str] = mapped_column(String(160), default="")
    quantity: Mapped[int] = mapped_column(Integer, default=1)

    booking = relationship("Booking", back_populates="addons")
    addon = relationship("Addon")


class BookingCounter(Base):
    """Collision-free ABK-2026-0001 references without a random retry loop."""

    __tablename__ = "booking_counters"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_seq: Mapped[int] = mapped_column(Integer, default=0)
