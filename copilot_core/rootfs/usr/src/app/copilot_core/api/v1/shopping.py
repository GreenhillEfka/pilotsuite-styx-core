"""Shopping List & Reminders REST API for PilotSuite.

Provides local persistent storage for:
- Shopping list items (add, complete, delete, list)
- Reminders with optional due dates (add, complete, snooze, list)

All data stored in SQLite (/data/shopping_reminders.db).
The LLM can use pilotsuite.shopping_list and pilotsuite.add_reminder tools.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import Blueprint, request, jsonify
import logging
import os
import sqlite3
import threading
import time
import uuid

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

shopping_bp = Blueprint("shopping", __name__, url_prefix="/api/v1")

DB_PATH = os.environ.get("SHOPPING_DB_PATH", "/data/shopping_reminders.db")
_lock = threading.Lock()


def _error_response(message: str, status_code: int):
    return jsonify({"error": message}), status_code


def _handle_storage_exception(action: str, exc: Exception):
    logger.exception("Shopping API action failed: %s", action)
    return _error_response(str(exc), 500)


def _with_db(action: str, callback):
    try:
        with _lock:
            conn = _get_conn()
            try:
                return callback(conn), None
            finally:
                conn.close()
    except Exception as exc:  # pragma: no cover - exercised via contracts
        return None, _handle_storage_exception(action, exc)


def _require_json_object(*, required: bool = True):
    data = request.get_json(silent=True)
    if data is None:
        if required:
            return None, _error_response("Request body required", 400)
        return {}, None
    if not isinstance(data, dict):
        return None, _error_response("JSON body must be an object", 400)
    return data, None


def _parse_binary_query_flag(name: str):
    raw = request.args.get(name)
    if raw is None:
        return None, None
    if raw not in {"0", "1"}:
        return None, _error_response(f"{name} must be 0 or 1", 400)
    return int(raw), None


def _coerce_int(value: Any, field_name: str):
    if value in (None, ""):
        return 0, None
    try:
        return int(value), None
    except (TypeError, ValueError):
        return None, _error_response(f"{field_name} must be an integer", 400)


def _normalize_shopping_items(data: dict[str, Any]):
    raw_items = data.get("items")
    items_to_add = raw_items if raw_items is not None else [data]
    if not isinstance(items_to_add, list):
        return None, _error_response("items must be a list", 400)

    normalized_items: list[dict[str, Any]] = []
    for item in items_to_add:
        if not isinstance(item, dict):
            return None, _error_response("Each item must be an object", 400)
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        normalized_items.append(
            {
                "name": name,
                "quantity": item.get("quantity", ""),
                "category": item.get("category", ""),
            }
        )

    if not normalized_items:
        return None, _error_response("At least one item with a name is required", 400)
    return normalized_items, None


def _normalize_due_at(value: Any):
    if value in (None, ""):
        return None, None
    if isinstance(value, (int, float)):
        return float(value), None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp(), None
        except (TypeError, ValueError):
            return None, _error_response("due_at must be epoch seconds or ISO-8601", 400)
    return None, _error_response("due_at must be epoch seconds or ISO-8601", 400)


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    conn = _get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS shopping_items (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                quantity TEXT DEFAULT '',
                category TEXT DEFAULT '',
                completed INTEGER DEFAULT 0,
                created_at REAL NOT NULL,
                completed_at REAL
            );
            CREATE INDEX IF NOT EXISTS idx_shop_completed ON shopping_items(completed);

            CREATE TABLE IF NOT EXISTS reminders (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                due_at REAL,
                recurring TEXT DEFAULT '',
                completed INTEGER DEFAULT 0,
                snoozed_until REAL,
                created_at REAL NOT NULL,
                completed_at REAL
            );
            CREATE INDEX IF NOT EXISTS idx_rem_completed ON reminders(completed);
            CREATE INDEX IF NOT EXISTS idx_rem_due ON reminders(due_at);
        """)
        conn.commit()
    finally:
        conn.close()


# Initialize DB on import
try:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    _init_db()
except Exception:
    logger.warning("Failed to init shopping/reminders DB", exc_info=True)


# ---------------------------------------------------------------------------
# Shopping List endpoints
# ---------------------------------------------------------------------------

