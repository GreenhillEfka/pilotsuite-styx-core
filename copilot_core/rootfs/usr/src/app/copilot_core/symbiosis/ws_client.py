"""Symbiotic WebSocket Client — Phase 4.
Real-time event streaming from HA to Core Rule Engine.
"""
import asyncio
import json
import logging
import websockets
from typing import Optional

_LOGGER = logging.getLogger(__name__)

class SymbioticWSClient:
    def __init__(self, ha_url: str, ha_token: str, event_bus_sync):
        self.ha_url = ha_url.replace("http", "ws") + "/api/websocket"
        self.ha_token = ha_token
        self.event_bus = event_bus_sync
        self._running = False

    async def start(self):
        self._running = True
        while self._running:
            try:
                async with websockets.connect(self.ha_url) as ws:
                    # Auth
                    await ws.send(json.dumps({"type": "auth", "access_token": self.ha_token}))
                    auth_resp = json.loads(await ws.recv())
                    if auth_resp.get("type") != "auth_ok":
                        _LOGGER.error("WS Auth failed")
                        return

                    # Subscribe to all events
                    await ws.send(json.dumps({
                        "id": 1,
                        "type": "subscribe_events",
                        "event_type": "state_changed"
                    }))

                    _LOGGER.info("Symbiotic WebSocket connected and subscribed")
                    
                    async for msg in ws:
                        data = json.loads(msg)
                        if data.get("type") == "event":
                            event = data["event"]
                            await self.event_bus.process_event(
                                event_type="state_changed",
                                payload=event["data"]
                            )
            except Exception as e:
                _LOGGER.error(f"WS Connection error: {e}, retrying...")
                await asyncio.sleep(5)
