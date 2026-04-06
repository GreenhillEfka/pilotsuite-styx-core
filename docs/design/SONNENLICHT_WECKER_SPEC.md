# SONNENLICHT_WECKER_SPEC

**Status:** Slice-Update (2026-04-06)
**Bereich:** `copilot_core/modules/sonnenwecker`

## 1) Zielbild
Der Sonnenlicht-Wecker ist eine zonale Komfort-Logik (Lichtramp + optionaler Audio-Start), die den morgendlichen Ablauf pro Zone orchestriert.

Zusätzliche Anforderung dieses Tasks:
- Audio-Fade **In/Out** im Modul selbst (sanfter Anlauf beim Wecken, kontrollierter Auslauf bei Schlaf).
- Interaktion mit dem **Schlaf-Status**: beim Schlafen/Presence-Lost wird die Musikwolke der betroffenen Zone deaktiviert.
- Neue Konfiguration: `suppress_music_cloud_during_sleep: bool`.

---

## 2) Datenmodell (Zone-Config)
In `copilot_core/modules/sonnenwecker/engine.py` ergänzt:

```python
@dataclass
class SunlightAlarmConfig:
    ...
    music_on_wake: bool = False
    music_volume_start: float = 0.15
    suppress_music_cloud_during_sleep: bool = True
```

**Semantik:**
- `music_on_wake`: Aktiviert den Musik-Start bei Alarmabschluss.
- `music_volume_start`: Ziel-Lautstärke (0.0–1.0) für den **Fade-In-Endwert**.
- `suppress_music_cloud_during_sleep`: Wenn `True`, werden bei Schlafbeginn alle Musikwolke-Sessions dieser Zone beendet.

---

## 3) Audio-Fade-Mechanik (In/Out)
### 3.1 Fade-In bei Wake
Beim Abschluss einer Wecksequenz (`_trigger_music_wake`) startet der Module-Engine:
1. Eine Musikwolke-Session mit Lautstärke `0%`.
2. Eine Hintergrund-Fade-Routine auf `music_volume_start` (in `0…1` skaliert auf Prozent).
3. Konstanten für Fade-Verhalten:
   - `_MUSIC_FADE_STEPS = 10`
   - `_MUSIC_FADE_STEP_DELAY_S = 0.3`

### 3.2 Fade-Out bei Sleep
`on_sleep_detected(zone_id)` prüft die Zonenkonfiguration:
- Wenn `suppress_music_cloud_during_sleep=True`:
  - Alle Sessions der Zone werden identifiziert.
  - Für jede Session wird ein Fade-Out auf `0%` gefahren.
  - Danach wird automatisch `stop_session(session_id)` aufgerufen.

### 3.3 Fade-Implementierung
- Hintergrund-Threads pro Session (`sonnenwecker-music-fade-<session>`)
- Fortschritt: linear über Schritte
- Abbruchfähigkeit: neue Fade-Anforderung für dieselbe Session bricht die alte direkt ab.

---

## 4) Interaktions-Logik Schlaf-Status
- Eingang: `on_sleep_detected(zone_id)` (Presence/Event-Signal)
- Wirkung:
  1. Laufende Alarme der Zone werden gecancelt.
  2. Bei aktivierter Suppression (`suppress_music_cloud_during_sleep=True`) wird die Musikwolke dieser Zone abgeschaltet.
  3. Bestehende Sleep-Lock-Callbacks werden weiterhin getriggert.

### Trigger-Return
- Rückgabe enthält weiterhin `alarm_cancelled:<run_id>` sowie `music_stopped:<n>`.
- Ist keine Musikwolke aktiv, wird nur das Alarm-Cancel/Callback-Verhalten zurückgegeben.

---

## 5) API / Wiring
- `symbiosis/sota_media_alarm.py` propagiert die neue Option:
  - `configure_sonnenwecker(..., suppress_music_cloud_during_sleep=...)`

---

## 6) Akzeptanzkriterien
1. **Audio-Fade In**: bei Weckende wird Musikwolke nicht hart auf Zielvolumen gesetzt, sondern sanft angefahren.
2. **Audio-Fade Out + Stop**: beim Schlaf der Zone werden vorhandene Musikwolken der Zone auf 0% gefadet und gestoppt.
3. **Konfigurierbarkeit**: `suppress_music_cloud_during_sleep=False` verhindert die Deaktivierung der Musikwolke beim Schlaf.
4. **Kompatibilität**: bestehende `music_on_wake`- und Lichtlogik bleibt erhalten.
