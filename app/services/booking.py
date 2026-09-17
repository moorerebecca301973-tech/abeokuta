from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Addon, Attraction, Booking, BookingCounter, TourTime


def next_reference(db: Session) -> str:
    """ABK-2026-0001. A per-year counter, not Math.random().

    Safe because the app runs a single worker against SQLite, so the
    surrounding transaction serialises this for free.
    """
    year = date.today().year
    counter = db.get(BookingCounter, year)
    if counter is None:
        counter = BookingCounter(year=year, last_seq=0)
        db.add(counter)
        db.flush()
    counter.last_seq += 1
    db.flush()
    return f"ABK-{year}-{counter.last_seq:04d}"


def seats_taken(db: Session, attraction_id: str, visit_date: date, slot: str) -> int:
    total = db.scalar(
        select(func.coalesce(func.sum(Booking.adults_count + Booking.children_count), 0))
        .where(
            Booking.attraction_id == attraction_id,
            Booking.visit_date == visit_date,
            Booking.time_slot == slot,
            Booking.status != "cancelled",
        )
    )
    return int(total or 0)


def slot_capacity(attraction: Attraction, slot: str) -> int:
    for t in attraction.tour_times:
        if t.slot_label == slot:
            return t.capacity
    return settings.DEFAULT_SLOT_CAPACITY


def validate_request(
    db: Session,
    attraction: Attraction,
    visit_date: date,
    time_slot: str,
    adults: int,
    children: int,
    addon_ids: list[str],
) -> list[Addon]:
    """Every rule the client cannot be trusted to enforce. Order matters."""
    if not attraction.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "This landmark is not open for booking")

    today = date.today()
    if visit_date < today:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Pick a visit date from today onwards"
        )
    if visit_date > today + timedelta(days=settings.MAX_BOOKING_DAYS_AHEAD):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Visits can be booked up to {settings.MAX_BOOKING_DAYS_AHEAD} days ahead",
        )

    valid_slots = [t.slot_label for t in attraction.tour_times]
    if valid_slots and time_slot not in valid_slots:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"{time_slot} is not a tour time at {attraction.name}",
        )

    if adults < 1:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "At least one adult is required"
        )
    if adults + children > settings.MAX_VISITORS_PER_BOOKING:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Groups are limited to {settings.MAX_VISITORS_PER_BOOKING} visitors. "
            "Contact the tourist desk for larger parties.",
        )

    addons: list[Addon] = []
    for addon_id in dict.fromkeys(addon_ids):  # dedupe, preserve order
        addon = db.get(Addon, addon_id)
        if addon is None or not addon.is_active:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown tour extra: {addon_id}"
            )
        addons.append(addon)

    capacity = slot_capacity(attraction, time_slot)
    taken = seats_taken(db, attraction.id, visit_date, time_slot)
    remaining = capacity - taken
    if adults + children > remaining:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Only {max(remaining, 0)} seat(s) left at {time_slot} on {visit_date}",
        )

    return addons


def availability(db: Session, attraction: Attraction, visit_date: date) -> list[dict]:
    slots = attraction.tour_times or [
        TourTime(slot_label=s, capacity=settings.DEFAULT_SLOT_CAPACITY, position=i)
        for i, s in enumerate(["09:00 AM", "11:00 AM", "01:00 PM", "03:00 PM"])
    ]
    out = []
    for t in slots:
        taken = seats_taken(db, attraction.id, visit_date, t.slot_label)
        out.append(
            {
                "time_slot": t.slot_label,
                "capacity": t.capacity,
                "seats_taken": taken,
                "seats_left": max(t.capacity - taken, 0),
                "is_available": taken < t.capacity,
            }
        )
    return out
