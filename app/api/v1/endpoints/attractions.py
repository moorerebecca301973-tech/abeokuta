from datetime import date as date_type
from math import ceil, log

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_optional_user
from app.db.session import get_db
from app.models import Attraction, Favorite, User
from app.schemas.attraction import (
    AttractionDetail, AttractionListItem, AvailabilityOut, MapMarker,
)
from app.schemas.common import Page
from app.services import booking as booking_service
from app.services.geo import bounding_box, haversine_km
from app.services.serialize import attraction_detail, attraction_list_item, map_marker

router = APIRouter(prefix="/attractions", tags=["attractions"])

SORTS = ("relevance", "distance_asc", "rating_desc", "price_asc", "name_asc")


def _favorite_ids(db: Session, user: User | None) -> set[str]:
    if user is None:
        return set()
    return set(
        db.scalars(
            select(Favorite.attraction_id).where(Favorite.user_id == user.id)
        ).all()
    )


def _relevance(a: Attraction, query: str | None) -> float:
    """Featured first, then rating weighted by how many people rated it.

    A plain review_count sort buries good small landmarks; the log dampens the
    advantage of Olumo Rock's 428 reviews over a well-rated quieter site.
    """
    score = a.rating * log(1 + a.review_count)
    if a.featured:
        score += 25
    if query:
        q = query.lower()
        if q in a.name.lower():
            score += 50
        elif q in (a.neighborhood or "").lower():
            score += 20
    return score


def _base_query():
    return select(Attraction).options(selectinload(Attraction.category)).where(
        Attraction.is_active.is_(True)
    )


@router.get("", response_model=Page[AttractionListItem])
def list_attractions(
    q: str | None = Query(default=None, max_length=120),
    category: str | None = Query(default=None, max_length=64),
    min_rating: float = Query(default=0, ge=0, le=5),
    max_distance_km: float | None = Query(default=None, gt=0, le=500),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    sort: str = Query(default="relevance"),
    featured: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    if sort not in SORTS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"sort must be one of: {', '.join(SORTS)}",
        )
    has_point = lat is not None and lng is not None
    if (max_distance_km or sort == "distance_asc") and not has_point:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "lat and lng are required to filter or sort by distance",
        )

    stmt = _base_query()

    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Attraction.name).like(term),
                func.lower(Attraction.description).like(term),
                func.lower(Attraction.neighborhood).like(term),
                func.lower(Attraction.category_slug).like(term),
            )
        )
    if category and category.lower() != "all":
        stmt = stmt.where(Attraction.category_slug == category.lower())
    if min_rating:
        stmt = stmt.where(Attraction.rating >= min_rating)
    if featured is not None:
        stmt = stmt.where(Attraction.featured.is_(featured))

    # Cheap SQL prefilter; exact circle applied in Python below.
    if max_distance_km and has_point:
        min_lat, max_lat, min_lng, max_lng = bounding_box(lat, lng, max_distance_km)
        stmt = stmt.where(
            Attraction.lat.between(min_lat, max_lat),
            Attraction.lng.between(min_lng, max_lng),
        )

    rows = list(db.scalars(stmt).unique().all())

    distances: dict[str, float] = {}
    if has_point:
        distances = {a.id: haversine_km(lat, lng, a.lat, a.lng) for a in rows}
        if max_distance_km:
            rows = [a for a in rows if distances[a.id] <= max_distance_km]

    if sort == "distance_asc":
        rows.sort(key=lambda a: distances[a.id])
    elif sort == "rating_desc":
        rows.sort(key=lambda a: a.rating, reverse=True)
    elif sort == "price_asc":
        rows.sort(key=lambda a: a.entry_fee)
    elif sort == "name_asc":
        rows.sort(key=lambda a: a.name.lower())
    else:
        rows.sort(key=lambda a: _relevance(a, q), reverse=True)

    total = len(rows)
    start = (page - 1) * page_size
    window = rows[start : start + page_size]
    favs = _favorite_ids(db, user)

    return {
        "items": [
            attraction_list_item(a, distances.get(a.id), a.id in favs) for a in window
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, ceil(total / page_size)),
    }


@router.get("/featured", response_model=list[AttractionListItem])
def featured_attractions(
    limit: int = Query(default=6, ge=1, le=20),
    lat: float | None = None,
    lng: float | None = None,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    rows = list(
        db.scalars(_base_query().where(Attraction.featured.is_(True))).unique().all()
    )
    rows.sort(key=lambda a: _relevance(a, None), reverse=True)
    favs = _favorite_ids(db, user)
    has_point = lat is not None and lng is not None
    return [
        attraction_list_item(
            a,
            haversine_km(lat, lng, a.lat, a.lng) if has_point else None,
            a.id in favs,
        )
        for a in rows[:limit]
    ]


@router.get("/nearby", response_model=list[AttractionListItem])
def nearby(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    radius_km: float = Query(default=25, gt=0, le=500),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    min_lat, max_lat, min_lng, max_lng = bounding_box(lat, lng, radius_km)
    rows = db.scalars(
        _base_query().where(
            Attraction.lat.between(min_lat, max_lat),
            Attraction.lng.between(min_lng, max_lng),
        )
    ).unique().all()

    scored = [(a, haversine_km(lat, lng, a.lat, a.lng)) for a in rows]
    scored = [pair for pair in scored if pair[1] <= radius_km]
    scored.sort(key=lambda pair: pair[1])
    favs = _favorite_ids(db, user)
    return [
        attraction_list_item(a, d, a.id in favs) for a, d in scored[:limit]
    ]


@router.get("/map", response_model=list[MapMarker])
def map_markers(
    category: str | None = Query(default=None, max_length=64),
    db: Session = Depends(get_db),
):
    stmt = _base_query()
    if category and category.lower() != "all":
        stmt = stmt.where(Attraction.category_slug == category.lower())
    return [map_marker(a) for a in db.scalars(stmt).unique().all()]


def _get_or_404(db: Session, attraction_id: str) -> Attraction:
    attraction = db.get(Attraction, attraction_id)
    if attraction is None or not attraction.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Landmark not found")
    return attraction


@router.get("/{attraction_id}", response_model=AttractionDetail)
def get_attraction(
    attraction_id: str,
    lat: float | None = None,
    lng: float | None = None,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    a = _get_or_404(db, attraction_id)
    distance = (
        haversine_km(lat, lng, a.lat, a.lng)
        if lat is not None and lng is not None
        else None
    )
    return attraction_detail(a, distance, a.id in _favorite_ids(db, user))


@router.get("/{attraction_id}/availability", response_model=AvailabilityOut)
def get_availability(
    attraction_id: str,
    visit_date: date_type | None = Query(default=None),
    db: Session = Depends(get_db),
):
    a = _get_or_404(db, attraction_id)
    target = visit_date or date_type.today()
    return {
        "attraction_id": a.id,
        "visit_date": target.isoformat(),
        "slots": booking_service.availability(db, a, target),
    }
