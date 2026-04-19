# PS_CORE_CORE_CONTRACT_201A_PERSISTENCE_DOMAIN_MAPPING_2026-04-19

## Task
Map all persistence domains in PilotSuite Core — storage location, env var / config key, fallback default, access pattern, and contract test status.

---

## Domain Map

| # | Domain | Storage Location | Env Var | Fallback | Access | Contract Test |
|---|--------|----------------|---------|---------|--------|---------------|
| 1 | Shopping list | `/data/shopping_reminders.db` | `SHOPPING_DB_PATH` | `/data/shopping_reminders.db` | SQLite R/W | ✅ `test_state_persistence_shopping_health_contract.py` |
| 2 | Conversation memory | `/data/conversation_memory.db` | `CONVERSATION_MEMORY_DB` | `/data/conversation_memory.db` | SQLite R/W | ✅ `test_conversation_memory.py` |
| 3 | Vector/RAG store | `/data/vector_store.db` | `COPILOT_VECTOR_DB_PATH` | `/data/vector_store.db` | SQLite R/W | ❌ No contract test |
| 4 | Dialog state | `runtime_data_dir/dialog_state.json` | `runtime_data_dir` via `COPILOT_DATA_DIR` | `/data/dialog_state.json` | JSON file R/W | ✅ Addressed in CORE-STRUCT-102B |
| 5 | Voice command history | In-memory / session only | — | — | Ephemeral | ❌ No persistence contract |
| 6 | Energy forecast data | `/data/forecasts.db` | Implicit in `data_dir` | `data_dir/forecasts.db` | SQLite R/W | ❌ No contract test |
| 7 | Events/Audit log | `data_dir/events.jsonl` | `events_jsonl_path` | `data_dir/events.jsonl` | Append-only | ❌ No contract test |
| 8 | Brain graph | `data_dir/brain_graph.json` | `brain_graph_json_path` | `data_dir/brain_graph.json` | JSON file R/W | ❌ No contract test |
| 9 | Candidates | `data_dir/candidates.json` | `candidates_json_path` | `data_dir/candidates.json` | JSON file R/W | ❌ No contract test |
| 10 | User preferences | `data_dir/user_preferences.json` | Implicit | `data_dir/user_preferences.json` | JSON file R/W | ❌ No contract test |

---

## Details

### 1 — Shopping List
- **Path:** `os.environ.get("SHOPPING_DB_PATH", "/data/shopping_reminders.db")`
- **Module:** `copilot_core/app.py` → `shopping_db` key in services
- **Access:** SQLite read/write via `ShoppingReminders` module
- **Tests:** `test_state_persistence_shopping_health_contract.py` — verified green
- **Hardened:** ✅ CORE-STRUCT-103A aligned path to env override

### 2 — Conversation Memory
- **Path:** `os.environ.get("CONVERSATION_MEMORY_DB", "/data/conversation_memory.db")`
- **Module:** `copilot_core/conversation_memory.py`
- **Access:** SQLite read/write
- **Tests:** `test_conversation_memory.py` — runs against real file in CI
- **Hardened:** ❌ No env-back override wiring in health route yet

### 3 — Vector/RAG Store
- **Path:** `os.environ.get("COPILOT_VECTOR_DB_PATH", "/data/vector_store.db")`
- **Module:** `copilot_core/rag/` (bm25.py, vector store)
- **Access:** SQLite read/write
- **Tests:** ❌ No contract test
- **Hardened:** ❌ Path is env-configurable but not verified in health route

### 4 — Dialog State
- **Path:** `{runtime_data_dir}/dialog_state.json`
- **Module:** `copilot_core/voice/dialog_state.py` via `dialog_state_module.get_dialog_machine()`
- **Access:** JSON file read/write via state machine
- **Tests:** ✅ Covered in `test_voice_command_api.py`
- **Hardened:** ✅ CORE-STRUCT-102B — runtime_data_dir resolved from `COPILOT_DATA_DIR`

### 5 — Voice Command History
- **Storage:** In-memory / session-scoped only
- **Module:** `copilot_core/voice/command_router.py`
- **Access:** Ephemeral — not persisted
- **Tests:** N/A
- **Decision needed:** Should this be persisted? (deferred to CORE-CONTRACT-201-E)

### 6 — Energy Forecast Data
- **Path:** Implicit `data_dir/forecasts.db`
- **Module:** `copilot_core/prediction/forecaster.py`, `energy_optimizer.py`
- **Access:** SQLite read/write
- **Tests:** ❌ No contract test
- **Hardened:** ❌ No explicit env var for forecasts.db

### 7 — Events/Audit Log
- **Path:** `os.path.join(data_dir, "events.jsonl")` — env var `events_jsonl_path`
- **Module:** `copilot_core/events/`
- **Access:** Append-only JSONL
- **Tests:** ❌ No contract test
- **Hardened:** ❌ Path defined but not verified in deep health

### 8 — Brain Graph
- **Path:** `os.path.join(data_dir, "brain_graph.json")`
- **Module:** `copilot_core/brain_graph/`
- **Access:** JSON file read/write via NetworkX
- **Tests:** ❌ No contract test
- **Hardened:** ❌ Path defined but not verified in health

### 9 — Candidates
- **Path:** `os.path.join(data_dir, "candidates.json")`
- **Module:** `copilot_core/collective_intelligence/pattern_library.py`
- **Access:** JSON file read/write
- **Tests:** ❌ No contract test
- **Hardened:** ❌ Path defined but not verified in health

### 10 — User Preferences
- **Path:** `data_dir/user_preferences.json`
- **Module:** `copilot_core/user_prefiles.py`, `storage/user_preferences.py`
- **Access:** JSON file read/write
- **Tests:** ❌ No contract test
- **Hardened:** ❌ No explicit env var

---

## Classification

### Tier A — Explicit Contract ✅
- Shopping list (has env override + contract test + health route)
- Conversation memory (has contract test, env override not in health yet)
- Dialog state (CORE-STRUCT-102B addressed)

### Tier B — Env Override, No Contract Test ⚠️
- Vector/RAG store: env var exists, no health check, no contract test
- Brain graph: path in config, no health check, no contract test
- Energy forecasts: implicit path, no health check, no contract test

### Tier C — No Formal Contract ❌
- Events/Audit log: append-only, path configurable, no health check
- Candidates: file-based, no health check
- User preferences: file-based, no health check
- Voice command history: ephemeral by design

---

## Findings for CORE-CONTRACT-201-B/C/D

**CORE-CONTRACT-201-B (Shopping):** Tier A — minimal work: add health route check for shopping_db path existence / TTL

**CORE-CONTRACT-201-C (Conversation Memory):** Tier A — add CONVERSATION_MEMORY_DB to deep health route

**CORE-CONTRACT-201-D (Vector/RAG):** Tier B — add COPILOT_VECTOR_DB_PATH health check + contract test

---

## Next exact step
`CORE-CONTRACT-201-B / Shopping persistence seam formalization` — add env-back persistence path rule to the deep health surface with a bounded contract test.
