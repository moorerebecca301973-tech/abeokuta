from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Attraction, Category
from app.schemas.attraction import CategoryOut

router = APIRouter(prefix="/categories", tags=["catalog"])


@router.get("", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    counts = dict(
        db.execute(
            select(Attraction.category_slug, func.count(Attraction.id))
            .where(Attraction.is_active.is_(True))
            .group_by(Attraction.category_slug)
        ).all()
    )
    return [
        {
            "slug": c.slug,
            "name": c.name,
            "description": c.description,
            "icon": c.icon,
            "attraction_count": counts.get(c.slug, 0),
        }
        for c in db.scalars(select(Category).order_by(Category.position)).all()
    ]
