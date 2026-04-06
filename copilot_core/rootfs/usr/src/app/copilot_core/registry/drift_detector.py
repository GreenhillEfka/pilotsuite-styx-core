"""Drift Detector — Runtime automation blueprint change detection.

Compares the current SHA-256 hash of a blueprint loaded from Home Assistant
(or any YAML source) against the hash stored in the BlueprintRegistry to
detect whether the live automation has been modified outside of PilotSuite.

Usage::

    detector = DriftDetector(registry)
    alerts = detector.check_all()
    for alert in alerts:
        print(alert.message)  # human-readable drift alert
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import yaml

from .blueprint_registry import BlueprintRegistryStore, BlueprintEntry
from .hash_calculator import compute_yaml_hash

_LOGGER = logging.getLogger(__name__)


class DriftStatus(Enum):
    CLEAN = "clean"          # Hash matches — no drift detected
    DRIFTED = "drifted"      # Hash mismatch — blueprint changed
    NEW = "new"              # Blueprint not yet in registry
    MISSING = "missing"      # Was in registry, now gone from HA
    ERROR = "error"          # Could not load/parse blueprint


@dataclass
class DriftAlert:
    """Single drift detection result."""
    blueprint_id: str
    name: str
    status: DriftStatus
    stored_hash: Optional[str] = None
    current_hash: Optional[str] = None
    message: str = ""
    detected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    severity: str = "warning"  # info | warning | critical

    def to_dict(self) -> Dict[str, Any]:
        return {
            "blueprint_id": self.blueprint_id,
            "name": self.name,
            "status": self.status.value,
            "stored_hash": self.stored_hash,
            "current_hash": self.current_hash,
            "message": self.message,
            "detected_at": self.detected_at,
            "severity": self.severity,
        }


class DriftDetector:
    """Detects runtime changes (drift) in automation blueprints."""

    def __init__(
        self,
        registry: BlueprintRegistryStore,
        data_dir: str = "/data",
    ) -> None:
        self._registry = registry
        self._data_dir = data_dir

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_blueprint(
        self,
        blueprint_id: str,
        current_yaml: Optional[str] = None,
        current_dict: Optional[Dict[str, Any]] = None,
    ) -> DriftAlert:
        """Check a single blueprint for drift.

        Pass either the raw YAML string (``current_yaml``) or the already-parsed
        dict (``current_dict``), but not both.
        """
        entry = self._registry.get(blueprint_id)
        name = entry.name if entry else blueprint_id

        if current_dict is not None:
            current_hash = self._compute_hash(current_dict)
        elif current_yaml is not None:
            current_hash = compute_yaml_hash(current_yaml)
        else:
            return DriftAlert(
                blueprint_id=blueprint_id,
                name=name,
                status=DriftStatus.ERROR,
                message="Neither yaml nor dict provided",
                severity="warning",
            )

        if entry is None:
            alert = DriftAlert(
                blueprint_id=blueprint_id,
                name=name,
                status=DriftStatus.NEW,
                stored_hash=None,
                current_hash=current_hash,
                message=f"Blueprint '{name}' is new and has been registered.",
                severity="info",
            )
        elif entry.hash != current_hash:
            entry = self._registry.record_drift(blueprint_id) or entry
            # re-fetch to get updated drift_count
            updated = self._registry.get(blueprint_id)
            drift_count = updated.drift_count if updated else (entry.drift_count + 1)
            severity = "critical" if drift_count >= 3 else "warning"
            alert = DriftAlert(
                blueprint_id=blueprint_id,
                name=name,
                status=DriftStatus.DRIFTED,
                stored_hash=entry.hash,
                current_hash=current_hash,
                message=(
                    f"Blueprint '{name}' has changed — "
                    f"expected hash {entry.hash[:12]}..., "
                    f"got {current_hash[:12]}... "
                    f"(drift #{drift_count})"
                ),
                severity=severity,
            )
        else:
            alert = DriftAlert(
                blueprint_id=blueprint_id,
                name=name,
                status=DriftStatus.CLEAN,
                stored_hash=entry.hash,
                current_hash=current_hash,
                message=f"Blueprint '{name}' is unchanged.",
                severity="info",
            )

        return alert

    def check_batch(
        self,
        blueprints: Dict[str, Dict[str, Any]],
    ) -> List[DriftAlert]:
        """Check multiple blueprints at once.

        ``blueprints`` is a mapping from blueprint_id → blueprint dict.
        """
        alerts: List[DriftAlert] = []
        for blueprint_id, bp_dict in blueprints.items():
            try:
                alert = self.check_blueprint(blueprint_id, current_dict=bp_dict)
                alerts.append(alert)
            except Exception as exc:
                _LOGGER.warning(
                    "Drift check failed for %s: %s", blueprint_id, exc
                )
                alerts.append(
                    DriftAlert(
                        blueprint_id=blueprint_id,
                        name=blueprint_id,
                        status=DriftStatus.ERROR,
                        message=f"Check failed: {exc}",
                        severity="warning",
                    )
                )
        return alerts

    def check_all(self) -> List[DriftAlert]:
        """Check all blueprints currently registered for drift.

        Loads YAML files from ``{data_dir}/blueprints/{domain}/`` and compares
        their hashes against the registry.

        Returns a list of alerts (one per registered blueprint, including
        MISSING entries for blueprints that were in the registry but have
        no corresponding file on disk).
        """
        alerts: List[DriftAlert] = []
        entries = self._registry.list_all(active_only=False)

        for entry in entries:
            file_path = self._resolve_path(entry)
            if file_path is None:
                alerts.append(
                    DriftAlert(
                        blueprint_id=entry.blueprint_id,
                        name=entry.name,
                        status=DriftStatus.MISSING,
                        stored_hash=entry.hash,
                        message=f"Blueprint '{entry.name}' file not found on disk.",
                        severity="warning",
                    )
                )
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as fh:
                    yaml_content = fh.read()
                alert = self.check_blueprint(
                    entry.blueprint_id,
                    current_yaml=yaml_content,
                )
                alerts.append(alert)
            except FileNotFoundError:
                alerts.append(
                    DriftAlert(
                        blueprint_id=entry.blueprint_id,
                        name=entry.name,
                        status=DriftStatus.MISSING,
                        stored_hash=entry.hash,
                        message=f"Blueprint file not found: {file_path}",
                        severity="warning",
                    )
                )
            except Exception as exc:
                _LOGGER.warning(
                    "Failed to check blueprint %s: %s", entry.blueprint_id, exc
                )
                alerts.append(
                    DriftAlert(
                        blueprint_id=entry.blueprint_id,
                        name=entry.name,
                        status=DriftStatus.ERROR,
                        stored_hash=entry.hash,
                        message=f"Failed to read file: {exc}",
                        severity="warning",
                    )
                )

        return alerts

    def get_drift_summary(self) -> Dict[str, Any]:
        """Return a high-level drift summary for all registered blueprints."""
        alerts = self.check_all()
        by_status: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        for a in alerts:
            by_status[a.status.value] = by_status.get(a.status.value, 0) + 1
            by_severity[a.severity] = by_severity.get(a.severity, 0) + 1

        critical = [a.to_dict() for a in alerts if a.severity == "critical"]
        return {
            "total": len(alerts),
            "by_status": by_status,
            "by_severity": by_severity,
            "critical_drifts": critical,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_hash(self, blueprint_dict: Dict[str, Any]) -> str:
        """Compute hash from a parsed blueprint dict."""
        # Import here to avoid circular import at module level
        from .hash_calculator import compute_blueprint_hash
        return compute_blueprint_hash(blueprint_dict)

    def _resolve_path(self, entry: BlueprintEntry) -> Optional[str]:
        """Resolve the filesystem path for a registered blueprint entry."""
        if entry.file_path:
            path = Path(entry.file_path)
            if path.is_absolute():
                return str(path) if path.exists() else None
            # Relative to data_dir
            path = Path(self._data_dir) / entry.file_path
            return str(path) if path.exists() else None

        # Fallback: construct from domain
        domain = entry.domain or "automation"
        path = Path(self._data_dir) / "blueprints" / domain / f"{entry.blueprint_id}.yaml"
        return str(path) if path.exists() else None


# ---------------------------------------------------------------------------
# Global detector (lazy)
# ---------------------------------------------------------------------------

_detector: Optional[DriftDetector] = None


def get_drift_detector(
    db_path: str = "/data/blueprint_registry.db",
    data_dir: str = "/data",
) -> DriftDetector:
    global _detector
    if _detector is None:
        from .blueprint_registry import get_blueprint_registry
        registry = get_blueprint_registry(db_path)
        _detector = DriftDetector(registry, data_dir)
    return _detector
