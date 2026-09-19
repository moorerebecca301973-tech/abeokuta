from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.db.session import get_db
from app.models import Attraction, Category
from app.schemas.admin import AdminCategoryOut, CategoryCreate, CategoryUpdate

router = APIRouter(
    prefix="/admin/categories", tags=["admin"], dependencies=[Depends(require_admin)]
)


def _get_or_404(db: Session, slug: str) -> Category:
    category = db.get(Category, slug)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    return category


def _with_count(db: Session, category: Category) -> dict:
    count = db.scalar(
        select(func.count()).select_from(Attraction).where(
            Attraction.category_slug == category.slug
        )
    )
    return {
        "slug": category.slug,
        "name": category.name,
        "description": category.description,
        "icon": category.icon,
        "position": category.position,
        "attraction_count": count or 0,
    }


@router.get("", response_model=list[AdminCategoryOut])
def list_categories(db: Session = Depends(get_db)):
    rows = db.scalars(select(Category).order_by(Category.position)).all()
    return [_with_count(db, c) for c in rows]


@router.post("", response_model=AdminCategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db)):
    if db.get(Category, payload.slug) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "That slug is already in use")
    category = Category(**payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return _with_count(db, category)


@router.patch("/{slug}", response_model=AdminCategoryOut)
def update_category(slug: str, payload: CategoryUpdate, db: Session = Depends(get_db)):
    category = _get_or_404(db, slug)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, key, value)
    db.commit()
    db.refresh(category)
    return _with_count(db, category)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(slug: str, db: Session = Depends(get_db)):
    category = _get_or_404(db, slug)
    in_use = db.scalar(
        select(func.count()).select_from(Attraction).where(
            Attraction.category_slug == slug
        )
    )
    if in_use:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{in_use} attraction(s) still use this category; reassign them first",
        )
    db.delete(category)
    db.commit()
