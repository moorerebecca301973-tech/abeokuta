from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_id, utcnow


class Category(Base):
    __tablename__ = "categories"

    slug: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(40), default="MapPin")
    position: Mapped[int] = mapped_column(Integer, default=0)

    attractions = relationship("Attraction", back_populates="category")


class Attraction(Base):
    __tablename__ = "attractions"

    # The slug is the primary key so the existing React route
    # /attractions/olumo-rock keeps working unchanged.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category_slug: Mapped[str] = mapped_column(
        ForeignKey("categories.slug"), index=True, nullable=False
    )
    tagline: Mapped[str] = mapped_column(String(240), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    history: Mapped[str] = mapped_column(Text, default="")
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    address: Mapped[str] = mapped_column(String(255), default="")
    neighborhood: Mapped[str] = mapped_column(String(120), default="", index=True)
    opening_hours: Mapped[str] = mapped_column(String(160), default="")
    entry_fee: Mapped[int] = mapped_column(Integer, default=0)
    child_entry_fee: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    image: Mapped[str] = mapped_column(String(500), default="")
    contact_phone: Mapped[str] = mapped_column(String(40), default="")
    audio_guide_duration: Mapped[str] = mapped_column(String(40), default="")
    audio_guide_summary: Mapped[str] = mapped_column(Text, default="")
    estimated_duration: Mapped[str] = mapped_column(String(60), default="")
    accessibility: Mapped[str] = mapped_column(Text, default="")
    featured: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    category = relationship("Category", back_populates="attractions")
    images = relationship(
        "AttractionImage", back_populates="attraction",
        cascade="all, delete-orphan", order_by="AttractionImage.position",
        lazy="selectin",
    )
    highlights = relationship(
        "AttractionHighlight", back_populates="attraction",
        cascade="all, delete-orphan", order_by="AttractionHighlight.position",
        lazy="selectin",
    )
    tips = relationship(
        "AttractionTip", back_populates="attraction",
        cascade="all, delete-orphan", order_by="AttractionTip.position",
        lazy="selectin",
    )
    tour_times = relationship(
        "TourTime", back_populates="attraction",
        cascade="all, delete-orphan", order_by="TourTime.position",
        lazy="selectin",
    )

    __table_args__ = (Index("ix_attractions_bbox", "lat", "lng"),)

    @property
    def gallery(self) -> list[str]:
        return [i.url for i in self.images]

    @property
    def highlight_list(self) -> list[str]:
        return [h.text for h in self.highlights]

    @property
    def tip_list(self) -> list[str]:
        return [t.text for t in self.tips]

    @property
    def tour_time_list(self) -> list[str]:
        return [t.slot_label for t in self.tour_times]


class AttractionImage(Base):
    __tablename__ = "attraction_images"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    attraction_id: Mapped[str] = mapped_column(
        ForeignKey("attractions.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0)

    attraction = relationship("Attraction", back_populates="images")


class AttractionHighlight(Base):
    __tablename__ = "attraction_highlights"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    attraction_id: Mapped[str] = mapped_column(
        ForeignKey("attractions.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0)

    attraction = relationship("Attraction", back_populates="highlights")


class AttractionTip(Base):
    __tablename__ = "attraction_tips"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    attraction_id: Mapped[str] = mapped_column(
        ForeignKey("attractions.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0)

    attraction = relationship("Attraction", back_populates="tips")


class TourTime(Base):
    __tablename__ = "tour_times"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    attraction_id: Mapped[str] = mapped_column(
        ForeignKey("attractions.id", ondelete="CASCADE"), index=True
    )
    slot_label: Mapped[str] = mapped_column(String(40), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=40)
    position: Mapped[int] = mapped_column(Integer, default=0)

    attraction = relationship("Attraction", back_populates="tour_times")


class SimulatedLocation(Base):
    __tablename__ = "simulated_locations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    position: Mapped[int] = mapped_column(Integer, default=0)
