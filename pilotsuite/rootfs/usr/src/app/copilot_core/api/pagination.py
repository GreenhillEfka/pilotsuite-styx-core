"""Cursor-based pagination helpers for list endpoints.

Cursor pagination avoids the problems of offset pagination when data changes
between pages (skipped/duplicate items) and is more performant on large tables.

Usage::

    from copilot_core.api.pagination import cursor_page, PageResult

    @bp.get("/entities")
    def list_entities():
        before  = request.args.get("before")   # opaque cursor
        after   = request.args.get("after")    # opaque cursor
        limit   = min(int(request.args.get("limit", 20)), 100)

        entities, has_next, has_prev = fetch_entities(before, after, limit + 1)

        page = cursor_page(
            items      = entities[:limit],
            before     = before,
            after      = after,
            has_next   = has_next,
            has_prev   = has_prev,
            total      = total_count,          # optional
            build_next = lambda item: item["id"],
            build_prev = lambda item: item["id"],
        )
        return jsonify(page)

    # fetch_entities returns (items, has_next, has_prev)
    def fetch_entities(before, after, limit):
        query = Entity.query
        if before:
            query = query.filter(Entity.id < before)
        if after:
            query = query.filter(Entity.id > after)
        items = query.order_by(Entity.id.desc()).limit(limit).all()
        return items, len(items) == limit, bool(before or after)
"""

from __future__ import annotations

import base64
import json
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar

from flask import request


T = TypeVar("T")


# ── Cursor encoding ─────────────────────────────────────────────────────


def _encode_cursor(data: Dict[str, Any]) -> str:
    """Encode a cursor dict to an opaque URL-safe string."""
    # Use JSON so field order is stable; double-encode so characters
    # like "/" don't appear in the cursor string.
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> Optional[Dict[str, Any]]:
    """Decode an opaque cursor string back to a dict, or None if invalid."""
    try:
        padded = cursor + "=" * (4 - len(cursor) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode()).decode()
        return json.loads(decoded)
    except Exception:
        return None


# ── Page result dataclass ────────────────────────────────────────────────


@dataclass
class PageResult(Generic[T]):
    """Standardised pagination response envelope.

    Attributes:
        items: List of items for the current page.
        total: Optional total count (omit for very large/unbounded sets).
        page_info: Cursor navigation info.
        pagination: Pagination metadata (limit, direction).
    """

    items: List[Any]
    total: Optional[int] = None
    page_info: Dict[str, Any] = field(default_factory=dict)
    pagination: Dict[str, Any] = field(default_factory=dict)


# ── Core builder ────────────────────────────────────────────────────────


def cursor_page(
    items: List[T],
    before: Optional[str],
    after: Optional[str],
    has_next: bool,
    has_prev: bool,
    limit: int,
    total: Optional[int] = None,
    build_next: Optional[Callable[[T], Any]] = None,
    build_prev: Optional[Callable[[T], Any]] = None,
    item_to_dict: bool = True,
) -> Dict[str, Any]:
    """Build a cursor-paginated response dict.

    The opaque cursors encode the sort field(s) of the edge items so clients
    can navigate without knowing the internal schema.

    Args:
        items: Items for the current page (may be one over limit to detect
            whether a next page exists; caller trims before calling this).
        before: ``before`` cursor sent by the client (or None).
        after: ``after`` cursor sent by the client (or None).
        has_next: True if there are items after the last item in ``items``.
        has_prev: True if there are items before the first item in ``items``.
        limit: Page size requested by the client.
        total: Optional total item count.
        build_next: Function(item) -> value used as the ``next_cursor`` anchor.
            Defaults to item["id"] if items are dicts, else str(item).
        build_prev: Function(item) -> value used as the ``prev_cursor`` anchor.
            Defaults to item["id"] if items are dicts, else str(item).
        item_to_dict: Convert items to dicts using ``dict()`` (safe for ORM
            objects with ``.to_dict()``). Set False if items are already dicts
            and you manage conversion yourself.

    Returns:
        Dict suitable for ``jsonify()``.
    """
    # Detect next/prev from the actual last/first items
    first = items[0] if items else None
    last = items[-1] if items else None

    def _id(item):
        if item is None:
            return None
        if isinstance(item, dict):
            return item.get("id")
        return getattr(item, "id", None)

    next_id = _id(last) if has_next and last is not None else None
    prev_id = _id(first) if has_prev and first is not None else None

    if build_next is not None and next_id is not None:
        next_id = build_next(last)
    if build_prev is not None and prev_id is not None:
        prev_id = build_prev(first)

    def _encode(val) -> Optional[str]:
        if val is None:
            return None
        return _encode_cursor({"id": val})

    next_cursor = _encode(next_id)
    prev_cursor = _encode(prev_id)

    rendered_items = items
    if item_to_dict and items:
        try:
            rendered_items = [dict(i) if not isinstance(i, dict) else i for i in items]
        except Exception:
            # Items don't have a simple dict conversion; try .to_dict()
            rendered_items = []
            for i in items:
                if hasattr(i, "to_dict"):
                    rendered_items.append(i.to_dict())
                else:
                    rendered_items.append(i)

    result: Dict[str, Any] = {
        "items": rendered_items,
        "count": len(rendered_items),
        "page_info": {
            "has_next_page": has_next,
            "has_previous_page": has_prev,
            "next_cursor": next_cursor,
            "previous_cursor": prev_cursor,
            "direction": "forward" if after else "backward" if before else "first",
        },
        "pagination": {
            "limit": limit,
            "requested_limit": int(request.args.get("limit", limit)) if request else limit,
        },
    }

    if total is not None:
        result["total"] = total
        result["page_info"]["total_count"] = total
        if total > 0 and limit > 0:
            # Approximate page count (real cursors don't need this, but clients
            # sometimes use it for progress bars)
            result["page_info"]["approximate_page_count"] = math.ceil(total / limit)

    return result


# ── Offset-based fallback helpers ───────────────────────────────────────


def offset_page(
    items: List[T],
    total: int,
    limit: int,
    offset: int,
) -> Dict[str, Any]:
    """Build an offset-based paginated response (for compatibility).

    Prefer cursor pagination for new endpoints. This helper wraps the classic
    offset+limit pattern with the same envelope shape so clients can switch
    to cursor-based pagination later.

    Args:
        items: Items for the current page.
        total: Total number of items across all pages.
        limit: Page size.
        offset: Current offset.

    Returns:
        Dict suitable for ``jsonify()``.
    """
    page_size = len(items)
    current_page = (offset // limit) + 1 if limit > 0 else 1
    total_pages = math.ceil(total / limit) if limit > 0 else 1

    return {
        "items": items if not isinstance(items[0], object) or hasattr(items[0], "to_dict") else items,
        "count": page_size,
        "total": total,
        "pagination": {
            "type": "offset",
            "limit": limit,
            "offset": offset,
            "current_page": current_page,
            "total_pages": total_pages,
            "has_next_page": offset + page_size < total,
            "has_previous_page": offset > 0,
        },
    }
