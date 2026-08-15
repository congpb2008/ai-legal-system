"""Shared contract primitives.

Implementation conveniences for the canonical contract field types (UUID,
datetime). These do not extend or alter any contract; they only make contract
field types ergonomic in Python while keeping values canonical (UTC, UUIDv4).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4


def now_utc() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def new_id() -> UUID:
    """Generate a new random UUID (UUIDv4) for an entity identifier."""
    return uuid4()


def to_utc(dt: datetime) -> datetime:
    """Normalize a datetime to timezone-aware UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def utc_iso(dt: datetime) -> str:
    """Render a datetime as an ISO-8601 UTC string (for storage/logging)."""
    return to_utc(dt).isoformat()
