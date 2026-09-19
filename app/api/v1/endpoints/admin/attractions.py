from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import require_admin
from app.db.session import get_db
from app.models import (
    Attraction, AttractionHighlight, AttractionImage, AttractionTip,
    Category, TourTime,
)
from app.schemas.admin import AdminAttractionOut, AttractionCreate, AttractionUpdate
from app.schemas.common import Page

router = APIRouter(
    prefix="/admin/attractions", tags=["admin"], dependencies=[Depends(require_admin)]
)

# Maps a payload key to the model it should be rebuilt into when the admin
# sends a replacement list for one of an attraction's sub-collections.
_CHILD_MODELS = {
    "images": AttractionImage,
    "highlights": AttractionHighlight,
    "tips": AttractionTip,
    "tour_times": TourTime,
}


def _get_or_404(db: Session, attraction_id: str) -> Attraction:
    attraction = db.get(Attraction, attraction_id)
    if attraction is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Landmark not found")
    return attraction


def _require_category(db: Session, category_slug: str) -> None:
    if db.get(Category, category_slug) is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unknown category_slug: {category_slug}",
        )


@router.get("", response_model=Page[AdminAttractionOut])
def list_attractions(
    q: str | None = Query(default=None, max_length=120),
    category_slug: str | None = Query(default=None, max_length=64),
    is_active: bool | None = None,
    featured: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Unlike the public listing, this includes inactive landmarks so the
    admin can find and re-activate something they previously hid."""
    stmt = select(Attraction).options(
        selectinload(Attraction.images),
        selectinload(Attraction.highlights),
        selectinload(Attraction.tips),
        selectinload(Attraction.tour_times),
    )
    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Attraction.name).like(term),
                func.lower(Attraction.neighborhood).like(term),
            )
        )
    if category_slug:
        stmt = stmt.where(Attraction.category_slug == category_slug.lower())
    if is_active is not None:
        stmt = stmt.where(Attraction.is_active.is_(is_active))
    if featured is not None:
        stmt = stmt.where(Attraction.featured.is_(featured))

    rows = list(db.scalars(stmt.order_by(Attraction.name)).unique().all())
    total = len(rows)
    start = (page - 1) * page_size
    window = rows[start : start + page_size]

    return {
        "items": window,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, ceil(total / page_size)),
    }


@router.post("", response_model=AdminAttractionOut, status_code=status.HTTP_201_CREATED)
def create_attraction(
    payload: AttractionCreate,
    db: Session = Depends(get_db),
):
    if db.get(Attraction, payload.id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "That id/slug is already in use")
    _require_category(db, payload.category_slug)

    data = payload.model_dump()
    child_payloads = {key: data.pop(key) for key in _CHILD_MODELS}

    attraction = Attraction(**data)
    for key, Model in _CHILD_MODELS.items():
        setattr(attraction, key, [Model(**row) for row in child_payloads[key]])

    db.add(attraction)
    db.commit()
    db.refresh(attraction)
    return attraction


@router.get("/{attraction_id}", response_model=AdminAttractionOut)
def get_attraction(
    attraction_id: str,
    db: Session = Depends(get_db),
):
    return _get_or_404(db, attraction_id)


@router.patch("/{attraction_id}", response_model=AdminAttractionOut)
def update_attraction(
    attraction_id: str,
    payload: AttractionUpdate,
    db: Session = Depends(get_db),
):
    attraction = _get_or_404(db, attraction_id)
    data = payload.model_dump(exclude_unset=True)

    if "category_slug" in data:
        _require_category(db, data["category_slug"])

    for key, Model in _CHILD_MODELS.items():
        if key in data:
            rows = data.pop(key)
            setattr(attraction, key, [Model(**row) for row in rows])

    for key, value in data.items():
        setattr(attraction, key, value)

    db.commit()
    db.refresh(attraction)
    return attraction


@router.delete("/{attraction_id}", response_model=AdminAttractionOut)
def deactivate_attraction(
    attraction_id: str,
    db: Session = Depends(get_db),
):
    """Soft delete only. Bookings and reviews reference attractions by id
    without cascading, so a hard delete would break booking history for
    anyone who already visited; is_active=False just hides it from the
    public API instead."""
    attraction = _get_or_404(db, attraction_id)
    attraction.is_active = False
    db.commit()
    db.refresh(attraction)
    return attraction
