# Coverage Gap Analysis

**Generated:** 2026-03-02  
**Target:** ≥90% coverage for all new modules  
**Current Overall Coverage:** 52.7%

---

## Target Module Coverage Status

| Module | Coverage | Status | Gap |
|--------|----------|--------|-----|
| `homeassistant/client.py` | 68.7% | △ Needs Work | -21.3% |
| `homeassistant/websocket_client.py` | N/A | ⚠️ Not Found | - |
| `homeassistant/entity_adoption.py` | 92.3% | ✓ Pass | +2.3% |
| `homeassistant/zone_matcher.py` | 99.0% | ✓ Pass | +9.0% |
| `dashboard/widgets/zone_summary.py` | N/A | ⚠️ Not Found | - |
| `api/v1/conversation.py` | 8.5% | ⚠️ Critical | -81.5% |
| `api/v1/rag.py` | 14.3% | ⚠️ Critical | -75.7% |
| `api/v1/zone_editor.py` | 26.4% | ⚠️ Critical | -63.6% |

---

## Critical Coverage Gaps (<50%)

### 1. `api/v1/conversation.py` - 8.5% Coverage

**Issue:** Large file (1054 statements) with minimal test coverage  
**Missing:**  
- Endpoint handler tests  
- Conversation flow logic  
- Error handling paths  
- Integration with LLM providers  

**Priority:** HIGH - Core API functionality  

**Recommendation:**  
- Create focused tests for main endpoints  
- Mock external dependencies (LLM providers)  
- Test error scenarios separately  

---

### 2. `api/v1/rag.py` - 14.3% Coverage

**Issue:** RAG (Retrieval-Augmented Generation) module lacks tests  
**Missing:**  
- Index endpoint tests  
- Search endpoint tests  
- Hybrid search logic  
- Vector store interactions  

**Priority:** HIGH - Core AI functionality  

**Recommendation:**  
- Mock vector database calls  
- Test search ranking logic  
- Verify document indexing flow  

---

### 3. `api/v1/zone_editor.py` - 26.4% Coverage

**Issue:** Zone management API partially tested  
**Missing:**  
- Create/update/delete zone tests  
- Room assignment logic  
- Zone validation edge cases  

**Priority:** MEDIUM - Administrative functionality  

**Recommendation:**  
- Add CRUD operation tests  
- Test zone-room relationships  
- Verify validation logic  

---

### 4. `homeassistant/client.py` - 68.7% Coverage

**Issue:** HTTP client needs more async integration tests  
**Missing:**  
- Full integration tests with real HA instance  
- SSL certificate validation tests  
- Complex retry scenario tests  

**Priority:** MEDIUM - Infrastructure component  

**Progress:** Improved from 26.7% → 68.7% (+42%) with new test file  

**Remaining Gaps:**  
- Lines 94-146: `test_connection()` full integration  
- Lines 163-173: Error handling in requests  
- Lines 208-221: POST request error scenarios  

---

## Modules Meeting Target (≥90%)

✅ `homeassistant/entity_adoption.py` - 92.3%  
✅ `homeassistant/zone_matcher.py` - 99.0%  

---

## Files Not Found in Coverage Report

The following target files were not found in the coverage report:
- `homeassistant/websocket_client.py` - May not exist or not imported
- `dashboard/widgets/zone_summary.py` - May be frontend-only (not Python)

**Action Required:** Verify these files exist and are part of the Python codebase.

---

## Test Files Created

### `tests/test_coverage_critical.py`

**Purpose:** Address critical coverage gaps in `homeassistant/client.py`  
**Tests:** 33 test cases  
**Coverage Impact:** +42% for `client.py`  

**Test Categories:**
1. **Configuration Tests** (6 tests)
   - Default and custom configurations
   - Connection status defaults
   
2. **Session Management Tests** (7 tests)
   - Session creation and reuse
   - Session lifecycle management
   
3. **Request Handling Tests** (6 tests)
   - GET/POST requests
   - Error handling (401, 404, 500)
   - Retry logic
   
4. **Entity Operations Tests** (6 tests)
   - Get areas, states, entities
   - Error handling
   
5. **Module Import Tests** (4 tests)
   - Verify API modules load correctly
   
6. **Integration Tests** (4 tests)
   - Async context manager
   - SSL configuration

---

## Recommendations

### Immediate Actions (This Sprint)

1. **Complete `client.py` coverage** (68.7% → 90%)
   - Add integration tests for `test_connection()` with mocked aiohttp
   - Test SSL certificate scenarios
   - Add tests for all error paths in request methods

2. **Address `api/v1/*.py` modules**
   - Start with `zone_editor.py` (26.4% - smallest file)
   - Create focused test files for each API module
   - Mock external dependencies heavily

3. **Investigate missing files**
   - Verify `websocket_client.py` exists
   - Check if `zone_summary.py` is frontend-only

### Medium-Term Actions

1. **Set up CI coverage enforcement**
   ```yaml
   # In CI configuration
   pytest --cov=copilot_core --cov-fail-under=90
   ```

2. **Add coverage badges to README**
   - Track progress over time
   - Set team expectations

3. **Create test templates**
   - Standard patterns for API endpoint tests
   - Common mocking utilities
   - Async test fixtures

---

## Coverage Commands

### Generate HTML Report
```bash
cd /config/.openclaw/workspace/pilotsuite-styx-core/copilot_core/rootfs/usr/src/app
pytest --cov=copilot_core --cov-report=html:htmlcov
```

### Run with Coverage Threshold
```bash
pytest --cov=copilot_core --cov-report=term-missing --cov-fail-under=90
```

### Check Specific Module
```bash
pytest tests/test_coverage_critical.py --cov=copilot_core.homeassistant.client --cov-report=term-missing
```

---

## Progress Summary

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| `client.py` Coverage | 26.7% | 68.7% | +42.0% |
| Test Files Created | 0 | 1 | +1 |
| Test Cases Added | 0 | 33 | +33 |
| Modules ≥90% | 2 | 2 | 0 |
| Overall Coverage | ~50% | 52.7% | +2.7% |

**Next Steps:** Continue adding tests for `client.py` remaining gaps and tackle `api/v1/*.py` modules.
