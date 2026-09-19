from fastapi import APIRouter

from app.api.v1.endpoints.admin import attractions, bookings, categories

router = APIRouter()
router.include_router(attractions.router)
router.include_router(categories.router)
router.include_router(bookings.router)
