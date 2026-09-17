from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class UserOut(ORMModel):
    id: str
    name: str
    email: EmailStr
    phone: str = ""
    origin: str = ""
    avatar: str = ""
    interests: list[str] = []
    created_at: datetime


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    origin: str | None = Field(default=None, max_length=120)
    avatar: str | None = Field(default=None, max_length=500)
    interests: list[str] | None = Field(default=None, max_length=20)


class UserStats(BaseModel):
    saved_count: int
    booking_count: int
    upcoming_count: int
    badges_unlocked: int
    badges_total: int
