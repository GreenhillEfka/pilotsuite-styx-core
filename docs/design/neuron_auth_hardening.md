# Neuron-Auth Hardening: UI States & Security Flows

**Status:** Finalized (2026-04-06)
**Owner:** DesignClaw
**Core-Worktree:** pilotsuite-styx-core-current

## 1. Overview
This document specifies the UI states and feedback loops for hardened neuron authentication and permission management in the Backend-UI.

## 2. UI Authentication States

| State | Backend-UI Display | Action / CTA |
| :--- | :--- | :--- |
| **Authorized** | Green Shield Icon | None |
| **Token Expired** | Orange Warning Banner: "Session Expired" | "Re-authenticate" (Opens Login Modal) |
| **Permission Denied** | Red Lock on specific Tab/Action | "Request Access" |
| **MFA Required** | Modal: "Confirm with 2nd Factor" | Input field for MFA code |

## 3. Feedback Loops (Success/Error)

### Success
- **Action:** Toggle Neuron State / Update Config.
- **Feedback:** Toast-Notification "Configuration Secured & Persisted".

### Error (Security Block)
- **Action:** Unauthorized access attempt.
- **Feedback:** Inline Error Message: "Insufficient Permissions. Security Audit Log triggered."

## 4. API-Contract (Slice 139)
Endpoints like `POST /api/v1/neurons/evaluate` or `PUT /api/v1/neurons/config` must return standard 401/403 errors with a JSON body for UI mapping:
```json
{
  "error": "permission_denied",
  "reason": "Missing scope: neuron.write",
  "resolution_url": "/api/v1/auth/request_scope"
}
```

## 5. Success Signal
Backend-UI prevents unauthorized actions at the interface level and provides clear paths to resolve authentication issues.
