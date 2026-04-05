# Slice 160: Media API Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** media.py (13KB)

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/media | ✅ List media |
| POST /api/v1/media | ✅ Upload media |

## Expansion Needed

1. **Media Transcoding** — Format conversion on upload
2. **Media Thumbnails** — Auto-generated thumbnails
3. **Media Albums** — Group media into albums
4. **Media Sharing** — Share links with expiration

## Decision

**Action:** Add transcoding + thumbnails + albums endpoints

**Priority:**
1. Media transcoding
2. Media thumbnails
3. Media albums
4. Media sharing

