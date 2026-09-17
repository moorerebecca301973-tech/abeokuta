from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_optional_user
from app.db.session import get_db
from app.models import Badge, User, UserBadge
from app.schemas.booking import BadgeOut

router = APIRouter(prefix="/badges", tags=["badges"])


@router.get("", response_model=list[BadgeOut])
def list_badges(
    db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)
):
    """Public: signed-out visitors see the badge set, all locked."""
    unlocked: dict[str, str] = {}
    if user is not None:
        rows = db.scalars(
            select(UserBadge).where(UserBadge.user_id == user.id)
        ).all()
        unlocked = {ub.badge_id: ub.unlocked_at.date().isoformat() for ub in rows}

    return [
        {
            "id": b.id,
            "title": b.title,
            "description": b.description,
            "icon": b.icon,
            "unlocked": b.id in unlocked,
            "unlocked_date": unlocked.get(b.id),
        }
        for b in db.scalars(select(Badge).order_by(Badge.position)).all()
    ]
