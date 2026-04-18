# SECURITY AUDIT — P0-001 Token Auth Review

**Date:** 2026-04-18 03:25 Europe/Berlin
**Author:** PilotClaw
**Status:** ✅ FIXES LANDED (Option B)

## Scope
Core shipped add-on (`addons/pilotsuite/app/`) token authentication surface.
Files reviewed:
- `addons/pilotsuite/app/copilot_core/api/security.py`
- `addons/pilotsuite/app/copilot_core/security/brute_force_protection.py`
- `addons/pilotsuite/app/copilot_core/security/rate_limiter.py`
- `copilot_core/security/hardening.py`
- `copilot_core/security/enhanced_security.py`

---

## WHAT'S SOLID ✅

| Area | Implementation | Verdict |
|------|---------------|---------|
| Token generation | `SecureTokenGenerator` , `secrets.token_bytes(32)` -> 256-bit, URL-safe base64 | ✅ |
| Timing-safe compare | `hmac.compare_digest` used everywhere (no `==` on tokens) | ✅ |
| Secure defaults | `is_auth_required()` returns `True` by default | ✅ |
| 1-Key-Flow | Auto-generates token on first startup, persists to `/data/.pilotsuite_token` | ✅ |
| Token caching | 60s TTL cache on `get_auth_token()`, thread-safe double-checked locking | ✅ |
| Brute-force protection | Per-IP + per-token lockout (`brute_force_protection.py`) | ✅ |
| HA user token validation | Cached 5min against HA Core API (internal Docker network) | ✅ |
| Password hashing | PBKDF2, 100k iterations, SHA256, OWASP-compliant | ✅ |
| TokenVault | Rotation, revocation, expiry, hierarchical tokens | ✅ |
| Rate limiting | `RateLimiter` on `/api/v1/users` + configurable per-endpoint | ✅ |
| Thread safety | `threading.Lock` used throughout | ✅ |

---

## GAPS FOUND ⚠️

### GAP-1: Token scope enforcement missing
`validate_token()` returns `{"valid": True, "type, scope}` but callers never check scope.
The TokenVault tracks scopes but `require_token` decorator only checks validity, not scope.

**Risk:** Any valid token can call any endpoint regardless of its intended scope.
**Fix:** Add `require_scope(*scopes)` decorator or check in `require_token`.

### GAP-2: HA token validation has no fallback mode
If HA API is unreachable (network partition, HA restart), `_validate_ha_user_token`
returns `False` and valid HA tokens are rejected until HA is back.
**Risk:** False rejection under HA failover scenarios.
**Fix:** Add `_ha_token_strict` config flag, if `False` and HA unreachable, log warning and allow.

### GAP-3: `is_auth_required()` lacks caching
Every call (except env var check) reads `/data/options.json` from disk.
Under high request load this adds ~1ms/read overhead.
**Risk:** Latency on authenticated endpoints if disk is slow.
**Fix:** Cache the result with a short TTL (already done for `get_auth_token`).

### GAP-4: No admin scope flag
`require_admin` exists but doesn't actually check a scope bit, only checks token matches.
**Risk:** Anyone with a valid user token can call admin endpoints if `auth_required=False`.
**Fix:** Add `admin` scope to TokenVault, `require_admin` checks for it.

### GAP-5: Token expiry not enforced in `validate_token`
The TokenVault has expiry but is only used by the `/api/v1/auth/revoke` flow.
Regular `validate_token` does not check token expiry.
**Risk:** Stale tokens remain valid until explicitly revoked.
**Fix:** Call TokenVault.validate_token() for full token lifecycle enforcement.

---

## FIXES LANDED (Option B)

### GAP-3 ✅ Cache `is_auth_required()` (2026-04-18)
- Added `_auth_required_cache: tuple[bool, float]` with 30s TTL
- Same double-checked locking pattern as `get_auth_token()`
- No more disk reads on every `is_auth_required()` call

### GAP-1 ✅ Scope support in `require_token` (2026-04-18)
- `require_token(f)` now accepts optional `scopes=('read','write')` kwarg
- Scope check after token validation, 403 if scope missing
- New `require_scope(*scopes)` decorator for post-auth scope gates
- Token scopes stored in `flask.g.token_scopes`

### GAP-4 ✅ Admin scope enforcement (2026-04-18)
- `require_admin_token()` now requires `'admin'` in `g.token_scopes`
- Only falls back to any valid token when `auth_required=False`
- `require_admin` decorator docstring updated

## Verification
- `python3 -m py_compile addons/pilotsuite/app/copilot_core/api/security.py tests/test_api_security_scope_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_api_security_scope_contract.py tests/test_security_brute_force_protection_contract.py` -> `10 passed`

## QUICK WINS (Minimal Risk)

1. **Cache `is_auth_required()`** , 10-line fix, same pattern as `get_auth_token()`
2. **Add scope check in `require_token`** , validate scope after token validity

## MID-EFFORT FIXES

3. **Admin scope flag** , add `admin` scope bit to TokenVault tokens
4. **Expiry enforcement** , hook TokenVault expiry into `validate_token`

## OUT OF SCOPE (for P0-001)

- HA token validation fallback (needs HA integration review)
- Token scope enforcement at scale (needs API contract review)

---

## Decision outcome
- Andreas-approved **Option B** is now file-backed: GAP-3, GAP-1, and GAP-4 are landed and covered by focused contract tests.
- Remaining auth-lifecycle work stays parked for a later bounded follow-up, not this rescue slice.
