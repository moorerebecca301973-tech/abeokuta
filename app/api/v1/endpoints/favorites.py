from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import Attraction, Favorite, User
from app.schemas.attraction import AttractionListItem
from app.schemas.common import Message
from app.services.serialize import attraction_list_item

router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.get("", response_model=list[AttractionListItem])
def list_favorites(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    rows = db.scalars(
        select(Attraction)
        .join(Favorite, Favorite.attraction_id == Attraction.id)
        .options(selectinload(Attraction.category))
        .where(Favorite.user_id == user.id)
        .order_by(Favorite.created_at.desc())
    ).unique().all()
    return [attraction_list_item(a, None, True) for a in rows]


@router.post("/{attraction_id}", response_model=Message, status_code=status.HTTP_201_CREATED)
def add_favorite(
    attraction_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if db.get(Attraction, attraction_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Landmark not found")
    # Composite primary key makes a duplicate impossible; treat it as success
    # so the UI's optimistic toggle never has to reconcile.
    if db.get(Favorite, (user.id, attraction_id)) is None:
        db.add(Favorite(user_id=user.id, attraction_id=attraction_id))
        db.commit()
    return {"detail": "Landmark saved to your profile"}


@router.delete("/{attraction_id}", response_model=Message)
def remove_favorite(
    attraction_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    favorite = db.get(Favorite, (user.id, attraction_id))
    if favorite is not None:
        db.delete(favorite)
        db.commit()
    return {"detail": "Landmark removed from saved places"}
