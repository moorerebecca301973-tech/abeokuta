from fastapi import APIRouter

from app.api.v1.endpoints import (
    addons, attractions, auth, badges, bookings, categories, favorites, geo,
    meta, reviews, users,
)

api_router = APIRouter()

api_router.include_router(meta.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(attractions.router)
api_router.include_router(reviews.router)
api_router.include_router(categories.router)
api_router.include_router(addons.router)
api_router.include_router(bookings.router)
api_router.include_router(favorites.router)
api_router.include_router(badges.router)
api_router.include_router(geo.router)
