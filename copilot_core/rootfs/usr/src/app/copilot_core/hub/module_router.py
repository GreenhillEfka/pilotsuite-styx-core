"""Module Router — Routet HA Entity States an Netzwerk-Module (v1.0.0).

Zentraler Router der HA-States an ZWave, Zigbee, Thread und
HomeAssistant-Module weiterleitet. Verwaltet Modul-Konfiguration
und periodische Aktualisierung.

Datenfluss:
    HomeAssistantClient.get_states() -> ModuleRouter.refresh() -> engine.update_from_ha()
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG: dict[str, dict[str, Any]] = {
    "zwave": {
        "enabled": True,
        "polling_interval_s": 120,
        "alert_dead_devices": True,
        "alert_threshold_dead": 1,
    },
    "zigbee": {
        "enabled": True,
        "polling_interval_s": 120,
        "alert_low_lqi": True,
        "lqi_threshold": 50,
    },
    "thread": {
        "enabled": True,
        "polling_interval_s": 120,
    },
    "homeassistant": {
        "enabled": True,
        "forwarded_domains": [
            "light", "sensor", "binary_sensor", "switch",
            "climate", "media_player", "cover", "fan",
        ],
        "webhook_retry_count": 3,
        "connection_timeout_s": 10,
    },
}

_CONFIG_PATH = Path("/data/network_modules_config.json")


class ModuleRouter:
    """Routet HA Entity States an Netzwerk-Module und verwaltet Config."""

    def __init__(
        self,
        *,
        hub_zwave: Any | None = None,
        hub_zigbee: Any | None = None,
        hub_thread: Any | None = None,
        ha_module_engine: Any | None = None,
        ha_client: Any | None = None,
        config_path: Path | str | None = None,
    ) -> None:
        self._zwave = hub_zwave
        self._zigbee = hub_zigbee
        self._thread = hub_thread
        self._ha = ha_module_engine
        self._ha_client = ha_client
        self._config_path = Path(config_path) if config_path else _CONFIG_PATH
        self._config: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._last_refresh: float = 0.0
        self._refresh_count: int = 0
        self._accumulated_states: dict[str, dict[str, Any]] = {}

        self._load_config()
        self._apply_config()

    # -- Config Persistence ---------------------------------------------------

    def _load_config(self) -> None:
        """Laedt Konfiguration aus JSON-Datei oder erstellt Defaults."""
        try:
            if self._config_path.exists():
                raw = self._config_path.read_text(encoding="utf-8")
                loaded = json.loads(raw)
                # Merge mit Defaults (neue Keys werden hinzugefuegt)
                for key, defaults in _DEFAULT_CONFIG.items():
                    if key in loaded:
                        merged = dict(defaults)
                        merged.update(loaded[key])
                        self._config[key] = merged
                    else:
                        self._config[key] = dict(defaults)
                logger.info("ModuleRouter: Config geladen von %s", self._config_path)
            else:
                self._config = {k: dict(v) for k, v in _DEFAULT_CONFIG.items()}
                self._save_config()
                logger.info("ModuleRouter: Default-Config erstellt")
        except Exception:
            logger.warning("ModuleRouter: Config-Ladefehler, verwende Defaults", exc_info=True)
            self._config = {k: dict(v) for k, v in _DEFAULT_CONFIG.items()}

    def _save_config(self) -> None:
        """Speichert Konfiguration in JSON-Datei."""
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            self._config_path.write_text(
                json.dumps(self._config, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            logger.warning("ModuleRouter: Config-Speicherfehler", exc_info=True)

    def _apply_config(self) -> None:
        """Wendet Config auf Module an."""
        ha_cfg = self._config.get("homeassistant", {})
        if self._ha and ha_cfg.get("forwarded_domains"):
            try:
                self._ha.configure_forwarded_domains(ha_cfg["forwarded_domains"])
            except Exception:
                logger.debug("ModuleRouter: HA-Domain-Config fehlgeschlagen", exc_info=True)

    def get_config(self, module: str | None = None) -> dict[str, Any]:
        """Gibt Konfiguration zurueck (einzelnes Modul oder alle)."""
        if module:
            return dict(self._config.get(module, {}))
        return {k: dict(v) for k, v in self._config.items()}

    def update_config(self, module: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Aktualisiert Konfiguration eines Moduls."""
        if module not in self._config:
            self._config[module] = {}
        self._config[module].update(updates)
        self._save_config()
        self._apply_config()
        return dict(self._config[module])

    # -- Event Accumulation (inkrementelles Update via Event Ingest) ----------

    _FLUSH_THRESHOLD = 50  # Nach N akkumulierten Events Flush ausfuehren

    def ingest_event(self, event: dict[str, Any]) -> None:
        """Akkumuliert ein einzelnes HA-Event fuer spaeteres Routing.

        Wird vom EventProcessor-Callback aufgerufen. Akkumuliert
        state_changed Events und flusht nach _FLUSH_THRESHOLD Events.

        Args:
            event: Einzelnes Event-Dict aus dem Event Ingest
                   (Format: {"entity_id": "...", "domain": "...",
                             "new": {"state": "on", "attributes": {...}}, ...})
        """
        kind = event.get("type", event.get("kind", ""))
        if kind != "state_changed":
            return

        entity_id = event.get("entity_id", "")
        new_state = event.get("new", event.get("data", {}).get("new_state", {}))
        if not entity_id or not new_state:
            return

        # Nur netzwerkrelevante Entities akkumulieren
        eid_lower = entity_id.lower()
        is_network = (
            eid_lower.startswith("zwave_js.") or
            eid_lower.startswith("zha.") or
            eid_lower.startswith("thread.") or
            (eid_lower.startswith("sensor.") and any(
                proto in eid_lower for proto in ("zwave", "zigbee", "thread")
            ))
        )
        if not is_network:
            return

        with self._lock:
            # State-Objekt im erwarteten Format aufbauen
            state_obj = {
                "state": new_state.get("state", "unknown"),
                "attributes": new_state.get("attributes", {}),
            }
            self._accumulated_states[entity_id] = state_obj

            if len(self._accumulated_states) >= self._FLUSH_THRESHOLD:
                self._flush_accumulated()

    def ingest_events_batch(self, events: list[dict[str, Any]]) -> None:
        """Verarbeitet einen Batch von Events und flusht am Ende."""
        for event in events:
            kind = event.get("type", event.get("kind", ""))
            if kind != "state_changed":
                continue

            entity_id = event.get("entity_id", "")
            new_state = event.get("new", event.get("data", {}).get("new_state", {}))
            if not entity_id or not new_state:
                continue

            eid_lower = entity_id.lower()
            is_network = (
                eid_lower.startswith("zwave_js.") or
                eid_lower.startswith("zha.") or
                eid_lower.startswith("thread.") or
                (eid_lower.startswith("sensor.") and any(
                    proto in eid_lower for proto in ("zwave", "zigbee", "thread")
                ))
            )
            if not is_network:
                continue

            state_obj = {
                "state": new_state.get("state", "unknown"),
                "attributes": new_state.get("attributes", {}),
            }
            self._accumulated_states[entity_id] = state_obj

        # Flush am Ende des Batches wenn Daten vorhanden
        if self._accumulated_states:
            with self._lock:
                self._flush_accumulated()

    def _flush_accumulated(self) -> None:
        """Flusht akkumulierte States an die Netzwerk-Module (lock muss gehalten werden)."""
        if not self._accumulated_states:
            return

        states = dict(self._accumulated_states)
        # Nicht clearen — akkumulierte States bleiben fuer naechsten Flush
        # bestehen und werden bei neuen Events ueberschrieben
        count = len(states)

        for name, engine, cfg_key in [
            ("zwave", self._zwave, "zwave"),
            ("zigbee", self._zigbee, "zigbee"),
            ("thread", self._thread, "thread"),
        ]:
            if engine is None:
                continue
            cfg = self._config.get(cfg_key, {})
            if not cfg.get("enabled", True):
                continue
            try:
                engine.update_from_ha(states)
            except Exception:
                logger.debug("ModuleRouter: %s flush fehlgeschlagen", name, exc_info=True)

        logger.debug("ModuleRouter: Flush %d akkumulierte States", count)

    # -- State Routing (Bulk) -------------------------------------------------

    def route_states(self, states_dict: dict[str, dict[str, Any]]) -> dict[str, int]:
        """Routet HA States an alle aktivierten Netzwerk-Module.

        Args:
            states_dict: Dict mit entity_id -> state-Objekt
                         (Format: {"state": "on", "attributes": {...}, ...})

        Returns:
            Dict mit Modul-Name -> Anzahl verarbeiteter Entities
        """
        result: dict[str, int] = {}
        with self._lock:
            for name, engine, cfg_key in [
                ("zwave", self._zwave, "zwave"),
                ("zigbee", self._zigbee, "zigbee"),
                ("thread", self._thread, "thread"),
            ]:
                if engine is None:
                    continue
                cfg = self._config.get(cfg_key, {})
                if not cfg.get("enabled", True):
                    continue
                try:
                    engine.update_from_ha(states_dict)
                    summary = engine.get_summary()
                    result[name] = summary.get("device_count", 0)
                except Exception:
                    logger.warning("ModuleRouter: %s update fehlgeschlagen", name, exc_info=True)

            # HA-Module bekommt Meta-Daten, keine Entity-States
            if self._ha:
                try:
                    self._ha.update_connection_status(
                        reachable=True, response_time_ms=0.0,
                    )
                    result["homeassistant"] = 1
                except Exception:
                    logger.debug("ModuleRouter: HA-Module update fehlgeschlagen", exc_info=True)

            self._last_refresh = time.monotonic()
            self._refresh_count += 1

        return result

    def refresh_from_states_list(self, states_list: list[dict[str, Any]]) -> dict[str, int]:
        """Konvertiert HA-States-Liste in Dict und routet.

        Args:
            states_list: Liste von State-Objekten wie von HomeAssistantClient.get_states()
                         (Format: [{"entity_id": "...", "state": "...", "attributes": {...}}, ...])
        """
        states_dict: dict[str, dict[str, Any]] = {}
        for state_obj in states_list:
            eid = state_obj.get("entity_id", "")
            if eid:
                states_dict[eid] = state_obj
        return self.route_states(states_dict)

    async def async_refresh_from_ha(self) -> dict[str, Any]:
        """Holt alle States vom HA-Client und routet sie an Module.

        Returns:
            Dict mit Refresh-Ergebnis (modules, entity_count, duration_ms)
        """
        if not self._ha_client:
            return {"ok": False, "error": "No HA client configured"}

        t0 = time.monotonic()
        try:
            states_list = await self._ha_client.get_states()
            if not states_list:
                if self._ha:
                    self._ha.update_connection_status(reachable=False, response_time_ms=0.0)
                return {"ok": False, "error": "No states received from HA"}

            modules = self.refresh_from_states_list(states_list)
            duration_ms = (time.monotonic() - t0) * 1000

            if self._ha:
                self._ha.update_connection_status(
                    reachable=True, response_time_ms=duration_ms,
                )

            logger.info(
                "ModuleRouter: Refresh abgeschlossen — %d Entities, %d Module in %.0f ms",
                len(states_list), len(modules), duration_ms,
            )
            return {
                "ok": True,
                "entity_count": len(states_list),
                "modules": modules,
                "duration_ms": round(duration_ms, 1),
            }
        except Exception as exc:
            duration_ms = (time.monotonic() - t0) * 1000
            if self._ha:
                self._ha.update_connection_status(
                    reachable=False, response_time_ms=duration_ms,
                )
            logger.warning("ModuleRouter: Refresh fehlgeschlagen: %s", exc, exc_info=True)
            return {"ok": False, "error": str(exc)}

    # -- Status ---------------------------------------------------------------

    def get_status(self) -> dict[str, Any]:
        """Gibt Router-Status zurueck."""
        modules: dict[str, Any] = {}
        for name, engine, cfg_key in [
            ("zwave", self._zwave, "zwave"),
            ("zigbee", self._zigbee, "zigbee"),
            ("thread", self._thread, "thread"),
            ("homeassistant", self._ha, "homeassistant"),
        ]:
            cfg = self._config.get(cfg_key, {})
            modules[name] = {
                "available": engine is not None,
                "enabled": cfg.get("enabled", True),
                "has_data": False,
            }
            if engine is not None:
                try:
                    summary = engine.get_summary()
                    modules[name]["has_data"] = bool(summary)
                    modules[name]["summary"] = summary
                except Exception:
                    pass

        return {
            "refresh_count": self._refresh_count,
            "last_refresh_ago_s": round(time.monotonic() - self._last_refresh, 1) if self._last_refresh else None,
            "modules": modules,
        }
