# PilotSuite VISION — Das Dachsystem

**Version:** 15.3.0  
**Date:** 2026-04-01  
**Status:** ✅ LEBENDIGE DOKUMENTATION

---

## 🎯 DIE VISION

### Ein Life-Long-Learning Dachsystem

```
┌─────────────────────────────────────────────────────────────────────┐
│                     PILOTSUITE — DAS DACHSYSTEM                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  "Ein SmartHome, das CLEVERER ist als sein Nutzer"                  │
│                                                                      │
│  Nicht nur reagiert — sondern VORAUSDENKT.                          │
│  Nicht nur speichert — sondern VERSTEHT.                            │
│  Nicht nur automatisiert — sondern LERNT.                           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ ARCHITEKTUR-PRINZIPIEN

### 1. MODULAR — Jede Komponente lernt

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Zonen      │    │   Neuronen   │    │   Module     │
│   lernt      │    │   lernt      │    │   lernt      │
│   Nutzung    │    │   Kontext    │    │   Patterns   │
└──────────────┘    └──────────────┘    └──────────────┘
       ↓                   ↓                   ↓
┌──────────────────────────────────────────────────────────────┐
│              ZENTRALES HABITUS-STORAGE                        │
│         (übergreifendes Pattern-Lernen)                       │
└──────────────────────────────────────────────────────────────┘
```

### 2. NUTZER-KENNTNIS — Über ALLE Schnittstellen

```
┌─────────────────────────────────────────────────────────────┐
│                    NUTZER-PROFIL                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Präferenzen (Licht, Temperatur, Musik)                     │
│  Routinen (Aufstehen, Arbeiten, Schlafen)                   │
│  Gewohnheiten (Wochentags, Wochenends)                      │
│  Stimmung (Komfort, Energie, Fokus)                         │
│  Feedback (Akzeptiert, Abgelehnt, Ignoriert)                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 3. HABITUS — ZENTRAL gespeichert

```python
Habitus = {
    "patterns": [
        {
            "id": "pattern_001",
            "description": "Licht an wenn Präsenz + Abend",
            "confidence": 0.95,
            "acceptances": 45,
            "rejections": 2,
            "last_triggered": "2026-04-01T19:30:00Z",
            "zones": ["living", "kitchen"],
            "modules": ["light", "presence"],
        }
    ],
    "user_model": {
        "preferences": {...},
        "routines": {...},
        "feedback_history": [...],
    },
}
```

### 4. PROAKTIV — System kommt ZUVOR

```
Reaktiv:     Event → Reaktion
             (Bewegung → Licht an)

Proaktiv:    Pattern → Vorhersage → Aktion
             (19:30 + Nutzer kommt heim → Licht an, Musik an)
```

### 5. ZUGÄNGLICH — Chat/API für EXTERNE

```
┌─────────────────────────────────────────────────────────────┐
│                    CHAT / API GATEWAY                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Telegram ←→ PilotSuite Chat ←→ Externe Dienste            │
│  WhatsApp ←→ PilotSuite API  ←→ Home Assistant             │
│  Web      ←→ PilotSuite GraphQL ←→ Drittanbieter           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 LEBENSZYKLUS — Wie das System lernt

### Phase 1: BEOBACHTEN (Learning Mode)

```
Nutzer schaltet Licht ein → System beobachtet
Nutzer ändert Temperatur → System beobachtet
Nutzer startet Musik → System beobachtet

Speichert:
- Zeitpunkt
- Kontext (Präsenz, Wetter, Tageszeit)
- Zone
- Modul
```

### Phase 2: MUSTER ERKENNEN (Pattern Mining)

```
System erkennt:
"Immer um 19:30, wenn Nutzer nach Hause kommt,
 wird Licht im Wohnzimmer eingeschaltet."

Pattern:
IF time ≈ 19:30 AND presence_detected AND zone=living
THEN light_on

Confidence: 0.85 (nach 10 Wiederholungen)
```

### Phase 3: VORSCHLAG (Suggestion)

```
System schlägt vor:
"Soll ich automatisch das Licht um 19:30 einschalten,
 wenn du nach Hause kommst?"

Nutzer: ✅ Akzeptieren | ❌ Ablehnen | ⏭️ Später
```

### Phase 4: AUTOMATISIEREN (Active Mode)

```
Nach Akzeptanz:
System führt AUTOMATISCH aus:
- 19:30 + Ankunft → Licht an

System lernt weiter:
- War Aktion hilfreich? (Feedback)
- Wurde sie überschrieben? (Korrektur)
- Wurde sie ignoriert? (Relevanz-Check)
```

