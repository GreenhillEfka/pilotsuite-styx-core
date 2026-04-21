# PS_CORE_SLICE_296_VOICE_DIALOG_NO_ACTIVE_DIALOG_CONTRACT

**Datum:** 2026-04-21  
**VM-02 Fortsetzung:** Voice/Memory continuity — explicit dialog authority  
**Vorherige Slices:** 293 (explicit persistence authority), 294 (explicit session miss contract), 295 (session-user authority contract)

## Problem

`/api/v1/voice/dialog/confirm` und `/api/v1/voice/dialog/clarify` haben bisher generische Fallback-Antworten geliefert, wenn kein aktiver Dialog existierte, statt ehrlich "kein aktiver Dialog" zu melden.

**Vorher:**
- `POST /api/v1/voice/dialog/confirm` ohne aktiven Dialog → `200 OK` mit generischer Antwort
- `POST /api/v1/voice/dialog/clarify` ohne aktiven Dialog → `200 OK` mit generischer "Kannst du das bitte genauer beschreiben?"-Frage

**Nach:**
- Beide Endpoints geben jetzt **409 Conflict** mit klarer Fehlermeldung: `"no active dialog to confirm"` bzw. `"no active dialog to clarify"`

## Änderung

### `addons/pilotsuite/app/copilot_core/voice/dialog_flow.py`

```python
def confirm_action(self, *, confirmed: bool) -> DialogConfirmResult:
    state = self._dialog_machine.get_state()
    if state.state == "IDLE":
        raise ValueError("no active dialog to confirm")
    state = self._dialog_machine.confirm_action() if confirmed else self._dialog_machine.cancel_action()
    return DialogConfirmResult(status="ok", **DialogSnapshot.from_state(state).to_dialog_mutation_state())

def clarify(self, *, clarification_text: str) -> DialogClarifyResult:
    state = self._dialog_machine.get_state()
    if state.state == "IDLE":
        raise ValueError("no active dialog to clarify")
    state = self._dialog_machine.set_clarifying(clarification_text)
    snapshot = DialogSnapshot.from_state(state)
    return DialogClarifyResult(
        status="ok",
        clarification_question=self._dialog_machine.generate_clarification_question(),
        **snapshot.to_dialog_mutation_state(),
    )
```

### `addons/pilotsuite/app/copilot_core/api/v1/voice.py`

HTTP-Adapter fängt `ValueError` mit "no active dialog" und wandelt es in **409 Conflict** um:

```python
@bp.route("/dialog/confirm", methods=["POST"])
def confirm_dialog_action():
    try:
        data = request.get_json(silent=True) or {}
        return jsonify(
            _get_dialog_flow().confirm_action(
                confirmed=bool(data.get("confirmed", False)),
            ).to_dict()
        )
    except ValueError as e:
        if "no active dialog" in str(e):
            return jsonify({"status": "error", "message": str(e)}), 409
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        _LOGGER.exception("Failed to confirm dialog action")
        return jsonify({"status": "error", "message": str(e)}), 500
```

Analog für `/dialog/clarify`.

## Test-Ergebnisse

```
confirm-miss (ohne aktiven Dialog): 409 {'message': 'no active dialog to confirm', 'status': 'error'}
clarify-miss (ohne aktiven Dialog): 409 {'message': 'no active dialog to clarify', 'status': 'error'}

activate (mit Intent): 200 {'state': 'ACTIVE', 'active_intent': 'light.turn_on', ...}
confirm-hit (mit aktivem Dialog): 200 {'state': 'IDLE', ...}  # nach Ausführung
```

## Contract-Grenzen

- **409 Conflict** wird zurückgegeben, wenn kein aktiver Dialog existiert (State == IDLE)
- **200 OK** nur wenn Dialog-Transition erfolgreich war
- **400 Bad Request** für andere `ValueError`-Fälle (z.B. fehlende Parameter)
- **500 Internal Error** für unerwartete Exceptions

## VM-02 Kontinuität

Dieser Slice setzt die VM-02-Serie fort:
- Slice 293: explizite Persistenz-Autorität (keine stillen `"default"`-Fallbacks)
- Slice 294: explizite Session-Miss-Verträge (404 statt in-memory Fallback)
- Slice 295: Session-User-Autorität (409 bei Rebinding-Versuchen)
- **Slice 296: No-Active-Dialog-Vertrag (409 bei Confirm/Clarify ohne aktiven Dialog)**

Alle Slices bleiben auf der shipped add-on spine (`addons/pilotsuite/app/copilot_core/api/v1/voice.py` und `dialog_flow.py`) mit fokussierten Contract-Guards.

## Nächster Schritt

Weiterer VM-02-Schritt: nächste kleinste Voice/Memory-Read-Surface oder Session-Memory-Edge-Case auf der shipped spine identifizieren.
