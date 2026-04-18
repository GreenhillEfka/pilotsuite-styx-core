# PilotSuite Core — Security Policy

**Version:** 1.0  
**Date:** 2026-04-18  
**Status:** Active  

---

## 1. Token Lifecycle

### 1.1 Auto-Token (1-Key-Flow)
PilotSuite generates a random 256-bit token on first startup if none is configured.

| Property | Value |
|----------|-------|
| Generation | `secrets.token_urlsafe(32)` |
| Storage | `/data/.pilotsuite_token` |
| Format | `{token}\n{created_at_unix}` |
| Lifetime | 90 days hard limit, 70 days warning |
| Rotation | Manual: set new `auth_token` in options.json |

### 1.2 Token Sources (Priority Order)
1. `COPILOT_AUTH_TOKEN` env var
2. `auth_token` in `/data/options.json`
3. Auto-generated token (1-Key-Flow)

### 1.3 Token Age Enforcement (GAP-5)
- Token age checked on every validation when file exists and has `created_at_unix`
- Age check bypassed for env/options.json tokens (no age metadata)
- `COPILOT_TOKEN_MAX_AGE_DAYS` env var overrides 90-day limit
- `COPILOT_TOKEN_WARN_AGE_DAYS` env var overrides 70-day warning

---

## 2. Authentication Surface

### 2.1 Endpoints
| Endpoint | Auth Required | Scope |
|----------|--------------|-------|
| `GET /health` | No | — |
| `GET /ready` | No | — |
| `GET /api/v1/status` | Yes | read |
| `GET /api/v1/capabilities` | Yes | read |
| `GET /version` | No | — |
| `POST /api/v1/...` | Yes | read+write |
| `POST /api/v1/automations/...` | Yes | read+write |
| `POST /api/v1/notifications/send` | Yes | admin |
| `POST /api/v1/brain/...` | Yes | admin |
| `WS /ws` | Token query param | — |

### 2.2 Authentication Methods
1. `X-Auth-Token` header (exact match, HMAC timing-safe)
2. `Authorization: Bearer <token>` (exact match, HMAC timing-safe)
3. `X-Ingress-Path` header (HA Ingress proxy — treated as authenticated)
4. HA user long-lived tokens (validated against HA Core API, cached 5 min)

### 2.3 Scope Model
Tokens carry scopes set by the caller. Standard scopes:
- `read` — GET endpoints
- `write` — POST/PUT endpoints
- `admin` — Sensitive operations (notifications, brain graph writes)

Scope check is additive: token needs ANY one of the declared scopes.

---

## 3. Brute Force Protection

### 3.1 IP-Based
- Max 10 failed attempts per IP per 15-minute window
- After max: reject for window duration (no auth attempt logged)
- Reset on successful auth

### 3.2 Token-Based
- Max 5 failed attempts per token per 15-minute window
- After max: 15-minute lockout
- Reset on successful auth

---

## 4. Caching (GAP-3)

| Function | Cache TTL | Rationale |
|----------|-----------|-----------|
| `is_auth_required()` | 30s | Avoid per-request disk I/O |
| `get_auth_token()` | 60s | Avoid per-request disk I/O |
| HA user token validation | 5 min | Avoid per-request HA API calls |

---

## 5. Security Defaults

| Setting | Default | Rationale |
|---------|---------|-----------|
| Auth required | `True` | Secure-by-default |
| Auto-token | Enabled | 1-Key-Flow for first-run convenience |
| Token min length | 32 bytes | Sufficient entropy |
| Brute force window | 15 min | Balance UX vs security |
| HA token min length | 20 chars | Filter obviously invalid tokens |

---

## 6. Test Coverage

| Test Class | Coverage |
|-----------|----------|
| `TestRequireTokenScopes` | GAP-1: `require_token(scopes=...)` |
| `TestRequireScope` | GAP-1: `require_scope()` |
| `TestRequireAdminToken` | GAP-4: admin scope enforcement |
| `TestTokenAgeEnforcement` | GAP-5: `_get_token_age()` |
| `TestAuthRequiredCaching` | GAP-3: TTL cache behavior |
| `TestBruteForceIPProtection` | Brute force: IP-based |
| `TestBruteForceTokenProtection` | Brute force: token-based |

---

## 7. Configuration Reference

```bash
# Disable auth entirely (NOT recommended for production)
COPILOT_AUTH_REQUIRED=false

# Set fixed auth token (overrides auto-token)
COPILOT_AUTH_TOKEN=your-secret-token

# Token age limits (days)
COPILOT_TOKEN_MAX_AGE_DAYS=90
COPILOT_TOKEN_WARN_AGE_DAYS=70
```