from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models import CulturalFact
from app.schemas.geo import CulturalFactOut

router = APIRouter(tags=["meta"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    """Touches the database on purpose.

    A health check that passes while the disk is unmounted is worse than none.
    """
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "database": "reachable",
    }


@router.get("/meta/cultural-facts", response_model=list[CulturalFactOut])
def cultural_facts(db: Session = Depends(get_db)):
    return db.scalars(select(CulturalFact).order_by(CulturalFact.position)).all()
