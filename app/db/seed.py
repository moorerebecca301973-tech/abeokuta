"""Idempotent seeder.

Runs on every container start. It must never duplicate rows and must never
overwrite data a real user created, so every step checks before inserting.
"""
import json
import logging
import re
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import (
    Addon, Attraction, AttractionHighlight, AttractionImage, AttractionTip,
    Badge, Booking, BookingAddon, Category, CulturalFact, Favorite, Review,
    SimulatedLocation, TourTime, User,
)
from app.services import booking as booking_service

logger = logging.getLogger("abeokuta.seed")
SEED_DIR = Path(__file__).resolve().parent.parent / "seed_data"

BADGE_RULES = {
    "rock-climber": {"type": "book_any_of", "ids": ["olumo-rock"]},
    "indigo-apprentice": {"type": "book_any_of", "ids": ["itoku-market", "kemta-adire"]},
    "royal-guest": {"type": "book_any_of", "ids": ["ake-palace", "centenary-hall"]},
    "archive-explorer": {"type": "book_any_of", "ids": ["oopl-complex"]},
}

# reviewsData.ts keys two entries by a short name that is not the attraction id.
REVIEW_KEY_ALIASES = {
    "oopl": "oopl-complex",
    "amala-shitta": "surulere-amala-point",
}

CATEGORY_ICONS = {
    "history": "Landmark", "nature": "Trees", "markets": "ShoppingBag",
    "hotels": "BedDouble", "food": "UtensilsCrossed",
}


def slugify(value: str) -> str:
    value = value.lower().replace("&", "and")
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", value))


def load(name: str):
    path = SEED_DIR / f"{name}.json"
    if not path.exists():
        logger.warning("Seed file missing: %s", path)
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def seed_categories(db: Session) -> None:
    rows = load("categories") or []
    for row in rows:
        if db.get(Category, row["slug"]):
            continue
        db.add(
            Category(
                slug=row["slug"],
                name=row["name"],
                icon=CATEGORY_ICONS.get(row["slug"], "MapPin"),
                position=row.get("position", 0),
            )
        )
    db.commit()


def seed_attractions(db: Session) -> None:
    rows = load("attractions") or []
    for row in rows:
        if db.get(Attraction, row["id"]):
            continue                       # never clobber edited content
        slug = slugify(row["category"])
        if db.get(Category, slug) is None:
            db.add(Category(slug=slug, name=row["category"]))
            db.flush()

        attraction = Attraction(
            id=row["id"],
            name=row["name"],
            category_slug=slug,
            tagline=row.get("tagline", ""),
            description=row.get("description", ""),
            history=row.get("history", ""),
            lat=row["coordinates"]["lat"],
            lng=row["coordinates"]["lng"],
            address=row.get("address", ""),
            neighborhood=row.get("neighborhood", ""),
            opening_hours=row.get("openingHours", ""),
            entry_fee=row.get("entryFee", 0),
            child_entry_fee=row.get("childEntryFee"),
            rating=row.get("rating", 0.0),
            review_count=row.get("reviewCount", 0),
            image=row.get("image", ""),
            contact_phone=row.get("contactPhone", ""),
            audio_guide_duration=row.get("audioGuideDuration", "") or "",
            audio_guide_summary=row.get("audioGuideSummary", "") or "",
            estimated_duration=row.get("estimatedDuration", ""),
            accessibility=row.get("accessibility", ""),
            featured=bool(row.get("featured", False)),
        )
        attraction.images = [
            AttractionImage(url=u, position=i)
            for i, u in enumerate(row.get("gallery", []))
        ]
        attraction.highlights = [
            AttractionHighlight(text=t, position=i)
            for i, t in enumerate(row.get("highlights", []))
        ]
        attraction.tips = [
            AttractionTip(text=t, position=i)
            for i, t in enumerate(row.get("tipsForVisitors", []))
        ]
        attraction.tour_times = [
            TourTime(
                slot_label=s,
                capacity=settings.DEFAULT_SLOT_CAPACITY,
                position=i,
            )
            for i, s in enumerate(row.get("availableTourTimes", []))
        ]
        db.add(attraction)
    db.commit()


def seed_addons(db: Session) -> None:
    for row in load("addons") or []:
        if db.get(Addon, row["id"]):
            continue
        db.add(
            Addon(
                id=row["id"],
                name=row["name"],
                price=row["price"],
                description=row.get("description", ""),
            )
        )
    db.commit()


def seed_locations(db: Session) -> None:
    for i, row in enumerate(load("locations") or []):
        if db.get(SimulatedLocation, row["id"]):
            continue
        db.add(
            SimulatedLocation(
                id=row["id"],
                name=row["name"],
                lat=row["coordinates"]["lat"],
                lng=row["coordinates"]["lng"],
                description=row.get("description", ""),
                position=i,
            )
        )
    db.commit()


def seed_badges(db: Session) -> None:
    for i, row in enumerate(load("badges") or []):
        if db.get(Badge, row["id"]):
            continue
        db.add(
            Badge(
                id=row["id"],
                title=row["title"],
                description=row.get("description", ""),
                icon=row.get("icon", "Award"),
                criteria=json.dumps(BADGE_RULES.get(row["id"], {})),
                position=i,
            )
        )
    db.commit()


