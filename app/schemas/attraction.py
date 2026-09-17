from pydantic import BaseModel, Field

from app.schemas.common import Coordinates, ORMModel


class CategoryOut(ORMModel):
    slug: str
    name: str
    description: str = ""
    icon: str = "MapPin"
    attraction_count: int = 0


class AttractionBase(BaseModel):
    id: str
    name: str
    category: str
    tagline: str = ""
    coordinates: Coordinates
    neighborhood: str = ""
    entry_fee: int = 0
    child_entry_fee: int | None = None
    rating: float = 0.0
    review_count: int = 0
    image: str = ""
    featured: bool = False
    distance_km: float | None = None
    is_favorite: bool = False


class AttractionListItem(AttractionBase):
    address: str = ""
    opening_hours: str = ""
    estimated_duration: str = ""


class AttractionDetail(AttractionBase):
    description: str = ""
    history: str = ""
    address: str = ""
    opening_hours: str = ""
    gallery: list[str] = []
    highlights: list[str] = []
    tips_for_visitors: list[str] = []
    available_tour_times: list[str] = []
    contact_phone: str = ""
    audio_guide_duration: str = ""
    audio_guide_summary: str = ""
    estimated_duration: str = ""
    accessibility: str = ""


class MapMarker(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    category: str
    image: str = ""
    rating: float = 0.0
    entry_fee: int = 0


class SlotAvailability(BaseModel):
    time_slot: str
    capacity: int
    seats_taken: int
    seats_left: int
    is_available: bool


class AvailabilityOut(BaseModel):
    attraction_id: str
    visit_date: str
    slots: list[SlotAvailability]


class SimulatedLocationOut(ORMModel):
    id: str
    name: str
    coordinates: Coordinates
    description: str = ""


class ReviewOut(ORMModel):
    id: str
    user_name: str
    user_avatar: str = ""
    rating: float
    comment: str
    date: str


class ReviewCreate(BaseModel):
    rating: float = Field(ge=1, le=5)
    comment: str = Field(min_length=10, max_length=2000)