@shopping_bp.route("/shopping", methods=["GET"])
@require_token
def list_shopping():
    """List shopping items. ?completed=0 for active, =1 for done, omit for all."""
    completed, err = _parse_binary_query_flag("completed")
    if err:
        return err

    def _query(conn: sqlite3.Connection):
        if completed is not None:
            rows = conn.execute(
                "SELECT * FROM shopping_items WHERE completed = ? ORDER BY created_at DESC",
                (completed,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM shopping_items ORDER BY completed ASC, created_at DESC"
            ).fetchall()
        items = [dict(r) for r in rows]
        return jsonify({"items": items, "count": len(items)})

    response, err = _with_db("list_shopping", _query)
    if err:
        return err
    return response


@shopping_bp.route("/shopping", methods=["POST"])
@require_token
def add_shopping():
    """Add item(s) to shopping list. Body: {name, quantity?, category?} or {items: [...]}"""
    data, err = _require_json_object()
    if err:
        return err

    items_to_add, err = _normalize_shopping_items(data)
    if err:
        return err

    def _insert(conn: sqlite3.Connection):
        added = []
        for item in items_to_add:
            item_id = f"shop_{uuid.uuid4().hex[:8]}"
            conn.execute(
                "INSERT INTO shopping_items (id, name, quantity, category, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    item_id,
                    item["name"],
                    item.get("quantity", ""),
                    item.get("category", ""),
                    time.time(),
                ),
            )
            added.append({"id": item_id, "name": item["name"]})
        conn.commit()
        return jsonify({"success": True, "added": added, "count": len(added)}), 201

    response, err = _with_db("add_shopping", _insert)
    if err:
        return err
    return response


