## Groky Dev Check — Erweiterte Struktur

**Run every 10 min via:**
```bash
*/10 * * * * python3 /config/.openclaw/workspace/groky_dev_check.py
```

---

## 6 Phasen + NEUE Phase 7: System Integrity

### Phase 1: Repo Status
- Git fetch, git log (last 5 commits)
- Git status (untracked files, submodules)
- **Goal:** Detect diverged branches, new changes

### Phase 2: Bugfix Round (P0)
- Unit tests (`test_error_boundary.py`, `test_error_status.py`)
- Connection pool health (`/api/performance/pool`)
- Error history cleanup (7 days)
- **Goal:** Validate error isolation, pooling, stability

### Phase 3: Feature Extension (P1/P2)
- SearXNG health (`http://192.168.30.18:4041`)
- Plugin registry (`/api/plugins`)
- New plugins integration
- **Goal:** Validate features, plugins, search

### Phase 4: HA Conformance
- `manifest.json` integrity
- HACS `repository.json` validation
- Addon structure check
- **Goal:** HA-compliant releases

### Phase 5: Release + Notes
- Auto-increment version (vX.Y.Z)
- Update `CHANGELOG.md`, `RELEASE_NOTES.md`
- Git commit + tag + push
- **Goal:** Clean release to `main` (no dev branches)

### Phase 6: Status Report
- Telegram report to Mensch
- Commit log, release info, plugin status
- System health summary
- **Goal:** Immediate feedback to human

### Phase 7 (NEU!): System Integrity — Dashboard + UX Optimierung
- Dashboard endpoint (`/dashboard`)
- Frontend/Backend API routes validation
- Config YAML syntax check
- UX stress test (100 API requests, error rate < 1%)
- **Goal:** Validate dashboard, API, UX from scratch

---

## Ziel jedes Loops

**Jeder Loop soll:**
1. **Kernprobleme identifizieren** und Lösungen implementieren
2. **Dashboard + Frontend/Backend-Kommunikation** validieren
3. **Konfiguration und Benutzererfahrung** von Grund auf optimieren
4. **System stabilisieren** und HA-conform release-fähig machen

---

## Modell Chain

- Primary: `xai/grok-4`
- Fallback: `ollama/qwen3-coder-next:cloud`

---

## WICHTIG

- Jeder Loop = **SAUBERES RELEASE** (vX.Y.Z)
- **Niemals dev branches** — direkt nach `main`
- Bei KEINEM Input → HEARTBEAT_OK
- **Phase 7 (System Integrity) ist der neue Kern** — prüft Dashboard, API, UX
