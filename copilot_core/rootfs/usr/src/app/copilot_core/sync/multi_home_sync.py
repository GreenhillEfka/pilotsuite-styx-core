"""Multi-Home Sync Orchestrator — Cross-home synchronization engine.

Coordinates synchronization between multiple home instances:
- Discovers and registers homes via HomesRegistry
- Executes sync operations via SyncProtocol
- Handles conflicts via ConflictResolver
- Manages secure data transfer via SecureTransfer

This is the main entry point for multi-home sync operations.
"""

from __future__ import annotations

import logging
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from .homes_registry import HomesRegistry, HomeRegistration, HomeType, HomeStatus
from .sync_protocol import SyncProtocol, SyncEnvelope, SyncResponse, MessageType, SyncDirection
from .conflict_resolver import ConflictResolver, ConflictStrategy, ConflictRecord
from .transfer import SecureTransfer, TransferResult

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------


class SyncMode(str, Enum):
    """Synchronization modes."""
    FULL = "full"           # Complete sync of all data
    INCREMENTAL = "incremental"  # Only changes since last sync
    SELECTIVE = "selective"     # Specific entities/domains only
    CONFIG_ONLY = "config_only"  # Configuration sync only
    STATE_ONLY = "state_only"    # Entity states only


class SyncStatus(str, Enum):
    """Sync job/operation status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFLICT = "conflict"


class SyncScope(str, Enum):
    """What to synchronize."""
    CONFIG = "config"
    STATE = "state"
    AUTOMATIONS = "automations"
    ALL = "all"


@dataclass
class SyncJob:
    """Represents a scheduled or running sync job."""
    id: str
    source_home_id: str
    target_home_id: str
    mode: SyncMode
    scope: SyncScope
    status: str = "pending"  # pending, running, completed, failed, conflict
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    entities_synced: int = 0
    bytes_transferred: int = 0
    conflicts_detected: int = 0
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_home_id": self.source_home_id,
            "target_home_id": self.target_home_id,
            "mode": self.mode.value,
            "scope": self.scope.value,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "entities_synced": self.entities_synced,
            "bytes_transferred": self.bytes_transferred,
            "conflicts_detected": self.conflicts_detected,
            "error": self.error,
        }


# -----------------------------------------------------------------------------


class MultiHomeSync:
    """Main orchestrator for cross-home synchronization.

    Usage:
        sync = MultiHomeSync(home_id="home-1", shared_secret="...")
        sync.register_home("home-2", "Ferienhaus", HomeType.VACATION, "https://...")
        sync.sync_to("home-2", SyncMode.INCREMENTAL, SyncScope.ALL)
    """

    DEFAULT_DATA_DIR = "/data/multihome"

    def __init__(
        self,
        home_id: str,
        shared_secret: Optional[str] = None,
        data_dir: str = DEFAULT_DATA_DIR,
        default_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS,
    ):
        self.home_id = home_id
        self.shared_secret = shared_secret or secrets.token_hex(32)
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._registry = HomesRegistry(str(self.data_dir / "homes_registry.json"))
        self._conflict_resolver = ConflictResolver(
            home_id=home_id,
            default_strategy=default_strategy,
            storage_path=str(self.data_dir / "conflicts.json"),
        )
        self._transfer = SecureTransfer(
            shared_secret=self.shared_secret,
            transfer_dir=str(self.data_dir / "transfers"),
        )
        self._protocol = SyncProtocol(
            home_id=home_id,
            shared_secret=self.shared_secret,
        )

        self._jobs: dict[str, SyncJob] = {}
        self._lock = threading.RLock()
        self._running = False

        # Callbacks
        self._on_sync_start: list[Callable[[SyncJob], None]] = []
        self._on_sync_complete: list[Callable[[SyncJob], None]] = []
        self._on_conflict: list[Callable[[ConflictRecord], None]] = []

        # Wire conflict callbacks
        self._conflict_resolver.on_conflict(self._on_conflict_detected)

    # -------------------------------------------------------------------------
    # Home registration
    # -------------------------------------------------------------------------

    def register_home(
        self,
        home_id: str,
        name: str,
        home_type: HomeType,
        base_url: str,
        auth_token: str = "",
        is_primary: bool = False,
        sync_interval_seconds: int = 300,
    ) -> HomeRegistration:
        """Register a remote home for synchronization."""
        return self._registry.register(
            home_id=home_id,
            name=name,
            home_type=home_type,
            base_url=base_url,
            auth_token=auth_token,
            is_primary=is_primary,
            sync_interval_seconds=sync_interval_seconds,
        )

    def unregister_home(self, home_id: str) -> bool:
        """Remove a home from the registry."""
        return self._registry.unregister(home_id)

    def get_home(self, home_id: str) -> Optional[HomeRegistration]:
        """Get a registered home."""
        return self._registry.get(home_id)

    def list_homes(self) -> list[HomeRegistration]:
        """List all registered homes."""
        return self._registry.list_all()

    @property
    def primary_home(self) -> Optional[HomeRegistration]:
        """Get the primary home registration."""
        return self._registry.get_primary()

    # -------------------------------------------------------------------------
    # Synchronization
    # -------------------------------------------------------------------------

    def sync_to(
        self,
        target_home_id: str,
        mode: SyncMode = SyncMode.INCREMENTAL,
        scope: SyncScope = SyncScope.ALL,
        entity_ids: Optional[list[str]] = None,
    ) -> SyncJob:
        """Synchronize data to a target home.

        This is a PUSH operation: sends local data to the remote home.
        """
        job = SyncJob(
            id=secrets.token_hex(8),
            source_home_id=self.home_id,
            target_home_id=target_home_id,
            mode=mode,
            scope=scope,
        )

        with self._lock:
            self._jobs[job.id] = job

        # Start sync in background thread
        thread = threading.Thread(
            target=self._run_sync_job,
            args=(job, target_home_id, mode, scope, entity_ids),
            daemon=True,
        )
        thread.start()

        return job

    def sync_from(
        self,
        source_home_id: str,
        mode: SyncMode = SyncMode.INCREMENTAL,
        scope: SyncScope = SyncScope.ALL,
        entity_ids: Optional[list[str]] = None,
    ) -> SyncJob:
        """Synchronize data from a source home.

        This is a PULL operation: fetches data from the remote home.
        """
        job = SyncJob(
            id=secrets.token_hex(8),
            source_home_id=source_home_id,
            target_home_id=self.home_id,
            mode=mode,
            scope=scope,
        )

        with self._lock:
            self._jobs[job.id] = job

        thread = threading.Thread(
            target=self._run_pull_sync_job,
            args=(job, source_home_id, mode, scope, entity_ids),
            daemon=True,
        )
        thread.start()

        return job

    def _run_sync_job(
        self,
        job: SyncJob,
        target_home_id: str,
        mode: SyncMode,
        scope: SyncScope,
        entity_ids: Optional[list[str]],
    ) -> None:
        """Execute a push sync job."""
        with self._lock:
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)

        # Notify callbacks
        for cb in self._on_sync_start:
            try:
                cb(job)
            except Exception:
                logger.exception("Error in sync_start callback")

        try:
            target = self._registry.get(target_home_id)
            if not target:
                raise ValueError(f"Target home {target_home_id} not found")

            # Update status
            self._registry.update_status(target_home_id, HomeStatus.SYNCING)

            # Prepare payload based on scope
            payload = self._prepare_sync_payload(scope, mode, entity_ids)

            # Send via protocol
            response = self._protocol.push_config(target.base_url, payload)

            if response.ok:
                job.status = "completed"
                job.entities_synced = response.payload.get("entities_synced", 0)
                job.bytes_transferred = response.payload.get("bytes_transferred", 0)
                self._registry.update_last_sync(target_home_id)
            elif response.error and "conflict" in response.error.lower():
                job.status = "conflict"
                job.conflicts_detected = response.payload.get("conflicts", 1)
            else:
                job.status = "failed"
                job.error = response.error

        except Exception as e:
            logger.exception("Sync job failed")
            job.status = "failed"
            job.error = str(e)

        finally:
            with self._lock:
                job.completed_at = datetime.now(timezone.utc)

            # Notify callbacks
            for cb in self._on_sync_complete:
                try:
                    cb(job)
                except Exception:
                    logger.exception("Error in sync_complete callback")

    def _run_pull_sync_job(
        self,
        job: SyncJob,
        source_home_id: str,
        mode: SyncMode,
        scope: SyncScope,
        entity_ids: Optional[list[str]],
    ) -> None:
        """Execute a pull sync job."""
        with self._lock:
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)

        for cb in self._on_sync_start:
            try:
                cb(job)
            except Exception:
                logger.exception("Error in sync_start callback")

        try:
            source = self._registry.get(source_home_id)
            if not source:
                raise ValueError(f"Source home {source_home_id} not found")

            self._registry.update_status(source_home_id, HomeStatus.SYNCING)

            # Pull from remote
            response = self._protocol.pull_config(source.base_url)

            if response.ok:
                job.status = "completed"
                job.entities_synced = response.payload.get("entities_synced", 0)
                job.bytes_transferred = response.payload.get("bytes_transferred", 0)
                self._registry.update_last_sync(source_home_id)
            elif response.error and "conflict" in response.error.lower():
                job.status = "conflict"
                job.conflicts_detected = response.payload.get("conflicts", 1)
            else:
                job.status = "failed"
                job.error = response.error

        except Exception as e:
            logger.exception("Pull sync job failed")
            job.status = "failed"
            job.error = str(e)

        finally:
            with self._lock:
                job.completed_at = datetime.now(timezone.utc)

            for cb in self._on_sync_complete:
                try:
                    cb(job)
                except Exception:
                    logger.exception("Error in sync_complete callback")

    def _prepare_sync_payload(
        self,
        scope: SyncScope,
        mode: SyncMode,
        entity_ids: Optional[list[str]],
    ) -> dict[str, Any]:
        """Prepare the payload for a sync operation.

        This is a placeholder — actual implementation would gather
        config/state from Home Assistant or the local database.
        """
        now = datetime.now(timezone.utc)

        payload = {
            "source_home_id": self.home_id,
            "sync_mode": mode.value,
            "sync_scope": scope.value,
            "timestamp": now.isoformat(),
            "data": {},
        }

        if entity_ids:
            payload["entity_ids"] = entity_ids

        # Placeholder data — would be replaced with actual HA data
        if scope in (SyncScope.CONFIG, SyncScope.ALL):
            payload["data"]["config"] = {
                "version": "1.0",
                "last_updated": now.isoformat(),
            }

        if scope in (SyncScope.STATE, SyncScope.ALL):
            payload["data"]["states"] = {}

        if scope in (SyncScope.AUTOMATIONS, SyncScope.ALL):
            payload["data"]["automations"] = []

        return payload

    # -------------------------------------------------------------------------
    # Conflict handling
    # -------------------------------------------------------------------------

    def _on_conflict_detected(self, conflict: ConflictRecord) -> None:
        """Internal callback when a conflict is detected."""
        for cb in self._on_conflict:
            try:
                cb(conflict)
            except Exception:
                logger.exception("Error in conflict callback")

    def resolve_conflict(
        self,
        conflict_id: str,
        resolution: Optional[str] = None,
        manual_value: Any = None,
    ) -> Optional[Any]:
        """Resolve a detected conflict."""
        return self._conflict_resolver.resolve(
            conflict_id,
            resolution=resolution,
            manual_value=manual_value,
        )

    def list_conflicts(self, active_only: bool = True) -> list[ConflictRecord]:
        """List detected conflicts."""
        if active_only:
            return self._conflict_resolver.list_active()
        return list(self._conflict_resolver._conflicts.values())

    def set_conflict_strategy(
        self,
        entity_type: str,
        strategy: ConflictStrategy,
    ) -> None:
        """Set conflict resolution strategy for an entity type."""
        self._conflict_resolver.set_strategy_for_entity(entity_type, strategy)

    # -------------------------------------------------------------------------
    # Job management
    # -------------------------------------------------------------------------

    def get_job(self, job_id: str) -> Optional[SyncJob]:
        """Get a sync job by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self, limit: int = 50) -> list[SyncJob]:
        """List recent sync jobs."""
        with self._lock:
            jobs = sorted(
                self._jobs.values(),
                key=lambda j: j.created_at,
                reverse=True,
            )
            return jobs[:limit]

    def cleanup_jobs(self, older_than_days: int = 7) -> int:
        """Remove old completed/failed jobs. Returns count removed."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        removed = 0
        with self._lock:
            to_remove = [
                jid for jid, job in self._jobs.items()
                if job.completed_at and job.completed_at < cutoff
            ]
            for jid in to_remove:
                del self._jobs[jid]
            removed = len(to_remove)
        return removed

    # -------------------------------------------------------------------------
    # Callbacks
    # -------------------------------------------------------------------------

    def on_sync_start(self, callback: Callable[[SyncJob], None]) -> None:
        """Register callback for sync job start."""
        self._on_sync_start.append(callback)

    def on_sync_complete(self, callback: Callable[[SyncJob], None]) -> None:
        """Register callback for sync job completion."""
        self._on_sync_complete.append(callback)

    def on_conflict(self, callback: Callable[[ConflictRecord], None]) -> None:
        """Register callback for conflict detection."""
        self._on_conflict.append(callback)

    # -------------------------------------------------------------------------
    # Status
    # -------------------------------------------------------------------------

    def get_status(self) -> dict[str, Any]:
        """Get overall sync status."""
        homes = [h.to_dict() for h in self._registry.list_all()]
        active_jobs = [j.to_dict() for j in self._jobs.values() if j.status == "running"]
        active_conflicts = self._conflict_resolver.list_active()

        return {
            "home_id": self.home_id,
            "homes": homes,
            "primary_home_id": self._registry.primary_home_id,
            "active_jobs": active_jobs,
            "active_conflicts": [c.to_dict() for c in active_conflicts],
            "conflict_count": len(active_conflicts),
            "total_jobs": len(self._jobs),
        }