@shopping_bp.route("/shopping/<item_id>/complete", methods=["POST"])
@require_token
def complete_shopping(item_id):
    """Mark a shopping item as completed."""

    def _complete(conn: sqlite3.Connection):
        cursor = conn.execute(
            "UPDATE shopping_items SET completed = 1, completed_at = ? WHERE id = ?",
            (time.time(), item_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return _error_response("Item not found", 404)
        return jsonify({"success": True, "id": item_id})

    response, err = _with_db("complete_shopping", _complete)
    if err:
        return err
    return response


@shopping_bp.route("/shopping/<item_id>", methods=["DELETE"])
@require_token
def delete_shopping(item_id):
    """Delete a shopping item."""

    def _delete(conn: sqlite3.Connection):
        cursor = conn.execute("DELETE FROM shopping_items WHERE id = ?", (item_id,))
        conn.commit()
        if cursor.rowcount == 0:
            return _error_response("Item not found", 404)
        return jsonify({"success": True, "deleted": item_id})

    response, err = _with_db("delete_shopping", _delete)
    if err:
        return err
    return response


@shopping_bp.route("/shopping/clear-completed", methods=["POST"])
@require_token
def clear_completed_shopping():
    """Delete all completed shopping items."""

    def _clear(conn: sqlite3.Connection):
        cursor = conn.execute("DELETE FROM shopping_items WHERE completed = 1")
        conn.commit()
        return jsonify({"success": True, "deleted": cursor.rowcount})

    response, err = _with_db("clear_completed_shopping", _clear)
    if err:
        return err
    return response


# ---------------------------------------------------------------------------
# Reminders endpoints
# ---------------------------------------------------------------------------

@shopping_bp.route("/reminders", methods=["GET"])
@require_token
def list_reminders():
    """List reminders. ?completed=0 for active, ?due=1 for due/overdue only."""
    completed, err = _parse_binary_query_flag("completed")
    if err:
        return err
    due_only, err = _parse_binary_query_flag("due")
    if err:
        return err

    def _query(conn: sqlite3.Connection):
        if due_only == 1:
            now = time.time()
            rows = conn.execute(
                "SELECT * FROM reminders WHERE completed = 0 AND due_at IS NOT NULL "
                "AND due_at <= ? AND (snoozed_until IS NULL OR snoozed_until <= ?) "
                "ORDER BY due_at ASC",
                (now, now),
            ).fetchall()
        elif completed is not None:
            rows = conn.execute(
                "SELECT * FROM reminders WHERE completed = ? ORDER BY created_at DESC",
                (completed,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM reminders ORDER BY completed ASC, due_at IS NULL ASC, due_at ASC"
            ).fetchall()
        items = [dict(r) for r in rows]
        return jsonify({"reminders": items, "count": len(items)})

    response, err = _with_db("list_reminders", _query)
    if err:
        return err
    return response


@shopping_bp.route("/reminders", methods=["POST"])
@require_token
def add_reminder():
    """Add a reminder. Body: {title, description?, due_at? (epoch), recurring?}."""
    data, err = _require_json_object()
    if err:
        return err

    title = str(data.get("title", "")).strip()
    if not title:
        return _error_response("title is required", 400)

    due_at, err = _normalize_due_at(data.get("due_at"))
    if err:
        return err

    def _insert(conn: sqlite3.Connection):
        rem_id = f"rem_{uuid.uuid4().hex[:8]}"
        conn.execute(
            "INSERT INTO reminders (id, title, description, due_at, recurring, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                rem_id,
                title,
                data.get("description", ""),
                due_at,
                data.get("recurring", ""),
                time.time(),
            ),
        )
        conn.commit()
        return jsonify({"success": True, "id": rem_id, "title": title}), 201

    response, err = _with_db("add_reminder", _insert)
    if err:
        return err
    return response


@shopping_bp.route("/reminders/<rem_id>/complete", methods=["POST"])
@require_token
def complete_reminder(rem_id):
    """Mark a reminder as completed."""

    def _complete(conn: sqlite3.Connection):
        cursor = conn.execute(
            "UPDATE reminders SET completed = 1, completed_at = ? WHERE id = ?",
            (time.time(), rem_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return _error_response("Reminder not found", 404)
        return jsonify({"success": True, "id": rem_id})

    response, err = _with_db("complete_reminder", _complete)
    if err:
        return err
    return response


@shopping_bp.route("/reminders/<rem_id>/snooze", methods=["POST"])
@require_token
def snooze_reminder(rem_id):
    """Snooze a reminder. Body: {minutes: 30} or {hours: 1}."""
    data, err = _require_json_object(required=False)
    if err:
        return err

    minutes, err = _coerce_int(data.get("minutes", 0), "minutes")
    if err:
        return err
    hours, err = _coerce_int(data.get("hours", 0), "hours")
    if err:
        return err

    total_minutes = minutes + hours * 60
    if total_minutes <= 0:
        total_minutes = 30  # default 30min snooze

    snooze_until = time.time() + total_minutes * 60

    def _snooze(conn: sqlite3.Connection):
        cursor = conn.execute(
            "UPDATE reminders SET snoozed_until = ? WHERE id = ? AND completed = 0",
            (snooze_until, rem_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return _error_response("Reminder not found or already completed", 404)
        return jsonify({"success": True, "id": rem_id, "snoozed_minutes": total_minutes})

    response, err = _with_db("snooze_reminder", _snooze)
    if err:
        return err
    return response


@shopping_bp.route("/reminders/<rem_id>", methods=["DELETE"])
@require_token
def delete_reminder(rem_id):
    """Delete a reminder."""

    def _delete(conn: sqlite3.Connection):
        cursor = conn.execute("DELETE FROM reminders WHERE id = ?", (rem_id,))
        conn.commit()
        if cursor.rowcount == 0:
            return _error_response("Reminder not found", 404)
        return jsonify({"success": True, "deleted": rem_id})

    response, err = _with_db("delete_reminder", _delete)
    if err:
        return err
    return response


# ---------------------------------------------------------------------------
# LLM Context
# ---------------------------------------------------------------------------

def get_shopping_context_for_llm() -> str:
    """Build shopping list context for LLM system prompt."""
    try:
        with _lock:
            conn = _get_conn()
            try:
                items = conn.execute(
                    "SELECT name, quantity FROM shopping_items WHERE completed = 0 "
                    "ORDER BY created_at DESC LIMIT 15"
                ).fetchall()
                if not items:
                    return ""
                names = [f"{r['name']}" + (f" ({r['quantity']})" if r["quantity"] else "")
                         for r in items]
                return f"Einkaufsliste ({len(items)} Artikel): {', '.join(names)}"
            finally:
                conn.close()
    except Exception:
        return ""


def get_reminders_context_for_llm() -> str:
    """Build reminders context for LLM system prompt."""
    try:
        now = time.time()
        with _lock:
            conn = _get_conn()
            try:
                # Active reminders, prioritize due/overdue
                rows = conn.execute(
                    "SELECT title, due_at FROM reminders WHERE completed = 0 "
                    "AND (snoozed_until IS NULL OR snoozed_until <= ?) "
                    "ORDER BY due_at IS NULL ASC, due_at ASC LIMIT 10",
                    (now,),
                ).fetchall()
                if not rows:
                    return ""
                lines = []
                for r in rows:
                    title = r["title"]
                    due = r["due_at"]
                    if due:
                        due_dt = datetime.fromtimestamp(due)
                        if due <= now:
                            lines.append(f"  UEBERFAELLIG: {title} (seit {due_dt.strftime('%d.%m %H:%M')})")
                        else:
                            lines.append(f"  {title} (faellig: {due_dt.strftime('%d.%m %H:%M')})")
                    else:
                        lines.append(f"  {title}")
                return f"Erinnerungen ({len(rows)} aktiv):\n" + "\n".join(lines)
            finally:
                conn.close()
    except Exception:
        return ""
