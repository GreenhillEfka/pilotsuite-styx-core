"""Conversation History REST API Blueprint.

Prefix: /api/v1/conversation
Exposes ConversationMemory for dashboard chat log display.
"""

import logging
import time
from typing import Any, Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

conversation_history_bp = Blueprint(
    "conversation_history", __name__, url_prefix="/api/v1/conversation"
)

_memory: Optional[Any] = None


def init_conversation_history_api(memory) -> None:
    """Wire ConversationMemory into API blueprint."""
    global _memory
    _memory = memory


def _require_memory():
    if _memory is None:
        return None, (jsonify({"ok": False, "error": "ConversationMemory not initialized"}), 503)
    return _memory, None


@conversation_history_bp.route("/history", methods=["GET"])
@require_token
def get_history():
    """Recent conversation messages (newest first).

    Query params:
        limit (int): Max messages to return (default 50, max 200)
        offset (int): Skip first N messages (default 0)
        role (str): Filter by role (user|assistant)
    """
    mem, err = _require_memory()
    if err:
        return err

    try:
        limit = min(int(request.args.get("limit", 50)), 200)
        offset = int(request.args.get("offset", 0))
    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "Invalid limit/offset parameter"}), 400
    role_filter = request.args.get("role")
    if role_filter and role_filter not in ("user", "assistant"):
        return jsonify({"ok": False, "error": "role must be 'user' or 'assistant'"}), 400

    import sqlite3

    with mem._lock:
        conn = sqlite3.connect(mem._db_path)
        try:
            query = "SELECT id, timestamp, role, content, character, topic_tags, conversation_id FROM conversations"
            params: list = []

            if role_filter:
                query += " WHERE role = ?"
                params.append(role_filter)

            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            rows = conn.execute(query, params).fetchall()

            total = conn.execute(
                "SELECT COUNT(*) FROM conversations" + (" WHERE role = ?" if role_filter else ""),
                [role_filter] if role_filter else [],
            ).fetchone()[0]

            messages = [
                {
                    "id": row[0],
                    "timestamp": row[1],
                    "role": row[2],
                    "content": row[3],
                    "character": row[4],
                    "topics": [t for t in (row[5] or "").split(",") if t],
                    "conversation_id": row[6],
                }
                for row in rows
            ]
        finally:
            conn.close()

    return jsonify({
        "ok": True,
        "messages": messages,
        "total": total,
        "limit": limit,
        "offset": offset,
    })


@conversation_history_bp.route("/history/<conversation_id>", methods=["GET"])
@require_token
def get_conversation(conversation_id: str):
    """Messages for a specific conversation (chronological)."""
    mem, err = _require_memory()
    if err:
        return err

    try:
        limit = min(int(request.args.get("limit", 50)), 200)
    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "Invalid limit parameter"}), 400
    messages = mem.get_conversation_history(conversation_id, limit=limit) or []
    return jsonify({"ok": True, "conversation_id": conversation_id, "messages": messages})


@conversation_history_bp.route("/preferences", methods=["GET"])
@require_token
def get_preferences():
    """Learned user preferences."""
    mem, err = _require_memory()
    if err:
        return err

    prefs = mem.get_user_preferences()
    return jsonify({
        "ok": True,
        "preferences": [
            {
                "key": p.key,
                "value": p.value,
                "confidence": round(p.confidence, 3),
                "source": p.source,
                "last_updated": p.last_updated,
                "mention_count": p.mention_count,
            }
            for p in prefs
        ],
    })


@conversation_history_bp.route("/stats", methods=["GET"])
@require_token
def get_stats():
    """Conversation memory statistics."""
    mem, err = _require_memory()
    if err:
        return err

    return jsonify({"ok": True, **mem.get_stats()})
