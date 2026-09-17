from typing import Literal

from pydantic import BaseModel

from app.schemas.common import Coordinates


class DistanceOut(BaseModel):
    from_point: Coordinates
    to_point: Coordinates
    attraction_id: str | None = None
    distance_km: float


class RoutePoint(Coordinates):
    id: str | None = None
    name: str | None = None


class RouteOut(BaseModel):
    from_point: RoutePoint
    to_point: RoutePoint
    distance_km: float
    duration_min: int
    mode: Literal["walking", "driving"]
    geometry_type: str
    polyline: list[list[float]]


class CulturalFactOut(BaseModel):
    id: str
    title: str
    fact: str
    icon: str = "Sparkles"
