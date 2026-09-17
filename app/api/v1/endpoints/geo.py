from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Attraction, SimulatedLocation
from app.schemas.attraction import SimulatedLocationOut
from app.schemas.geo import DistanceOut, RouteOut
from app.services.geo import build_route, haversine_km

router = APIRouter(prefix="/geo", tags=["geo"])


@router.get("/simulated-locations", response_model=list[SimulatedLocationOut])
def simulated_locations(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(SimulatedLocation).order_by(SimulatedLocation.position)
    ).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "coordinates": {"lat": r.lat, "lng": r.lng},
            "description": r.description,
        }
        for r in rows
    ]


def _target(db: Session, attraction_id: str) -> Attraction:
    attraction = db.get(Attraction, attraction_id)
    if attraction is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Landmark not found")
    return attraction


@router.get("/distance", response_model=DistanceOut)
def distance(
    from_lat: float = Query(ge=-90, le=90),
    from_lng: float = Query(ge=-180, le=180),
    to: str = Query(description="Attraction id"),
    db: Session = Depends(get_db),
):
    a = _target(db, to)
    return {
        "from_point": {"lat": from_lat, "lng": from_lng},
        "to_point": {"lat": a.lat, "lng": a.lng},
        "attraction_id": a.id,
        "distance_km": haversine_km(from_lat, from_lng, a.lat, a.lng),
    }


@router.get("/route", response_model=RouteOut)
def route(
    from_lat: float = Query(ge=-90, le=90),
    from_lng: float = Query(ge=-180, le=180),
    to: str = Query(description="Attraction id"),
    mode: Literal["walking", "driving"] = "walking",
    db: Session = Depends(get_db),
):
    a = _target(db, to)
    leg = build_route(from_lat, from_lng, a.lat, a.lng, mode)
    return {
        "from_point": {"lat": from_lat, "lng": from_lng},
        "to_point": {"lat": a.lat, "lng": a.lng, "id": a.id, "name": a.name},
        **leg,
    }
