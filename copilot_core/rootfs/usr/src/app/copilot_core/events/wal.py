"""Write-Ahead Log for Semantic Events — PilotSuite Core.

Stores only high-value semantic events:
- Zone transitions
- Intent completions
- Rule evaluations
- Learning memory updates
- Automation decisions

NOT stored: raw sensor events, heartbeat pings, debug traces.

Location: /config/copilot_core/events/wal/
Rotation: 24h or 10MB, compressed archive.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Iterator

_LOGGER = logging.getLogger(__name__)

WAL_BASE_DIR = "/config/copilot_core/events/wal"
WAL_ARCHIVE_DIR = "/config/copilot_core/events/wal/archive"
WAL_MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
WAL_ROTATION_INTERVAL_HOURS = 24
WAL_CURRENT_FILE = "wal_current.jsonl"

SEMANTIC_EVENT_TYPES = {
    "zone_transition",
    "intent_complete",
    "intent_start",
    "rule_evaluated",
    "learning_update",
    "automation_decision",
    "habitus_context_change",
    "presence_confidence_update",
    "anomaly_detected",
    "proposal_generated",
    "feedback_received",
}


class WALEntry:
    """Single WAL entry."""
    __slots__ = ("event_type", "event_id", "timestamp", "source", "data", "version")

    def __init__(
        self,
        event_type: str,
        event_id: str,
        timestamp: str,
        source: str,
        data: Dict[str, Any],
        version: int = 1,
    ):
        self.event_type = event_type
        self.event_id = event_id
        self.timestamp = timestamp
        self.source = source
        self.data = data
        self.version = version

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "source": self.source,
            "data": self.data,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WALEntry":
        return cls(
            event_type=d["event_type"],
            event_id=d["event_id"],
            timestamp=d["timestamp"],
            source=d.get("source", ""),
            data=d.get("data", {}),
            version=d.get("version", 1),
        )


class WriteAheadLog:
    """Append-only WAL for semantic events."""

    def __init__(self, base_dir: str = WAL_BASE_DIR):
        self.base_dir = Path(base_dir)
        self.archive_dir = Path(WAL_ARCHIVE_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self._current_path = self.base_dir / WAL_CURRENT_FILE
        self._lock = asyncio.Lock()
        self._last_rotation = datetime.now(timezone.utc)
        self._bytes_written = 0

    def _should_rotate(self) -> bool:
        """Check if WAL should rotate."""
        now = datetime.now(timezone.utc)
        age_hours = (now - self._last_rotation).total_seconds() / 3600
        if age_hours >= WAL_ROTATION_INTERVAL_HOURS:
            return True
        if self._current_path.exists():
            size = self._current_path.stat().st_size
            if size >= WAL_MAX_SIZE_BYTES:
                return True
        return False

    async def write(self, entry: WALEntry) -> None:
        """Append entry to WAL."""
        if entry.event_type not in SEMANTIC_EVENT_TYPES:
            _LOGGER.debug("Skipping non-semantic event %s", entry.event_type)
            return

        async with self._lock:
            if self._should_rotate():
                await self._rotate()

            line = json.dumps(entry.to_dict(), ensure_ascii=False) + "\n"
            with open(self._current_path, "a", encoding="utf-8") as f:
                f.write(line)
            self._bytes_written += len(line.encode())

    async def _rotate(self) -> None:
        """Rotate WAL: compress current file, start new one."""
        if not self._current_path.exists():
            self._last_rotation = datetime.now(timezone.utc)
            return

        timestamp = self._last_rotation.strftime("%Y%m%d_%H%M%S")
        archive_name = f"wal_{timestamp}.jsonl.gz"
        archive_path = self.archive_dir / archive_name

        # Compress current file
        with open(self._current_path, "rb") as f_in:
            with gzip.open(archive_path, "wb") as f_out:
                f_out.writelines(f_in)

        # Truncate current
        self._current_path.unlink(missing_ok=True)
        self._last_rotation = datetime.now(timezone.utc)
        self._bytes_written = 0
        _LOGGER.info("WAL rotated to %s", archive_name)

    def replay(
        self,
        event_type: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 1000,
    ) -> Iterator[WALEntry]:
        """Replay WAL entries (oldest first)."""
        # Replay current + all archived files
        files = sorted(self.archive_dir.glob("wal_*.jsonl.gz"))
        if self._current_path.exists():
            files.append(self._current_path)

        count = 0
        for fpath in files:
            try:
                if fpath.suffix == ".gz":
                    opener = gzip.open
                else:
                    opener = open

                with opener(fpath, "rt", encoding="utf-8") as f:
                    for line in f:
                        if count >= limit:
                            return
                        try:
                            d = json.loads(line)
                            entry = WALEntry.from_dict(d)
                        except (json.JSONDecodeError, KeyError):
                            continue

                        if event_type and entry.event_type != event_type:
                            continue
                        if since:
                            ts = datetime.fromisoformat(entry.timestamp)
                            if ts < since:
                                continue

                        yield entry
                        count += 1
            except (OSError, gzip.BadGzipFile) as e:
                _LOGGER.warning("Could not read WAL file %s: %s", fpath, e)

    async def get_stats(self) -> Dict[str, Any]:
        """Get WAL statistics."""
        archive_files = list(self.archive_dir.glob("wal_*.jsonl.gz"))
        current_size = self._current_path.stat().st_size if self._current_path.exists() else 0
        archive_size = sum(f.stat().st_size for f in archive_files)
        return {
            "current_size_bytes": current_size,
            "archived_files": len(archive_files),
            "archived_size_bytes": archive_size,
            "last_rotation": self._last_rotation.isoformat(),
            "rotation_interval_hours": WAL_ROTATION_INTERVAL_HOURS,
            "max_size_bytes": WAL_MAX_SIZE_BYTES,
        }


# Singleton
_wal: Optional[WriteAheadLog] = None


def get_wal() -> WriteAheadLog:
    global _wal
    if _wal is None:
        _wal = WriteAheadLog()
    return _wal


async def wal_write(
    event_type: str,
    event_id: str,
    source: str,
    data: Dict[str, Any],
    version: int = 1,
) -> None:
    """Convenience: write semantic event to WAL."""
    entry = WALEntry(
        event_type=event_type,
        event_id=event_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        source=source,
        data=data,
        version=version,
    )
    await get_wal().write(entry)
