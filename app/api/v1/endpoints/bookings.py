import base64
import hashlib
import hmac
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.deps import get_current_user
from app.db.base import utcnow
from app.db.session import get_db
from app.models import Addon, Attraction, Booking, BookingAddon, User
from app.schemas.booking import (
    BookingCreate, BookingCreateOut, BookingOut, BookingPassOut, QuoteOut, QuoteRequest,
)
from app.services import badges as badge_service
from app.services import booking as booking_service
from app.services import pricing
from app.services.serialize import booking_out

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _owned_or_404(db: Session, booking_id: str, user: User) -> Booking:
    booking = db.scalar(
        select(Booking)
        .options(selectinload(Booking.attraction))
        .where(Booking.id == booking_id)
    )
    # 404 rather than 403 for someone else's booking: do not confirm it exists.
    if booking is None or booking.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reservation not found")
    return booking


@router.post("/quote", response_model=QuoteOut)
def quote_booking(payload: QuoteRequest, db: Session = Depends(get_db)):
    """Same arithmetic that will be charged, so PriceSummary cannot drift."""
    attraction = db.get(Attraction, payload.attraction_id)
    if attraction is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Landmark not found")
    addons = [a for a in (db.get(Addon, i) for i in payload.addon_ids) if a is not None]
    return pricing.quote(
        attraction, payload.adults_count, payload.children_count, addons
    )


@router.get("", response_model=list[BookingOut])
def list_bookings(
    status_filter: str | None = Query(default=None, alias="status"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Booking)
        .options(selectinload(Booking.attraction))
        .where(Booking.user_id == user.id)
        .order_by(Booking.created_at.desc())
    )
    if status_filter:
        stmt = stmt.where(Booking.status == status_filter)
    return [booking_out(b) for b in db.scalars(stmt).unique().all()]


@router.post("", response_model=BookingCreateOut, status_code=status.HTTP_201_CREATED)
def create_booking(
    payload: BookingCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attraction = db.get(Attraction, payload.attraction_id)
    if attraction is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Landmark not found")

    addons = booking_service.validate_request(
        db,
        attraction,
        payload.visit_date,
        payload.time_slot,
        payload.adults_count,
        payload.children_count,
        payload.addon_ids,
    )

    priced = pricing.quote(
        attraction, payload.adults_count, payload.children_count, addons
    )

    booking = Booking(
        booking_ref=booking_service.next_reference(db),
        user_id=user.id,
        attraction_id=attraction.id,
        visit_date=payload.visit_date,
        time_slot=payload.time_slot,
        adults_count=payload.adults_count,
        children_count=payload.children_count,
        base_amount=priced["base_amount"],
        addons_amount=priced["addons_amount"],
        total_amount=priced["total_amount"],
        status="confirmed",
        payment_method=payload.payment_method,
        contact_name=payload.contact_name.strip(),
        contact_email=str(payload.contact_email).lower(),
        contact_phone=payload.contact_phone.strip(),
        attraction_name_snapshot=attraction.name,
        attraction_image_snapshot=attraction.image,
    )
    booking.addons = [
        BookingAddon(
            addon_id=a.id, unit_price=a.price, name_snapshot=a.name, quantity=1
        )
        for a in addons
    ]
    db.add(booking)
    db.commit()
    db.refresh(booking)

    # Returned in the same response so the success modal can celebrate the
    # badge alongside the confetti, instead of the user finding it later.
    newly = badge_service.evaluate(db, user)

    return {
        "booking": booking_out(booking),
        "newly_unlocked_badges": [
            {
                "id": b.id,
                "title": b.title,
                "description": b.description,
                "icon": b.icon,
                "unlocked": True,
                "unlocked_date": date.today().isoformat(),
            }
            for b in newly
        ],
    }


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(
    booking_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return booking_out(_owned_or_404(db, booking_id, user))


@router.post("/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(
    booking_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = _owned_or_404(db, booking_id, user)
    if booking.status == "cancelled":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This reservation is already cancelled"
        )
    if booking.visit_date < date.today():
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A past visit cannot be cancelled"
        )
    booking.status = "cancelled"
    booking.cancelled_at = utcnow()
    db.commit()          # the row is never deleted
    db.refresh(booking)
    return booking_out(booking)


def _sign(payload: str) -> str:
    """HMAC so a gate attendant can verify a pass was not fabricated."""
    return hmac.new(
        settings.SECRET_KEY.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()[:16]


@router.get("/{booking_id}/pass", response_model=BookingPassOut)
def get_pass(
    booking_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = _owned_or_404(db, booking_id, user)
    if booking.status == "cancelled":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A cancelled reservation has no pass"
        )

    payload = (
        f"{booking.booking_ref}|{booking.attraction_id}"
        f"|{booking.visit_date.isoformat()}|{booking.time_slot}"
    )
    signature = _sign(payload)

    import qrcode  # imported lazily: only this endpoint needs Pillow loaded

    img = qrcode.make(f"{payload}|{signature}")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    png_b64 = base64.b64encode(buffer.getvalue()).decode()

    return {
        "booking_ref": booking.booking_ref,
        "attraction_name": booking.attraction_name_snapshot,
        "attraction_image": booking.attraction_image_snapshot,
        "visit_date": booking.visit_date,
        "time_slot": booking.time_slot,
        "visitors": {
            "adults": booking.adults_count,
            "children": booking.children_count,
        },
        "total_amount": booking.total_amount,
        "status": booking.status,
        "contact_name": booking.contact_name,
        "qr_payload": payload,
        "qr_signature": signature,
        "qr_png_base64": png_b64,
    }
