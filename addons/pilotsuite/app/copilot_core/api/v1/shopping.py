"""Shopping List & Reminders REST API for PilotSuite.

Provides local persistent storage for:
- Shopping list items (add, complete, delete, list)
- Reminders with optional due dates (add, complete, snooze, list)

All data stored in SQLite (/data/shopping_reminders.db).
The LLM can use pilotsuite.shopping_list and pilotsuite.add_reminder tools.
"""

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
    completed = request.args.get("completed")
    with _lock:
        conn = _get_conn()
        try:
            if completed is not None:
                rows = conn.execute(
                    "SELECT * FROM shopping_items WHERE completed = ? ORDER BY created_at DESC",
                    (int(completed),),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM shopping_items ORDER BY completed ASC, created_at DESC"
                ).fetchall()
            items = [dict(r) for r in rows]
            return jsonify({"items": items, "count": len(items)})
        finally:
            conn.close()


@shopping_bp.route("/shopping", methods=["POST"])
@require_token
def add_shopping():
    """Add item(s) to shopping list. Body: {name, quantity?, category?} or {items: [...]}."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    items_to_add = data.get("items", [data]) if "items" in data else [data]
    added = []

    with _lock:
        conn = _get_conn()
        try:
            for item in items_to_add:
                name = item.get("name", "").strip()
                if not name:
                    continue
                item_id = f"shop_{uuid.uuid4().hex[:8]}"
                conn.execute(
                    "INSERT INTO shopping_items (id, name, quantity, category, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (item_id, name, item.get("quantity", ""), item.get("category", ""), time.time()),
                )
                added.append({"id": item_id, "name": name})
            conn.commit()
            return jsonify({"success": True, "added": added, "count": len(added)}), 201
        finally:
            conn.close()


@shopping_bp.route("/shopping/<item_id>/complete", methods=["POST"])
@require_token
def complete_shopping(item_id):
    """Mark a shopping item as completed."""
    with _lock:
        conn = _get_conn()
        try:
            cursor = conn.execute(
                "UPDATE shopping_items SET completed = 1, completed_at = ? WHERE id = ?",
                (time.time(), item_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return jsonify({"error": "Item not found"}), 404
            return jsonify({"success": True, "id": item_id})
        finally:
            conn.close()


@shopping_bp.route("/shopping/<item_id>", methods=["DELETE"])
@require_token
def delete_shopping(item_id):
    """Delete a shopping item."""
    with _lock:
        conn = _get_conn()
        try:
            cursor = conn.execute("DELETE FROM shopping_items WHERE id = ?", (item_id,))
            conn.commit()
            if cursor.rowcount == 0:
                return jsonify({"error": "Item not found"}), 404
            return jsonify({"success": True, "deleted": item_id})
        finally:
            conn.close()


@shopping_bp.route("/shopping/clear-completed", methods=["POST"])
@require_token
def clear_completed_shopping():
    """Delete all completed shopping items."""
    with _lock:
        conn = _get_conn()
        try:
            cursor = conn.execute("DELETE FROM shopping_items WHERE completed = 1")
            conn.commit()
            return jsonify({"success": True, "deleted": cursor.rowcount})
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Reminders endpoints
# ---------------------------------------------------------------------------

@shopping_bp.route("/reminders", methods=["GET"])
@require_token
def list_reminders():
    """List reminders. ?completed=0 for active, ?due=1 for due/overdue only."""
    completed = request.args.get("completed")
    due_only = request.args.get("due")

    with _lock:
        conn = _get_conn()
        try:
            if due_only:
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
                    (int(completed),),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM reminders ORDER BY completed ASC, due_at ASC NULLS LAST"
                ).fetchall()
            items = [dict(r) for r in rows]
            return jsonify({"reminders": items, "count": len(items)})
        finally:
            conn.close()


@shopping_bp.route("/reminders", methods=["POST"])
@require_token
def add_reminder():
    """Add a reminder. Body: {title, description?, due_at? (epoch), recurring?}."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    rem_id = f"rem_{uuid.uuid4().hex[:8]}"
    due_at = data.get("due_at")

    # Support ISO date strings as well as epoch
    if isinstance(due_at, str):
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
            due_at = dt.timestamp()
        except (ValueError, TypeError):
            due_at = None

    with _lock:
        conn = _get_conn()
        try:
            conn.execute(
                "INSERT INTO reminders (id, title, description, due_at, recurring, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (rem_id, title, data.get("description", ""),
                 due_at, data.get("recurring", ""), time.time()),
            )
            conn.commit()
            return jsonify({"success": True, "id": rem_id, "title": title}), 201
        finally:
            conn.close()


@shopping_bp.route("/reminders/<rem_id>/complete", methods=["POST"])
@require_token
def complete_reminder(rem_id):
    """Mark a reminder as completed."""
    with _lock:
        conn = _get_conn()
        try:
            cursor = conn.execute(
                "UPDATE reminders SET completed = 1, completed_at = ? WHERE id = ?",
                (time.time(), rem_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return jsonify({"error": "Reminder not found"}), 404
            return jsonify({"success": True, "id": rem_id})
        finally:
            conn.close()


@shopping_bp.route("/reminders/<rem_id>/snooze", methods=["POST"])
@require_token
def snooze_reminder(rem_id):
    """Snooze a reminder. Body: {minutes: 30} or {hours: 1}."""
    data = request.get_json() or {}
    minutes = int(data.get("minutes", 0)) + int(data.get("hours", 0)) * 60
    if minutes <= 0:
        minutes = 30  # default 30min snooze

    snooze_until = time.time() + minutes * 60
    with _lock:
        conn = _get_conn()
        try:
            cursor = conn.execute(
                "UPDATE reminders SET snoozed_until = ? WHERE id = ? AND completed = 0",
                (snooze_until, rem_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return jsonify({"error": "Reminder not found or already completed"}), 404
            return jsonify({"success": True, "id": rem_id, "snoozed_minutes": minutes})
        finally:
            conn.close()


@shopping_bp.route("/reminders/<rem_id>", methods=["DELETE"])
@require_token
def delete_reminder(rem_id):
    """Delete a reminder."""
    with _lock:
        conn = _get_conn()
        try:
            cursor = conn.execute("DELETE FROM reminders WHERE id = ?", (rem_id,))
            conn.commit()
            if cursor.rowcount == 0:
                return jsonify({"error": "Reminder not found"}), 404
            return jsonify({"success": True, "deleted": rem_id})
        finally:
            conn.close()


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
                    "ORDER BY due_at ASC NULLS LAST LIMIT 10",
                    (now,),
                ).fetchall()
                if not rows:
                    return ""
                lines = []
                for r in rows:
                    title = r["title"]
                    due = r["due_at"]
                    if due:
                        from datetime import datetime
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
