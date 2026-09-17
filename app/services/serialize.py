"""Model to response-dict conversion.

Kept out of the endpoints so the same attraction shape is produced everywhere
and the field names line up with the existing TypeScript interfaces.
"""
import json

from app.models import Attraction, Booking, Review, User


def user_out(user: User) -> dict:
    try:
        interests = json.loads(user.interests or "[]")
    except json.JSONDecodeError:
        interests = []
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "origin": user.origin,
        "avatar": user.avatar_url,
        "interests": interests,
        "created_at": user.created_at,
    }


def attraction_base(
    a: Attraction, distance_km: float | None = None, is_favorite: bool = False
) -> dict:
    return {
        "id": a.id,
        "name": a.name,
        "category": a.category.name if a.category else a.category_slug,
        "tagline": a.tagline,
        "coordinates": {"lat": a.lat, "lng": a.lng},
        "neighborhood": a.neighborhood,
        "entry_fee": a.entry_fee,
        "child_entry_fee": a.child_entry_fee,
        "rating": a.rating,
        "review_count": a.review_count,
        "image": a.image,
        "featured": a.featured,
        "distance_km": distance_km,
        "is_favorite": is_favorite,
    }


def attraction_list_item(a: Attraction, distance_km=None, is_favorite=False) -> dict:
    return {
        **attraction_base(a, distance_km, is_favorite),
        "address": a.address,
        "opening_hours": a.opening_hours,
        "estimated_duration": a.estimated_duration,
    }


def attraction_detail(a: Attraction, distance_km=None, is_favorite=False) -> dict:
    return {
        **attraction_list_item(a, distance_km, is_favorite),
        "description": a.description,
        "history": a.history,
        "gallery": a.gallery,
        "highlights": a.highlight_list,
        "tips_for_visitors": a.tip_list,
        "available_tour_times": a.tour_time_list,
        "contact_phone": a.contact_phone,
        "audio_guide_duration": a.audio_guide_duration,
        "audio_guide_summary": a.audio_guide_summary,
        "accessibility": a.accessibility,
    }


def map_marker(a: Attraction) -> dict:
    """Deliberately slim: 15 pins should not carry 4 KB of history each."""
    return {
        "id": a.id,
        "name": a.name,
        "lat": a.lat,
        "lng": a.lng,
        "category": a.category.name if a.category else a.category_slug,
        "image": a.image,
        "rating": a.rating,
        "entry_fee": a.entry_fee,
    }


def review_out(r: Review) -> dict:
    return {
        "id": r.id,
        "user_name": r.author_name,
        "user_avatar": r.author_avatar,
        "rating": r.rating,
        "comment": r.comment,
        "date": r.created_at.strftime("%B %Y"),
    }


def booking_out(b: Booking) -> dict:
    return {
        "id": b.id,
        "booking_ref": b.booking_ref,
        "attraction_id": b.attraction_id,
        "attraction_name": b.attraction_name_snapshot
        or (b.attraction.name if b.attraction else ""),
        "attraction_image": b.attraction_image_snapshot
        or (b.attraction.image if b.attraction else ""),
        "visit_date": b.visit_date,
        "time_slot": b.time_slot,
        "adults_count": b.adults_count,
        "children_count": b.children_count,
        "addons": [
            {"id": ba.addon_id, "name": ba.name_snapshot, "price": ba.unit_price}
            for ba in b.addons
        ],
        "base_amount": b.base_amount,
        "addons_amount": b.addons_amount,
        "total_amount": b.total_amount,
        "status": b.status,
        "payment_method": b.payment_method,
        "contact_name": b.contact_name,
        "contact_email": b.contact_email,
        "contact_phone": b.contact_phone,
        "created_at": b.created_at,
    }
