from math import asin, cos, radians, sin, sqrt

from app.core.config import settings

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in km, rounded to one decimal.

    Rounding matches calculateHaversineDistance() in the React client so the
    number on the map never disagrees with the number in the list.
    """
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    )
    return round(2 * EARTH_RADIUS_KM * asin(sqrt(a)), 1)


def bounding_box(lat: float, lng: float, radius_km: float) -> tuple[float, float, float, float]:
    """Square that fully contains the radius circle.

    Used as a cheap SQL prefilter, because SQLite is not guaranteed to have
    sin()/cos() available: those need a compile-time flag. Exact filtering
    happens in Python afterwards.
    """
    dlat = radius_km / 110.574
    dlng = radius_km / (111.320 * max(cos(radians(lat)), 1e-6))
    return lat - dlat, lat + dlat, lng - dlng, lng + dlng


def estimate_duration_minutes(distance_km: float, mode: str) -> int:
    speed = settings.DRIVING_SPEED_KMH if mode == "driving" else settings.WALKING_SPEED_KMH
    minutes = (distance_km * settings.DETOUR_FACTOR) / speed * 60
    return max(1, round(minutes))


def build_route(
    from_lat: float, from_lng: float, to_lat: float, to_lng: float, mode: str
) -> dict:
    """Straight-line route.

    geometry_type is in the response so this can later be swapped for OSRM or
    OpenRouteService returning "road_network" without any frontend change.
    """
    distance = haversine_km(from_lat, from_lng, to_lat, to_lng)
    return {
        "distance_km": distance,
        "duration_min": estimate_duration_minutes(distance, mode),
        "mode": mode,
        "geometry_type": "straight_line",
        "polyline": [[from_lat, from_lng], [to_lat, to_lng]],
    }
