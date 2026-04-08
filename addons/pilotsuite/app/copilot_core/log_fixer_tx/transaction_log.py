"""
Transaction Log Engine - Append-only JSONL-based WAL
"""
import json
import logging
import os
import fcntl
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
import ulid

logger = logging.getLogger(__name__)


class TransactionLog:
    """
    Append-only transaction log with Write-Ahead Logging (WAL).
    
    Thread-safe via file locking (fcntl.flock).
    """
    
    def __init__(self, log_path: str = "/data/logs/log_fixer_tx.jsonl"):
        self.log_path = self._resolve_writable_log_path(Path(log_path))
        self.lock_path = Path(str(self.log_path) + ".lock")
        self._lock_fd = None
        
    def _resolve_writable_log_path(self, configured_path: Path) -> Path:
        """Resolve a writable log path (fallback outside add-on runtime)."""
        try:
            configured_path.parent.mkdir(parents=True, exist_ok=True)
            return configured_path
        except OSError:
            fallback_dir = Path(os.environ.get("COPILOT_TX_LOG_DIR", "/tmp"))
            fallback_dir.mkdir(parents=True, exist_ok=True)
            fallback_path = fallback_dir / configured_path.name
            logger.warning(
                "TransactionLog path %s is not writable, using fallback %s",
                configured_path,
                fallback_path,
            )
            return fallback_path
        
    def _acquire_lock(self):
        """Acquire exclusive lock on log file (single-writer)."""
        self._lock_fd = open(self.lock_path, 'w')
        fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_EX)
        
    def _release_lock(self):
        """Release lock on log file."""
        if self._lock_fd:
            fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_UN)
            self._lock_fd.close()
            self._lock_fd = None
            
    def begin_tx(
        self,
        actor: Dict[str, str],
        reason: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Begin a new transaction.
        
        Args:
            actor: {"service": "...", "user": "...", "host": "..."}
            reason: Human-readable reason
            meta: Optional metadata (e.g., correlationId)
            
        Returns:
            txId (ULID string)
        """
        tx_id = str(ulid.ULID())
        return tx_id
        
    def append_intent(
        self,
        tx_id: str,
        seq: int,
        actor: Dict[str, str],
        operation: Dict[str, Any],
        reason: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Append INTENT record (Write-Ahead Log).
        
        Args:
            tx_id: Transaction ID
            seq: Sequence number (1..n)
            actor: Actor info
            operation: {kind, target, before, after, inverse}
            reason: Optional reason
            meta: Optional metadata
            
        Returns:
            Record dict
        """
        record = {
            "v": 1,
            "ts": datetime.now(timezone.utc).isoformat(),
            "txId": tx_id,
            "seq": seq,
            "type": "INTENT",
            "actor": actor,
            "op": operation,
        }
        
        if reason:
            record["reason"] = reason
        if meta:
            record["meta"] = meta
            
        self._append_record(record)
        return record
        
    def append_outcome(
        self,
        tx_id: str,
        seq: int,
        outcome_type: str,  # APPLIED | FAILED | ROLLED_BACK | ABORTED
        error: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Append outcome record (APPLIED, FAILED, ROLLED_BACK, ABORTED).
        
        Args:
            tx_id: Transaction ID
            seq: Sequence number
            outcome_type: Type of outcome
            error: Optional error dict for FAILED
            
        Returns:
            Record dict
        """
        record = {
            "v": 1,
            "ts": datetime.now(timezone.utc).isoformat(),
            "txId": tx_id,
            "seq": seq,
            "type": outcome_type,
        }
        
        if error:
            record["error"] = error
            
        self._append_record(record)
        return record
        
    def _append_record(self, record: Dict[str, Any]):
        """
        Append record to log file with fsync for durability.
        
        Thread-safe via file locking.
        """
        try:
            self._acquire_lock()
            
            # Append to log file
            with open(self.log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
                f.flush()
                os.fsync(f.fileno())  # Ensure durability
                
        finally:
            self._release_lock()
            
    def read_all_records(self) -> List[Dict[str, Any]]:
        """
        Read all records from log file.
        
        Returns:
            List of record dicts
        """
        if not self.log_path.exists():
            return []
            
        records = []
        with open(self.log_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        # Log corruption - should be handled by recovery
                        logger.warning(f"Corrupted log line: {e}")
                        
        return records
        
    def get_tx_records(self, tx_id: str) -> List[Dict[str, Any]]:
        """
        Get all records for a specific transaction.
        
        Args:
            tx_id: Transaction ID
            
        Returns:
            List of records for this transaction
        """
        all_records = self.read_all_records()
        return [r for r in all_records if r.get("txId") == tx_id]
        
    def get_tx_state(self, tx_id: str) -> str:
        """
        Determine the current state of a transaction.
        
        Args:
            tx_id: Transaction ID
            
        Returns:
            State: "in-flight" | "applied" | "failed" | "rolled_back" | "aborted" | "unknown"
        """
        records = self.get_tx_records(tx_id)
        
        if not records:
            return "unknown"
            
        # Check for outcome records
        has_intent = any(r.get("type") == "INTENT" for r in records)
        has_applied = any(r.get("type") == "APPLIED" for r in records)
        has_failed = any(r.get("type") == "FAILED" for r in records)
        has_rolled_back = any(r.get("type") == "ROLLED_BACK" for r in records)
        has_aborted = any(r.get("type") == "ABORTED" for r in records)
        
        if has_rolled_back:
            return "rolled_back"
        elif has_aborted:
            return "aborted"
        elif has_failed:
            return "failed"
        elif has_applied:
            return "applied"
        elif has_intent:
            return "in-flight"
        else:
            return "unknown"
            
    def list_in_flight_tx(self) -> List[str]:
        """
        List all in-flight (incomplete) transactions.
        
        Returns:
            List of transaction IDs
        """
        all_records = self.read_all_records()
        tx_ids = set(r.get("txId") for r in all_records if r.get("txId"))
        
        in_flight = []
        for tx_id in tx_ids:
            if self.get_tx_state(tx_id) == "in-flight":
                in_flight.append(tx_id)
                
        return sorted(in_flight)
