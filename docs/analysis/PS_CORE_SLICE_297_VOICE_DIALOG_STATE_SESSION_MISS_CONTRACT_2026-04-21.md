# PS_CORE_SLICE_297_VOICE_DIALOG_STATE_SESSION_MISS_CONTRACT

**Datum:** 2026-04-21  
**VM-02 Fortsetzung:** Voice/Memory continuity — explicit dialog state session miss  
**Vorherige Slices:** 293 (explicit persistence authority), 294 (explicit session miss confirm/clarify), 295 (session-user authority), 296 (no-active-dialog contract)

## Problem

`GET /api/v1/voice/dialog/state?session_id=<id>` hat bisher keinen expliziten Session-Miss-Vertrag gehabt. Bei Anfrage einer nicht-existierenden Session wurde der globale IDLE-State zurückgegeben statt ehrlich "Session nicht gefunden" zu melden.

**Vorher:**
- `GET /api/v1/voice/dialog/state?session_id=never-existed` → `200 OK` mit globalem IDLE-State

**Nach:**
- `GET /api/v1/voice/dialog/state?session_id=<id>` prüft explizit ob die angefragte Session existiert
- Bei nicht-existierender Session → **404 Not Found** mit `"session not found"`

## Änderung

### `addons/pilotsuite/app/copilot_core/api/v1/voice.py`

```python
@bp.route("/dialog/state", methods=["GET"])
def get_dialog_state():
    """Get current dialog state."""
    try:
        session_id = request.args.get("session_id")
        if session_id:
            machine = _get_dialog_machine()
            state = machine.get_state()
            if state.session_id != session_id:
                return jsonify({"status": "error", "message": "session not found", "session_id": session_id}), 404
        return jsonify(_get_dialog_flow().get_state().to_dict())
    except Exception as e:
        _LOGGER.exception("Failed to get dialog state")
        return jsonify({"status": "error", "message": str(e)}), 500
```

## Test-Ergebnisse

```
=== Dialog state with non-existent session ===
dialog-state-miss: 404 {'message': 'session not found', 'session_id': 'never-existed', 'status': 'error'}

=== Dialog state without session ===
dialog-state: 200 {'state': 'IDLE', ...}

=== Activate then state ===
activate: 200
state: 200 ACTIVE
```

## Contract-Grenzen

- **404 Not Found** wenn `session_id` Query-Parameter angegeben, aber nicht existiert
- **200 OK** wenn kein `session_id` Parameter (globaler State) oder wenn Session existiert
- Session-Existenz wird über `state.session_id == requested_session_id` geprüft

## VM-02 Kontinuität

Dieser Slice setzt die VM-02-Serie fort:
- Slice 293: explizite Persistenz-Autorität (keine stillen `"default"`-Fallbacks)
- Slice 294: explizite Session-Miss-Verträge für confirm/clarify/state (404/409 statt in-memory Fallback)
- Slice 295: Session-User-Autorität (409 bei Rebinding-Versuchen)
- Slice 296: No-Active-Dialog-Vertrag (409 bei Confirm/Clarify ohne aktiven Dialog)
- **Slice 297: Dialog-State-Session-Miss (404 bei expliziter nicht-existierender Session)**

Alle Slices bleiben auf der shipped add-on spine (`addons/pilotsuite/app/copilot_core/api/v1/voice.py`) mit fokussierten Contract-Guards.

## Nächster Schritt

Weiterer VM-02-Schritt: nächste kleinste Voice/Memory-Read-Surface oder Session-Memory-Edge-Case auf der shipped spine identifizieren.
