import json
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import Badge, Booking, Favorite, User, UserBadge
from app.schemas.user import UserOut, UserStats, UserUpdate
from app.services.serialize import user_out

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserOut)
def update_me(
    payload: UserUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"]:
        user.name = data["name"].strip()
    if "phone" in data and data["phone"] is not None:
        user.phone = data["phone"].strip()
    if "origin" in data and data["origin"] is not None:
        user.origin = data["origin"].strip()
    if "avatar" in data and data["avatar"] is not None:
        user.avatar_url = data["avatar"].strip()
    if "interests" in data and data["interests"] is not None:
        user.interests = json.dumps(data["interests"])
    db.commit()
    db.refresh(user)
    return user_out(user)


@router.get("/me/stats", response_model=UserStats)
def my_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    saved = db.scalar(
        select(func.count()).select_from(Favorite).where(Favorite.user_id == user.id)
    )
    bookings = db.scalar(
        select(func.count()).select_from(Booking).where(Booking.user_id == user.id)
    )
    upcoming = db.scalar(
        select(func.count()).select_from(Booking).where(
            Booking.user_id == user.id,
            Booking.status == "confirmed",
            Booking.visit_date >= date.today(),
        )
    )
    unlocked = db.scalar(
        select(func.count()).select_from(UserBadge).where(UserBadge.user_id == user.id)
    )
    total = db.scalar(select(func.count()).select_from(Badge))
    return {
        "saved_count": int(saved or 0),
        "booking_count": int(bookings or 0),
        "upcoming_count": int(upcoming or 0),
        "badges_unlocked": int(unlocked or 0),
        "badges_total": int(total or 0),
    }
