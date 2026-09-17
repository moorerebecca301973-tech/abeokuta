import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.deps import get_current_user
from app.core.security import (
    REFRESH, create_access_token, create_refresh_token, decode_token,
    fingerprint, hash_password, verify_password,
)
from app.db.base import utcnow
from app.db.session import get_db
from app.models import RefreshToken, User
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenPair
from app.schemas.common import Message
from app.schemas.user import UserOut
from app.services.serialize import user_out
from datetime import timedelta

router = APIRouter(prefix="/auth", tags=["auth"])

DEFAULT_AVATAR = (
    "https://images.unsplash.com/photo-1534528741775-53994a69daeb"
    "?auto=format&fit=crop&w=300&q=80"
)


def _issue_tokens(db: Session, user: User) -> dict:
    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=fingerprint(refresh),
            expires_at=utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    db.commit()
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": user_out(user),
    }


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An account with that email already exists"
        )

    user = User(
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        phone=payload.phone.strip(),
        origin=payload.origin.strip() or "Abeokuta Visitor",
        avatar_url=DEFAULT_AVATAR,
        interests=json.dumps(["History", "Markets"]),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue_tokens(db, user)


@router.post("/login", response_model=TokenPair)
@limiter.limit("10/minute")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower().strip()))
    # Same message either way: do not reveal which accounts exist.
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "That email and password do not match"
        )
    return _issue_tokens(db, user)


@router.post("/demo", response_model=TokenPair)
def demo_login(db: Session = Depends(get_db)):
    """Replaces quickDemoLogin() in TourismContext."""
    user = db.scalar(select(User).where(User.is_demo.is_(True)))
    if user is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The demo account is not available. Run the seeder.",
        )
    return _issue_tokens(db, user)


@router.post("/refresh", response_model=TokenPair)
def refresh_tokens(payload: RefreshRequest, db: Session = Depends(get_db)):
    user_id = decode_token(payload.refresh_token, REFRESH)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    stored = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == fingerprint(payload.refresh_token)
        )
    )
    if stored is None or not stored.is_active:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "This session has been signed out"
        )

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found")

    # Rotate: the presented token can never be replayed.
    stored.revoked_at = utcnow()
    db.commit()
    return _issue_tokens(db, user)


@router.post("/logout", response_model=Message)
def logout(payload: RefreshRequest, db: Session = Depends(get_db)):
    stored = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == fingerprint(payload.refresh_token)
        )
    )
    if stored and stored.revoked_at is None:
        stored.revoked_at = utcnow()
        db.commit()
    # Always 200: logging out twice is not an error.
    return {"detail": "Signed out"}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user_out(user)
