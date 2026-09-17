from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import Attraction, Review, User
from app.schemas.attraction import ReviewCreate, ReviewOut
from app.services.serialize import review_out

router = APIRouter(prefix="/attractions", tags=["reviews"])


def _recompute(db: Session, attraction: Attraction) -> None:
    avg, count = db.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(
            Review.attraction_id == attraction.id, Review.is_approved.is_(True)
        )
    ).one()
    attraction.rating = round(float(avg or 0), 1)
    attraction.review_count = int(count or 0)


@router.get("/{attraction_id}/reviews", response_model=list[ReviewOut])
def list_reviews(
    attraction_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    if db.get(Attraction, attraction_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Landmark not found")
    rows = db.scalars(
        select(Review)
        .where(Review.attraction_id == attraction_id, Review.is_approved.is_(True))
        .order_by(Review.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [review_out(r) for r in rows]


@router.post(
    "/{attraction_id}/reviews",
    response_model=ReviewOut,
    status_code=status.HTTP_201_CREATED,
)
def create_review(
    attraction_id: str,
    payload: ReviewCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attraction = db.get(Attraction, attraction_id)
    if attraction is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Landmark not found")

    existing = db.scalar(
        select(Review).where(
            Review.attraction_id == attraction_id, Review.user_id == user.id
        )
    )
    if existing:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "You have already reviewed this landmark"
        )

    review = Review(
        attraction_id=attraction_id,
        user_id=user.id,
        author_name=user.name,
        author_avatar=user.avatar_url,
        rating=round(payload.rating, 1),
        comment=payload.comment.strip(),
    )
    db.add(review)
    db.flush()
    _recompute(db, attraction)   # same transaction: rating never drifts
    db.commit()
    db.refresh(review)
    return review_out(review)
