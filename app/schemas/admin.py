"""Schemas used only by the admin API (/admin/...).

Kept separate from app/schemas/attraction.py because the admin shape is
different on purpose: it exposes fields the public API hides (is_active,
category_slug, created_at, row ids for sub-items) and accepts full
create/update payloads rather than the read-only public views.
"""
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


# ---- attraction sub-item schemas ------------------------------------------

class ImageIn(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    position: int = 0


class ImageOut(ORMModel):
    id: str
    url: str
    position: int


class HighlightIn(BaseModel):
    text: str = Field(min_length=1)
    position: int = 0


class HighlightOut(ORMModel):
    id: str
    text: str
    position: int


class TipIn(BaseModel):
    text: str = Field(min_length=1)
    position: int = 0


class TipOut(ORMModel):
    id: str
    text: str
    position: int


class TourTimeIn(BaseModel):
    slot_label: str = Field(min_length=1, max_length=40)
    capacity: int = Field(default=40, ge=1)
    position: int = 0


class TourTimeOut(ORMModel):
    id: str
    slot_label: str
    capacity: int
    position: int


# ---- attraction ------------------------------------------------------------

class AttractionCreate(BaseModel):
    id: str = Field(min_length=1, max_length=64, description="URL slug, e.g. olumo-rock")
    name: str = Field(min_length=1, max_length=160)
    category_slug: str = Field(min_length=1, max_length=64)
    tagline: str = Field(default="", max_length=240)
    description: str = ""
    history: str = ""
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    address: str = Field(default="", max_length=255)
    neighborhood: str = Field(default="", max_length=120)
    opening_hours: str = Field(default="", max_length=160)
    entry_fee: int = Field(default=0, ge=0)
    child_entry_fee: int | None = Field(default=None, ge=0)
    image: str = Field(default="", max_length=500)
    contact_phone: str = Field(default="", max_length=40)
    audio_guide_duration: str = Field(default="", max_length=40)
    audio_guide_summary: str = ""
    estimated_duration: str = Field(default="", max_length=60)
    accessibility: str = ""
    featured: bool = False
    is_active: bool = True
    images: list[ImageIn] = []
    highlights: list[HighlightIn] = []
    tips: list[TipIn] = []
    tour_times: list[TourTimeIn] = []


class AttractionUpdate(BaseModel):
    """All fields optional; only keys the admin actually sends are applied.

    Sending `images`, `highlights`, `tips`, or `tour_times` replaces that
    whole sub-list (it's an edit-and-save form field, not an append).
    """

    name: str | None = Field(default=None, min_length=1, max_length=160)
    category_slug: str | None = Field(default=None, min_length=1, max_length=64)
    tagline: str | None = Field(default=None, max_length=240)
    description: str | None = None
    history: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    address: str | None = Field(default=None, max_length=255)
    neighborhood: str | None = Field(default=None, max_length=120)
    opening_hours: str | None = Field(default=None, max_length=160)
    entry_fee: int | None = Field(default=None, ge=0)
    child_entry_fee: int | None = Field(default=None, ge=0)
    image: str | None = Field(default=None, max_length=500)
    contact_phone: str | None = Field(default=None, max_length=40)
    audio_guide_duration: str | None = Field(default=None, max_length=40)
    audio_guide_summary: str | None = None
    estimated_duration: str | None = Field(default=None, max_length=60)
    accessibility: str | None = None
    featured: bool | None = None
    is_active: bool | None = None
    images: list[ImageIn] | None = None
    highlights: list[HighlightIn] | None = None
    tips: list[TipIn] | None = None
    tour_times: list[TourTimeIn] | None = None


class AdminAttractionOut(ORMModel):
    id: str
    name: str
    category_slug: str
    tagline: str
    description: str
    history: str
    lat: float
    lng: float
    address: str
    neighborhood: str
    opening_hours: str
    entry_fee: int
    child_entry_fee: int | None
    rating: float
    review_count: int
    image: str
    contact_phone: str
    audio_guide_duration: str
    audio_guide_summary: str
    estimated_duration: str
    accessibility: str
    featured: bool
    is_active: bool
    created_at: datetime
    images: list[ImageOut] = []
    highlights: list[HighlightOut] = []
    tips: list[TipOut] = []
    tour_times: list[TourTimeOut] = []


# ---- category ---------------------------------------------------------------

class CategoryCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=80)
    description: str = ""
    icon: str = Field(default="MapPin", max_length=40)
    position: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = None
    icon: str | None = Field(default=None, max_length=40)
    position: int | None = None


class AdminCategoryOut(ORMModel):
    slug: str
    name: str
    description: str
    icon: str
    position: int
    attraction_count: int = 0