### Phase 5: ADAPTIEREN (Life-Long Learning)

```
System passt sich an:
- Nutzer ändert Routine → Pattern update
- Jahreszeit ändert sich → Kontext update
- Neues Gerät → Entity mapping

System wird CLEVERER mit jeder Interaktion.
```

---

## 🔗 SCHNITTSTELLEN — Breiter Zugang

### Interne APIs

| API | Endpoint | Beschreibung |
|-----|----------|--------------|
| **Habitus API** | `/api/v1/habitus` | Pattern, Feedback, User-Model |
| **Neurons API** | `/api/v1/neurons` | Kontext, Zustand, Stimmung |
| **Chat API** | `/api/v1/chat` | LLM Chat, Voice, Character |
| **Zones API** | `/api/v1/hub/zones` | Zonen, Module, Entities |
| **Modules API** | `/api/v1/backend/modules` | Module-Konfiguration |

### Externe APIs

| Dienst | Integration | Beschreibung |
|--------|-------------|--------------|
| **Telegram** | ✅ Aktiv | Chat-Bot, Notifications |
| **WhatsApp** | ⏳ Bereit | Chat-Bot, Notifications |
| **Home Assistant** | ✅ Aktiv | Native Integration |
| **REST API** | ✅ Aktiv | Externe Dienste |
| **GraphQL** | ⏳ Geplant | Flexible Queries |
| **WebSocket** | ⏳ Geplant | Real-time Events |

---

## 🎯 ZIEL — SmartHome ist CLEVERER

### Heute (Stand der Technik)

```
Nutzer muss:
- Automatisierungen programmieren
- Regeln manuell erstellen
- Schwellwerte setzen
- Bei Änderungen anpassen

SmartHome ist WERKZEUG — nicht Partner.
```

### Mit PilotSuite (Vision)

```
System lernt:
- Beobachtet Nutzung
- Erkennt Muster
- Schlägt vor
- Passt sich an

SmartHome ist PARTNER — denkt mit.
```

### Konkrete Beispiele

| Situation | Heute | Mit PilotSuite |
|-----------|-------|----------------|
| **Nach Hause kommen** | Nutzer schaltet Licht | System schaltet VORHER |
| **Filmabend** | Nutzer stellt Szenen ein | System erkennt Intent |
| **Urlaub** | Nutzer schaltet alles aus | System erkennt Abwesenheit |
| **Gäste** | Nutzer erklärt alles | System lernt von Gästen |
| **Jahreszeit** | Nutzer passt an | System adaptiert automatisch |

---

## 📈 METRIKEN — Wie messen wir Erfolg?

### Learning Rate

```
- Patterns pro Woche
- Akzeptanz-Rate (%)
- Korrektur-Rate (%)
- Adaptions-Geschwindigkeit
```

### Nutzer-Kenntnis

```
- Bekannte Präferenzen
- Erkannte Routinen
- Vorhergesagte Aktionen (%)
- Proaktive Aktionen (%)
```

### System-Intelligenz

```
- Kontext-Verständnis
- Cross-Module Synergien
- Langzeit-Gedächtnis (RAG)
- Externes Wissen (SearXNG)
```

---

## 🔮 ZUKUNFT — Was kommt nach v15.3.0?

### v16.0.0 — Cross-Module Learning

- Module lernen ÜBERGREIFEND
- Synergien zwischen Licht, Klima, Musik
- Ganzheitliche Patterns

### v17.0.0 — Externe Integration

- Chat-API für Drittanbieter
- GraphQL für flexible Queries
- Webhooks für Event-Streaming

### v18.0.0 — Kollektive Intelligenz

- Multi-Home Learning (anonymisiert)
- Patterns von anderen Nutzern
- Best-Practices teilen

---

## ✅ UMSETZUNGS-STATUS (v15.3.0)

| Vision-Element | Status | Implementiert |
|----------------|--------|---------------|
| **Modular** | ✅ | Jede Komponente lernt |
| **Nutzer-Kenntnis** | ⏳ | HouseholdProfile (teilweise) |
| **Habitus-Storage** | ⏳ | ZoneMining (dezentral) |
| **Proaktiv** | ✅ | Candidates + Proposals |
| **Zugänglich** | ⏳ | Chat (intern), API (teilweise) |
| **Ende-zu-Ende** | ❌ | NICHT verbunden |
| **Learning-Vis** | ❌ | FEHLT |

---

**✅ VISION DOKUMENTIERT — JETZT UMSETZEN.**
