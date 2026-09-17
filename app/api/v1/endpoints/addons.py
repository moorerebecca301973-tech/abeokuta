from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Addon
from app.schemas.booking import AddonOut

router = APIRouter(prefix="/addons", tags=["catalog"])


@router.get("", response_model=list[AddonOut])
def list_addons(db: Session = Depends(get_db)):
    return db.scalars(
        select(Addon).where(Addon.is_active.is_(True)).order_by(Addon.price)
    ).all()
