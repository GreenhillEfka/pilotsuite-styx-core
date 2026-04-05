# Slice 163: Templates API Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** templates.py (10KB)

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/templates | ✅ List templates |
| POST /api/v1/templates | ✅ Create template |

## Expansion Needed

1. **Template Categories** — Organize templates by category
2. **Template Variables** — Variable substitution in templates
3. **Template Preview** — Preview template rendering
4. **Template Sharing** — Share/export templates

## Decision

**Action:** Add categories + variables + preview endpoints

**Priority:**
1. Template categories
2. Template variables
3. Template preview
4. Template sharing

