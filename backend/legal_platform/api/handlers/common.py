"""Common helpers and constants for API handlers."""
from __future__ import annotations

import json
import time
from typing import Any


_START_TIME = time.time()


def _document_metadata_from_body(body: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize the mutable metadata fields exposed by the public API."""
    raw_metadata = body.get("metadata")
    if raw_metadata is not None and not isinstance(raw_metadata, dict):
        raise ValueError("metadata must be an object")
    metadata: dict[str, Any] = dict(raw_metadata or {})
    touched = raw_metadata is not None

    if "tags" in body:
        raw_tags = body.get("tags")
        if isinstance(raw_tags, str):
            stripped = raw_tags.strip()
            if stripped.startswith("["):
                try:
                    raw_tags = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise ValueError("tags must be a comma-separated list or JSON array") from exc
            else:
                raw_tags = [part.strip() for part in stripped.replace("\n", ",").split(",")]
        if raw_tags is None:
            raw_tags = []
        if not isinstance(raw_tags, list) or not all(isinstance(tag, str) for tag in raw_tags):
            raise ValueError("tags must be a list of strings")
        tags: list[str] = []
        seen: set[str] = set()
        for raw_tag in raw_tags:
            tag = " ".join(raw_tag.strip().split())
            if not tag:
                continue
            if len(tag) > 64:
                raise ValueError("each tag must be at most 64 characters")
            if any(ord(char) < 32 for char in tag):
                raise ValueError("tags cannot contain control characters")
            key = tag.casefold()
            if key not in seen:
                seen.add(key)
                tags.append(tag)
        if len(tags) > 20:
            raise ValueError("a document can have at most 20 tags")
        metadata["tags"] = tags
        touched = True

    for field in ("issue_date", "effective_date", "expiration_date"):
        if field in body:
            value = body.get(field)
            if isinstance(value, str) and value and len(value) == 10:
                value = f"{value}T00:00:00Z"
            metadata[field] = value or None
            touched = True

    return metadata if touched else None
