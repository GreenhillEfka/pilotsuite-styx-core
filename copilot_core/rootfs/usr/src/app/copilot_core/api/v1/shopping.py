"""Shopping list + reminders API (v8.4).

This module is intentionally small but complete because both the dashboard
and the conversation tool layer depend on it.

Endpoints:
  GET    /api/v1/shopping
  POST   /api/v1/shopping
  POST   /api/v1/shopping/<item_id>/complete
  POST   /api/v1/shopping/<item_id>/reopen
  DELETE /api/v1/shopping/<item_id>

  GET    /api/v1/reminders
  POST   /api/v1/reminders
  POST   /api/v1/reminders/<reminder_id>/complete
  POST   /api/v1/reminders/<reminder_id>/snooze
  GET    /api/v1/reminders/explain
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
import sqlite3
import threading
import time
import uuid
from typing import Any

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

shopping_bp = Blueprint("shopping", __name__, url_prefix="/api/v1")

_DB_PATH = os.environ.get("SHOPPING_REMINDERS_DB_PATH", "/data/shopping_reminders.db")
_lock = threading.RLock()
_db_initialized_for: str | None = None


def _now_ts() -> float:
    return time.time()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_conn() -> sqlite3.Connection:
    """Get sqlite connection with schema initialized."""
    global _db_initialized_for
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    if _db_initialized_for != _DB_PATH:
        with _lock:
            if _db_initialized_for != _DB_PATH:
                _init_db(conn)
                _db_initialized_for = _DB_PATH
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS shopping_items (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            quantity TEXT DEFAULT '',
            category TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            source TEXT DEFAULT 'dashboard',
            created_by TEXT DEFAULT 'user',
            created_at REAL NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            completed_at REAL
        );

        CREATE TABLE IF NOT EXISTS reminders (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            due_at REAL,
            recurring TEXT DEFAULT '',
            source TEXT DEFAULT 'dashboard',
            created_by TEXT DEFAULT 'user',
            trigger_reason TEXT DEFAULT '',
            origin_entity_id TEXT DEFAULT '',
            created_at REAL NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            completed_at REAL,
            snoozed_until REAL
        );

        CREATE TABLE IF NOT EXISTS reminder_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reminder_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            detail TEXT DEFAULT '',
            created_at REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_shopping_completed ON shopping_items(completed, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_reminders_active ON reminders(completed, due_at, snoozed_until);
        CREATE INDEX IF NOT EXISTS idx_reminder_events_reminder ON reminder_events(reminder_id, created_at DESC);
        """
    )
    conn.commit()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def _safe_int(raw: Any, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


def _parse_due_timestamp(body: dict[str, Any]) -> float | None:
    """Parse due time from unix ts / ISO string / relative minutes."""
    due_at = body.get("due_at")
    if isinstance(due_at, (int, float)):
        return float(due_at)
    if isinstance(due_at, str) and due_at.strip():
        text = due_at.strip()
        try:
            if text.isdigit():
                return float(text)
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return dt.timestamp()
        except Exception:
            return None
    due_in_minutes = body.get("due_in_minutes")
    if isinstance(due_in_minutes, (int, float)):
        return _now_ts() + max(1.0, float(due_in_minutes)) * 60.0
    return None


def _insert_reminder_event(conn: sqlite3.Connection, reminder_id: str, event_type: str, detail: str = "") -> None:
    conn.execute(
        "INSERT INTO reminder_events (reminder_id, event_type, detail, created_at) VALUES (?, ?, ?, ?)",
        (reminder_id, event_type, detail, _now_ts()),
    )


def _reminder_status_reason(row: dict[str, Any], now_ts: float) -> str:
    if int(row.get("completed") or 0) == 1:
        return "completed"
    snoozed_until = row.get("snoozed_until")
    if isinstance(snoozed_until, (int, float)) and snoozed_until > now_ts:
        return "snoozed"
    due_at = row.get("due_at")
    if isinstance(due_at, (int, float)):
        if due_at < now_ts:
            return "overdue"
        return "scheduled"
    return "open"


def get_shopping_context_for_llm() -> str:
    """Compact shopping-list context for prompt injection."""
    try:
        with _lock:
            conn = _get_conn()
            try:
                rows = conn.execute(
                    "SELECT name, quantity, category FROM shopping_items "
                    "WHERE completed = 0 ORDER BY created_at DESC LIMIT 8"
                ).fetchall()
            finally:
                conn.close()
        if not rows:
            return ""
        items: list[str] = []
        for row in rows:
            quantity = str(row["quantity"] or "").strip()
            suffix = f" ({quantity})" if quantity else ""
            items.append(f"- {row['name']}{suffix}")
        return "Einkaufsliste:\n" + "\n".join(items)
    except Exception:
        return ""


def get_reminders_context_for_llm() -> str:
    """Compact reminders context for prompt injection."""
    try:
        now = _now_ts()
        with _lock:
            conn = _get_conn()
            try:
                rows = conn.execute(
                    "SELECT title, due_at, snoozed_until, trigger_reason "
                    "FROM reminders WHERE completed = 0 "
                    "ORDER BY CASE WHEN due_at IS NULL THEN 1 ELSE 0 END, due_at ASC, created_at DESC LIMIT 8"
                ).fetchall()
            finally:
                conn.close()
        if not rows:
            return ""
        lines: list[str] = []
        for row in rows:
            title = str(row["title"] or "")
            due_at = row["due_at"]
            snoozed_until = row["snoozed_until"]
            reason = str(row["trigger_reason"] or "").strip()
            tag = ""
            if isinstance(snoozed_until, (int, float)) and snoozed_until > now:
                tag = " (gesnoozed)"
            elif isinstance(due_at, (int, float)):
                if due_at < now:
                    tag = " (überfällig)"
                else:
                    delta_min = int(max(0.0, due_at - now) // 60)
                    tag = f" (in {delta_min} Min)" if delta_min < 180 else ""
            if reason:
                lines.append(f"- {title}{tag} — Grund: {reason}")
            else:
                lines.append(f"- {title}{tag}")
        return "Erinnerungen:\n" + "\n".join(lines)
    except Exception:
        return ""


@shopping_bp.route("/shopping", methods=["GET"])
@require_token
def list_shopping_items():
    completed = str(request.args.get("completed", "0")).strip().lower()
    limit = _safe_int(request.args.get("limit", "100"), 100, minimum=1, maximum=500)
    where_sql = ""
    params: tuple[Any, ...] = ()
    if completed in {"0", "false", "open"}:
        where_sql = "WHERE completed = 0"
    elif completed in {"1", "true", "done"}:
        where_sql = "WHERE completed = 1"
    sql = (
        "SELECT id, name, quantity, category, notes, source, created_by, created_at, completed, completed_at "
        f"FROM shopping_items {where_sql} ORDER BY created_at DESC LIMIT ?"
    )
    params = (*params, limit)
    with _lock:
        conn = _get_conn()
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
    items = [_row_to_dict(row) for row in rows]
    return jsonify({"ok": True, "count": len(items), "items": items})


@shopping_bp.route("/shopping", methods=["POST"])
@require_token
def add_shopping_item():
    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    if not name:
        return jsonify({"ok": False, "error": "name_required"}), 400
    item_id = str(body.get("id") or f"shop_{uuid.uuid4().hex[:10]}")
    quantity = str(body.get("quantity", "")).strip()
    category = str(body.get("category", "")).strip()
    notes = str(body.get("notes", "")).strip()
    source = str(body.get("source", "dashboard") or "dashboard")
    created_by = str(body.get("created_by", "user") or "user")
    with _lock:
        conn = _get_conn()
        try:
            conn.execute(
                "INSERT INTO shopping_items (id, name, quantity, category, notes, source, created_by, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (item_id, name, quantity, category, notes, source, created_by, _now_ts()),
            )
            conn.commit()
        finally:
            conn.close()
    return jsonify({"ok": True, "id": item_id, "name": name})


@shopping_bp.route("/shopping/<item_id>/complete", methods=["POST"])
@require_token
def complete_shopping_item(item_id: str):
    with _lock:
        conn = _get_conn()
        try:
            cur = conn.execute(
                "UPDATE shopping_items SET completed = 1, completed_at = ? WHERE id = ?",
                (_now_ts(), item_id),
            )
            conn.commit()
        finally:
            conn.close()
    return jsonify({"ok": cur.rowcount > 0, "id": item_id})


@shopping_bp.route("/shopping/<item_id>/reopen", methods=["POST"])
@require_token
def reopen_shopping_item(item_id: str):
    with _lock:
        conn = _get_conn()
        try:
            cur = conn.execute(
                "UPDATE shopping_items SET completed = 0, completed_at = NULL WHERE id = ?",
                (item_id,),
            )
            conn.commit()
        finally:
            conn.close()
    return jsonify({"ok": cur.rowcount > 0, "id": item_id})


@shopping_bp.route("/shopping/<item_id>", methods=["DELETE"])
@require_token
def delete_shopping_item(item_id: str):
    with _lock:
        conn = _get_conn()
        try:
            cur = conn.execute("DELETE FROM shopping_items WHERE id = ?", (item_id,))
            conn.commit()
        finally:
            conn.close()
    return jsonify({"ok": cur.rowcount > 0, "id": item_id})


@shopping_bp.route("/reminders", methods=["GET"])
@require_token
def list_reminders():
    completed = str(request.args.get("completed", "0")).strip().lower()
    limit = _safe_int(request.args.get("limit", "100"), 100, minimum=1, maximum=500)
    include_events = str(request.args.get("include_events", "0")).strip().lower() in {"1", "true", "yes"}

    where_sql = ""
    if completed in {"0", "false", "open"}:
        where_sql = "WHERE completed = 0"
    elif completed in {"1", "true", "done"}:
        where_sql = "WHERE completed = 1"

    with _lock:
        conn = _get_conn()
        try:
            rows = conn.execute(
                "SELECT id, title, description, due_at, recurring, source, created_by, trigger_reason, "
                "origin_entity_id, created_at, completed, completed_at, snoozed_until "
                f"FROM reminders {where_sql} "
                "ORDER BY "
                "CASE WHEN due_at IS NULL THEN 1 ELSE 0 END, "
                "due_at ASC, created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            reminders = [_row_to_dict(row) for row in rows]

            now_ts = _now_ts()
            for reminder in reminders:
                reminder["status_reason"] = _reminder_status_reason(reminder, now_ts)

            if include_events and reminders:
                rid_map = {r["id"]: [] for r in reminders}
                events = conn.execute(
                    "SELECT reminder_id, event_type, detail, created_at "
                    "FROM reminder_events ORDER BY created_at DESC LIMIT 200"
                ).fetchall()
                for event in events:
                    rid = str(event["reminder_id"])
                    if rid not in rid_map or len(rid_map[rid]) >= 5:
                        continue
                    rid_map[rid].append(_row_to_dict(event))
                for reminder in reminders:
                    reminder["events"] = rid_map.get(reminder["id"], [])
        finally:
            conn.close()
    return jsonify({"ok": True, "count": len(reminders), "reminders": reminders})


@shopping_bp.route("/reminders", methods=["POST"])
@require_token
def add_reminder():
    body = request.get_json(silent=True) or {}
    title = str(body.get("title", "")).strip()
    if not title:
        return jsonify({"ok": False, "error": "title_required"}), 400

    reminder_id = str(body.get("id") or f"rem_{uuid.uuid4().hex[:10]}")
    due_at = _parse_due_timestamp(body)
    description = str(body.get("description", "")).strip()
    recurring = str(body.get("recurring", "")).strip()
    source = str(body.get("source", "dashboard") or "dashboard")
    created_by = str(body.get("created_by", "user") or "user")
    trigger_reason = str(body.get("trigger_reason", "")).strip()
    origin_entity_id = str(body.get("origin_entity_id", "")).strip()

    with _lock:
        conn = _get_conn()
        try:
            conn.execute(
                "INSERT INTO reminders (id, title, description, due_at, recurring, source, created_by, "
                "trigger_reason, origin_entity_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    reminder_id,
                    title,
                    description,
                    due_at,
                    recurring,
                    source,
                    created_by,
                    trigger_reason,
                    origin_entity_id,
                    _now_ts(),
                ),
            )
            _insert_reminder_event(conn, reminder_id, "created", trigger_reason or source)
            conn.commit()
        finally:
            conn.close()

    return jsonify({"ok": True, "id": reminder_id, "title": title, "due_at": due_at})


@shopping_bp.route("/reminders/<reminder_id>/complete", methods=["POST"])
@require_token
def complete_reminder(reminder_id: str):
    with _lock:
        conn = _get_conn()
        try:
            cur = conn.execute(
                "UPDATE reminders SET completed = 1, completed_at = ? WHERE id = ?",
                (_now_ts(), reminder_id),
            )
            if cur.rowcount > 0:
                _insert_reminder_event(conn, reminder_id, "completed", "completed via API")
            conn.commit()
        finally:
            conn.close()
    return jsonify({"ok": cur.rowcount > 0, "id": reminder_id})


@shopping_bp.route("/reminders/<reminder_id>/snooze", methods=["POST"])
@require_token
def snooze_reminder(reminder_id: str):
    body = request.get_json(silent=True) or {}
    minutes = _safe_int(body.get("minutes", 30), 30, minimum=1, maximum=24 * 60)
    snoozed_until = _now_ts() + minutes * 60
    with _lock:
        conn = _get_conn()
        try:
            cur = conn.execute(
                "UPDATE reminders SET snoozed_until = ? WHERE id = ? AND completed = 0",
                (snoozed_until, reminder_id),
            )
            if cur.rowcount > 0:
                _insert_reminder_event(conn, reminder_id, "snoozed", f"{minutes}m")
            conn.commit()
        finally:
            conn.close()
    return jsonify({"ok": cur.rowcount > 0, "id": reminder_id, "snoozed_until": snoozed_until})


@shopping_bp.route("/reminders/explain", methods=["GET"])
@require_token
def explain_reminders():
    """Explain why reminders exist and what triggered them."""
    limit = _safe_int(request.args.get("limit", "40"), 40, minimum=1, maximum=200)
    with _lock:
        conn = _get_conn()
        try:
            rows = conn.execute(
                "SELECT r.id, r.title, r.trigger_reason, r.origin_entity_id, r.source, r.created_by, r.created_at, "
                "e.event_type, e.detail, e.created_at AS event_created_at "
                "FROM reminders r "
                "LEFT JOIN reminder_events e ON e.reminder_id = r.id "
                "ORDER BY COALESCE(e.created_at, r.created_at) DESC LIMIT ?",
                (limit,),
            ).fetchall()
        finally:
            conn.close()

    items: list[dict[str, Any]] = []
    for row in rows:
        item = _row_to_dict(row)
        item["explanation"] = (
            f"{item.get('title')}: source={item.get('source')}, "
            f"reason={item.get('trigger_reason') or 'n/a'}, "
            f"event={item.get('event_type') or 'created'}"
        )
        items.append(item)
    return jsonify({"ok": True, "count": len(items), "items": items, "generated_at": _now_iso()})