def seed_facts(db: Session) -> None:
    if db.scalar(select(func.count()).select_from(CulturalFact)):
        return
    for i, row in enumerate(load("facts") or []):
        db.add(
            CulturalFact(
                title=row["title"],
                fact=row["fact"],
                icon=row.get("icon", "Sparkles"),
                position=i,
            )
        )
    db.commit()


def seed_reviews(db: Session) -> None:
    """Imported with user_id NULL: these have no accounts behind them."""
    data = load("reviews") or {}
    if db.scalar(select(func.count()).select_from(Review)):
        return
    for raw_key, reviews in data.items():
        attraction_id = REVIEW_KEY_ALIASES.get(raw_key, raw_key)
        if db.get(Attraction, attraction_id) is None:
            logger.warning("Skipping reviews for unknown attraction: %s", raw_key)
            continue
        for row in reviews:
            db.add(
                Review(
                    id=row["id"].replace("-", ""),
                    attraction_id=attraction_id,
                    user_id=None,
                    author_name=row["userName"],
                    author_avatar=row.get("userAvatar", ""),
                    rating=row["rating"],
                    comment=row.get("comment", ""),
                )
            )
    db.commit()


def seed_demo_user(db: Session) -> User | None:
    row = load("demo_user")
    if row is None:
        return None
    email = row["email"].lower()
    user = db.scalar(select(User).where(User.email == email))
    if user:
        return user

    user = User(
        id=row["id"].replace("-", ""),
        name=row["name"],
        email=email,
        password_hash=hash_password(settings.DEMO_USER_PASSWORD),
        phone=row.get("phone", ""),
        origin=row.get("origin", ""),
        avatar_url=row.get("avatar", ""),
        interests=json.dumps(row.get("interests", [])),
        is_demo=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Demo account ready: %s / %s", email, settings.DEMO_USER_PASSWORD)
    return user


def seed_demo_bookings(db: Session, user: User) -> None:
    """Gives the My Bookings screen something to show on first run.

    Dates are shifted forward relative to today so the seeded reservations are
    always upcoming, not stuck in the past.
    """
    if db.scalar(
        select(func.count()).select_from(Booking).where(Booking.user_id == user.id)
    ):
        return

    offsets = [3, 6]
    for i, row in enumerate(load("demo_bookings") or []):
        attraction = db.get(Attraction, row["attractionId"])
        if attraction is None:
            continue
        addon_ids = row.get("selectedAddons", [])
        addons = [a for a in (db.get(Addon, x) for x in addon_ids) if a is not None]
        child_fee = (
            attraction.child_entry_fee
            if attraction.child_entry_fee is not None
            else round(attraction.entry_fee * 0.5)
        )
        base = (
            attraction.entry_fee * row["adultsCount"]
            + child_fee * row["childrenCount"]
        )
        extras = sum(a.price for a in addons)

        booking = Booking(
            booking_ref=booking_service.next_reference(db),
            user_id=user.id,
            attraction_id=attraction.id,
            visit_date=date.today() + timedelta(days=offsets[i % len(offsets)]),
            time_slot=row["timeSlot"],
            adults_count=row["adultsCount"],
            children_count=row["childrenCount"],
            base_amount=base,
            addons_amount=extras,
            total_amount=base + extras,
            status="confirmed",
            payment_method=row.get("paymentMethod", "arrival"),
            contact_name=row.get("contactName", user.name),
            contact_email=row.get("contactEmail", user.email),
            contact_phone=row.get("contactPhone", user.phone),
            attraction_name_snapshot=attraction.name,
            attraction_image_snapshot=attraction.image,
        )
        booking.addons = [
            BookingAddon(
                addon_id=a.id, unit_price=a.price, name_snapshot=a.name, quantity=1
            )
            for a in addons
        ]
        db.add(booking)
    db.commit()


def seed_demo_extras(db: Session, user: User) -> None:
    for attraction_id in ("olumo-rock", "itoku-market"):
        if db.get(Attraction, attraction_id) and not db.get(
            Favorite, (user.id, attraction_id)
        ):
            db.add(Favorite(user_id=user.id, attraction_id=attraction_id))
    db.commit()

    from app.services import badges as badge_service

    badge_service.evaluate(db, user)


def run() -> None:
    db = SessionLocal()
    try:
        seed_categories(db)
        seed_attractions(db)
        seed_addons(db)
        seed_locations(db)
        seed_badges(db)
        seed_facts(db)
        seed_reviews(db)
        user = seed_demo_user(db)
        if user:
            seed_demo_bookings(db, user)
            seed_demo_extras(db, user)

        counts = {
            "attractions": db.scalar(select(func.count()).select_from(Attraction)),
            "categories": db.scalar(select(func.count()).select_from(Category)),
            "addons": db.scalar(select(func.count()).select_from(Addon)),
            "reviews": db.scalar(select(func.count()).select_from(Review)),
            "badges": db.scalar(select(func.count()).select_from(Badge)),
            "users": db.scalar(select(func.count()).select_from(User)),
        }
        logger.info("Seed complete: %s", counts)
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run()
