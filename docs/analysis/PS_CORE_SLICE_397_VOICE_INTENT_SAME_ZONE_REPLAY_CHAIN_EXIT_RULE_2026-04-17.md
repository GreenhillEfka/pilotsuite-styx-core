# PS Core Slice 397 — Voice intent same-zone replay chain EXIT CRITERIA

## Stop Rule: Same-Zone Replay Chain Closure

**Definition:** The alias-equivalent same-zone replay chain is CLOSED when ALL of the following are file-backed:
- `context.timestamp` ✅ (Slice 392)
- `context.context_version` ✅ (Slice 392)
- `context.mood` ✅ (Slice 393, mood is built fresh from mood_engine — no replay gap)
- `context.time` ✅ (Slice 394)
- `context.language_preference` ✅ (Slice 395)
- `context.user_preferences` ✅ (Slice 396 — just landed)

**Why this is the stop:** All read-only scalar metadata and accepted scalar/context fields on the same-zone double-authority path are now file-backed. The replay chain has a natural boundary here — further fields (relevant_patterns, sensor_data) have structural reasons they aren't simply replayed (they're built from live services), not validation gaps.

**Known separate issue:** `active_devices` replay has a genuine architectural bug (build_context does not accept it + to_dict() type mismatch on DeviceContext). Filed as separate concern, not part of this chain.

## Next Seam After Replay Chain: `/api/v1/voice/context` (GET)

**Why this is the next seam:**
- All bounded `/api/v1/voice/intent` POST context surface is now replay-proven
- The adjacent read-side seam is `/api/v1/voice/context` (GET) — serves the same context data to callers
- It may have different validation/behavior than the POST
- Next bounded slice: audit `GET /api/v1/voice/context` for parity with POST replay surface

## Verification
- All 6 replay fields proven on `POST /api/v1/voice/intent` with double zone-name alias-equivalent shape
- `active_devices` is a known separate bug, not a replay gap
- No further micro-rescans needed on the POST intent replay surface
