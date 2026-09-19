from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import require_admin
from app.db.base import utcnow
from app.db.session import get_db
from app.models import BOOKING_STATUSES, Booking
from app.schemas.admin import AdminBookingOut, BookingStatsOut, BookingStatusUpdate
from app.services import booking as booking_service

router = APIRouter(
    prefix="/admin/bookings", tags=["admin"], dependencies=[Depends(require_admin)]
)


def _admin_booking_out(b: Booking) -> dict:
    return {
        "id": b.id,
        "booking_ref": b.booking_ref,
        "user_id": b.user_id,
        "user_name": b.user.name if b.user else "",
        "user_email": b.user.email if b.user else "",
        "attraction_id": b.attraction_id,
        "attraction_name": b.attraction_name_snapshot
        or (b.attraction.name if b.attraction else ""),
        "attraction_image": b.attraction_image_snapshot
        or (b.attraction.image if b.attraction else ""),
        "visit_date": b.visit_date.isoformat(),
        "time_slot": b.time_slot,
        "adults_count": b.adults_count,
        "children_count": b.children_count,
        "base_amount": b.base_amount,
        "addons_amount": b.addons_amount,
        "total_amount": b.total_amount,
        "status": b.status,
        "payment_method": b.payment_method,
        "contact_name": b.contact_name,
        "contact_email": b.contact_email,
        "contact_phone": b.contact_phone,
        "created_at": b.created_at,
        "cancelled_at": b.cancelled_at,
    }


def _base_query():
    return select(Booking).options(
        selectinload(Booking.user), selectinload(Booking.attraction)
    )


@router.get("/stats", response_model=BookingStatsOut)
def booking_stats(db: Session = Depends(get_db)):
    """Declared before /{booking_id} so 'stats' is never parsed as an id."""
    rows = db.scalars(_base_query()).unique().all()
    today = date.today()
    revenue = sum(b.total_amount for b in rows if b.status != "cancelled")
    return {
        "total_bookings": len(rows),
        "confirmed": sum(1 for b in rows if b.status == "confirmed"),
        "completed": sum(1 for b in rows if b.status == "completed"),
        "cancelled": sum(1 for b in rows if b.status == "cancelled"),
        "upcoming": sum(
            1 for b in rows if b.status == "confirmed" and b.visit_date >= today
        ),
        "revenue_total": revenue,
        "bookings_today": sum(1 for b in rows if b.created_at.date() == today),
    }


@router.get("", response_model=list[AdminBookingOut])
def list_bookings(
    status_filter: str | None = Query(default=None, alias="status"),
    attraction_id: str | None = Query(default=None, max_length=64),
    user_id: str | None = Query(default=None, max_length=32),
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = Query(default=None, max_length=120, description="Matches booking ref or contact name/email"),
    db: Session = Depends(get_db),
):
    stmt = _base_query().order_by(Booking.created_at.desc())

    if status_filter:
        if status_filter not in BOOKING_STATUSES:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"status must be one of: {', '.join(BOOKING_STATUSES)}",
            )
        stmt = stmt.where(Booking.status == status_filter)
    if attraction_id:
        stmt = stmt.where(Booking.attraction_id == attraction_id)
    if user_id:
        stmt = stmt.where(Booking.user_id == user_id)
    if date_from:
        stmt = stmt.where(Booking.visit_date >= date_from)
    if date_to:
        stmt = stmt.where(Booking.visit_date <= date_to)
    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Booking.booking_ref).like(term),
                func.lower(Booking.contact_name).like(term),
                func.lower(Booking.contact_email).like(term),
            )
        )

    return [_admin_booking_out(b) for b in db.scalars(stmt).unique().all()]


def _get_or_404(db: Session, booking_id: str) -> Booking:
    booking = db.scalar(_base_query().where(Booking.id == booking_id))
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    return booking


@router.get("/{booking_id}", response_model=AdminBookingOut)
def get_booking(booking_id: str, db: Session = Depends(get_db)):
    return _admin_booking_out(_get_or_404(db, booking_id))


@router.patch("/{booking_id}/status", response_model=AdminBookingOut)
def update_status(
    booking_id: str,
    payload: BookingStatusUpdate,
    db: Session = Depends(get_db),
):
    if payload.status not in BOOKING_STATUSES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"status must be one of: {', '.join(BOOKING_STATUSES)}",
        )
    booking = _get_or_404(db, booking_id)

    # Reactivating a previously cancelled slot could overbook it, since the
    # capacity check only ran once, at original creation time.
    if booking.status == "cancelled" and payload.status != "cancelled":
        capacity = booking_service.slot_capacity(booking.attraction, booking.time_slot)
        taken = booking_service.seats_taken(
            db, booking.attraction_id, booking.visit_date, booking.time_slot
        )
        remaining = capacity - taken
        if booking.visitors_total > remaining:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Only {max(remaining, 0)} seat(s) left at {booking.time_slot} "
                f"on {booking.visit_date}; cannot restore this booking",
            )

    booking.status = payload.status
    booking.cancelled_at = utcnow() if payload.status == "cancelled" else None
    db.commit()
    db.refresh(booking)
    return _admin_booking_out(booking)
