from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class AddonOut(ORMModel):
    id: str
    name: str
    price: int
    description: str = ""


class BookingAddonOut(BaseModel):
    id: str
    name: str
    price: int


class QuoteRequest(BaseModel):
    attraction_id: str
    adults_count: int = Field(default=1, ge=1, le=20)
    children_count: int = Field(default=0, ge=0, le=20)
    addon_ids: list[str] = Field(default_factory=list, max_length=10)


class PriceLine(BaseModel):
    label: str
    amount: int


class QuoteOut(BaseModel):
    currency: str = "NGN"
    adult_fee: int
    child_fee: int
    base_amount: int
    addons_amount: int
    total_amount: int
    breakdown: list[PriceLine]


class BookingCreate(BaseModel):
    """Note what is absent: no total. The client never sends a price."""

    attraction_id: str = Field(max_length=64)
    visit_date: date
    time_slot: str = Field(max_length=40)
    adults_count: int = Field(default=1, ge=1, le=20)
    children_count: int = Field(default=0, ge=0, le=20)
    addon_ids: list[str] = Field(default_factory=list, max_length=10)
    contact_name: str = Field(min_length=2, max_length=120)
    contact_email: EmailStr
    contact_phone: str = Field(default="", max_length=40)
    payment_method: Literal["arrival", "card", "transfer"] = "arrival"


class BadgeOut(ORMModel):
    id: str
    title: str
    description: str = ""
    icon: str = "Award"
    unlocked: bool = False
    unlocked_date: str | None = None


class BookingOut(BaseModel):
    id: str
    booking_ref: str
    attraction_id: str
    attraction_name: str
    attraction_image: str = ""
    visit_date: date
    time_slot: str
    adults_count: int
    children_count: int
    addons: list[BookingAddonOut] = []
    base_amount: int
    addons_amount: int
    total_amount: int
    status: str
    payment_method: str
    contact_name: str
    contact_email: str
    contact_phone: str
    created_at: datetime


class BookingCreateOut(BaseModel):
    booking: BookingOut
    newly_unlocked_badges: list[BadgeOut] = []


class BookingPassOut(BaseModel):
    booking_ref: str
    attraction_name: str
    attraction_image: str = ""
    visit_date: date
    time_slot: str
    visitors: dict[str, int]
    total_amount: int
    status: str
    contact_name: str
    qr_payload: str
    qr_signature: str
    qr_png_base64: str
