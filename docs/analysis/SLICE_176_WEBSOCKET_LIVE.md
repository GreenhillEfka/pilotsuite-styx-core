# Slice 176: WebSocket Live Updates

**Status:** Analyzed (2026-04-05)
**Basis:** websocket_server.py (Slice 132)

## Current State
WebSocket exists, but widget-specific live updates not implemented.

## Expansion Needed
1. **Widget Subscription** — Subscribe to widget-specific events
2. **Entity Push** — Push entity state changes to clients
3. **Floorplan Sync** — Real-time floorplan entity updates
4. **Area Tree Sync** — Live area/device count updates

## Decision
Extend WebSocket with widget-specific channels.

