"""
Candidate Storage - Manage automation suggestion lifecycle.

The candidate store manages potential automation suggestions discovered by the habitus miner.
Each candidate represents an A→B pattern that could become a user automation.

Lifecycle states:
- pending: Fresh candidate, not yet presented to user
- offered: Shown to user via HA Repairs UI  
- accepted: User confirmed, blueprint created
- dismissed: User rejected this suggestion
- deferred: User wants to see again later (with retry_after timestamp)

Privacy: All data stays local, no external transmission.
Persistence: Simple JSON file storage for MVP.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Literal

CandidateState = Literal["pending", "offered", "accepted", "dismissed", "deferred"]

class Candidate:
    """A single automation suggestion candidate."""
    
    def __init__(self, 
                 candidate_id: str = None,
                 pattern_id: str = None,
                 state: CandidateState = "pending",
                 evidence: Dict[str, Any] = None,
                 created_at: float = None,
                 updated_at: float = None,
                 retry_after: float = None,
                 metadata: Dict[str, Any] = None):
        self.candidate_id = candidate_id or str(uuid.uuid4())
        self.pattern_id = pattern_id  # Reference to brain graph pattern
        self.state = state
        self.evidence = evidence or {}  # support/confidence/lift from miner
        self.created_at = created_at or time.time()
        self.updated_at = updated_at or time.time()
        self.retry_after = retry_after  # For deferred candidates
        self.metadata = metadata or {}  # Additional context
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "candidate_id": self.candidate_id,
            "pattern_id": self.pattern_id,
            "state": self.state,
            "evidence": self.evidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "retry_after": self.retry_after,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Candidate":
        """Deserialize from JSON dict."""
        return cls(**data)
    
    def update_state(self, new_state: CandidateState, retry_after: float = None) -> None:
        """Update candidate state and timestamp."""
        self.state = new_state
        self.updated_at = time.time()
        if retry_after is not None:
            self.retry_after = retry_after


class CandidateStore:
    """Persistent storage for automation candidates."""
    
    def __init__(self, storage_path: str = "/data/candidates.json"):
        self.storage_path = Path(storage_path)
        self._candidates: Dict[str, Candidate] = {}
        # RLock allows nested calls (e.g. add_candidate -> _save_to_disk)
        self._lock = threading.RLock()
        self._load_from_disk()
    
    def _load_from_disk(self) -> None:
        """Load candidates from JSON file."""
        if not self.storage_path.exists():
            return

        with self._lock:
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for candidate_data in data.get("candidates", []):
                        candidate = Candidate.from_dict(candidate_data)
                        self._candidates[candidate.candidate_id] = candidate
            except Exception:
                # Corrupted file - start fresh but don't crash
                self._candidates = {}
    
    def _save_to_disk(self) -> None:
        """Persist candidates to JSON file (caller must hold self._lock)."""
        try:
            # Ensure directory exists
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            # Backup existing file before overwrite
            backup_path = self.storage_path.with_suffix('.bak')
            if self.storage_path.exists():
                try:
                    self.storage_path.replace(backup_path)
                except OSError:
                    pass  # best-effort backup

            # Write atomically via temp file
            temp_path = self.storage_path.with_suffix('.tmp')
            data = {
                "version": 1,
                "saved_at": time.time(),
                "candidates": [c.to_dict() for c in self._candidates.values()]
            }

            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Atomic replace
            temp_path.replace(self.storage_path)

        except Exception as e:
            raise RuntimeError(f"Failed to save candidates: {e}")
    
    def add_candidate(self, pattern_id: str, evidence: Dict[str, Any],
                     metadata: Dict[str, Any] = None) -> str:
        """Add new candidate from pattern discovery."""
        with self._lock:
            candidate = Candidate(
                pattern_id=pattern_id,
                evidence=evidence,
                metadata=metadata or {}
            )
            self._candidates[candidate.candidate_id] = candidate
            self._save_to_disk()
            return candidate.candidate_id

    def get_candidate(self, candidate_id: str) -> Optional[Candidate]:
        """Get candidate by ID."""
        with self._lock:
            return self._candidates.get(candidate_id)

    def update_candidate_state(self, candidate_id: str, new_state: CandidateState,
                              retry_after: float = None) -> bool:
        """Update candidate state. Returns True if found and updated."""
        with self._lock:
            candidate = self._candidates.get(candidate_id)
            if not candidate:
                return False
            candidate.update_state(new_state, retry_after)
            self._save_to_disk()
            return True

    def list_candidates(self, state: CandidateState = None,
                       include_ready_deferred: bool = False) -> List[Candidate]:
        """List candidates, optionally filtered by state."""
        with self._lock:
            result = []
            now = time.time()

            for candidate in self._candidates.values():
                # State filter
                if state and candidate.state != state:
                    continue

                # Handle deferred candidates
                if candidate.state == "deferred":
                    if include_ready_deferred and candidate.retry_after and now >= candidate.retry_after:
                        result.append(candidate)
                    elif not include_ready_deferred:
                        result.append(candidate)
                    # Skip deferred candidates that aren't ready yet
                    continue
                else:
                    result.append(candidate)

            # Sort by created_at (newest first)
            return sorted(result, key=lambda c: c.created_at, reverse=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        with self._lock:
            now = time.time()
            stats = {"total": len(self._candidates)}

            # Count by state
            for state in ["pending", "offered", "accepted", "dismissed", "deferred"]:
                stats[state] = len([c for c in self._candidates.values() if c.state == state])

            # Ready deferred candidates
            ready_deferred = len([
                c for c in self._candidates.values()
                if c.state == "deferred" and c.retry_after and now >= c.retry_after
            ])
            stats["ready_deferred"] = ready_deferred

            return stats

    def cleanup_old_candidates(self, max_age_days: int = 30) -> int:
        """Remove old dismissed/accepted candidates. Returns count removed."""
        with self._lock:
            cutoff = time.time() - (max_age_days * 24 * 60 * 60)
            to_remove = []

            for candidate_id, candidate in self._candidates.items():
                if candidate.state in ["dismissed", "accepted"] and candidate.updated_at < cutoff:
                    to_remove.append(candidate_id)

            for candidate_id in to_remove:
                del self._candidates[candidate_id]

            if to_remove:
                self._save_to_disk()

            return len(to_remove)