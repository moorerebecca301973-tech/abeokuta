"""Shared limiter.

Lives here rather than in main.py so endpoint modules can import it without
a circular import (main -> router -> endpoints -> main).
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    # Tests hit /auth/register repeatedly from one address; limiting there
    # would fail the suite for the wrong reason.
    enabled=settings.ENVIRONMENT != "test",
)
