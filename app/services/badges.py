import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models import Badge, Booking, User, UserBadge


def _booked_attraction_ids(db: Session, user_id: str) -> set[str]:
    rows = db.scalars(
        select(Booking.attraction_id).where(
            Booking.user_id == user_id, Booking.status != "cancelled"
        )
    ).all()
    return set(rows)


def evaluate(db: Session, user: User) -> list[Badge]:
    """Run after every confirmed booking. Returns badges unlocked just now.

    Rules live in the badges table as JSON, not as if-statements, so adding a
    badge is a seed-data edit rather than a code change.
    """
    booked = _booked_attraction_ids(db, user.id)
    owned = set(
        db.scalars(select(UserBadge.badge_id).where(UserBadge.user_id == user.id)).all()
    )

    newly: list[Badge] = []
    for badge in db.scalars(select(Badge).order_by(Badge.position)).all():
        if badge.id in owned:
            continue
        try:
            rule = json.loads(badge.criteria or "{}")
        except json.JSONDecodeError:
            continue

        unlocked = False
        rule_type = rule.get("type")

        if rule_type == "book_any_of":
            unlocked = bool(booked & set(rule.get("ids", [])))
        elif rule_type == "book_all_of":
            unlocked = set(rule.get("ids", [])).issubset(booked)
        elif rule_type == "booking_count_gte":
            unlocked = len(booked) >= int(rule.get("count", 0))

        if unlocked:
            db.add(UserBadge(user_id=user.id, badge_id=badge.id, unlocked_at=utcnow()))
            newly.append(badge)

    if newly:
        db.commit()
    return newly
