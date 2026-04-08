"""
Basic tests for log_fixer_tx module

Run with: python3 -m pytest tests/test_log_fixer_tx.py
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from copilot_core.log_fixer_tx import TransactionLog, RenameOperation, SetEnabledOperation
from copilot_core.log_fixer_tx.recovery import TransactionManager


@pytest.fixture(autouse=True)
def _allow_tmp_paths():
    """Allow /tmp paths in tests for rename operations."""
    with patch("copilot_core.log_fixer_tx.operations.validate_rename_path", return_value=True):
        yield


def test_transaction_log_basic():
    """Test basic transaction log functionality."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "test.jsonl")
        log = TransactionLog(log_path)
        
        # Begin transaction
        tx_id = log.begin_tx(
            actor={"service": "test", "user": "test_user", "host": "test_host"},
            reason="Test transaction"
        )
        
        assert tx_id is not None
        assert len(tx_id) > 0
        
        # Append intent
        operation = {
            "kind": "rename",
            "target": "/test/file.txt",
            "before": {"path": "/test/old.txt"},
            "after": {"path": "/test/new.txt"},
            "inverse": {
                "kind": "rename",
                "target": "/test/file.txt",
                "before": {"path": "/test/new.txt"},
                "after": {"path": "/test/old.txt"},
            }
        }
        
        record = log.append_intent(
            tx_id=tx_id,
            seq=1,
            actor={"service": "test", "user": "test_user", "host": "test_host"},
            operation=operation,
            reason="Test rename"
        )
        
        assert record["txId"] == tx_id
        assert record["type"] == "INTENT"
        assert record["seq"] == 1
        
        # Check state
        state = log.get_tx_state(tx_id)
        assert state == "in-flight"
        
        # Append outcome
        log.append_outcome(tx_id, 1, "APPLIED")
        
        state = log.get_tx_state(tx_id)
        assert state == "applied"


def test_rename_operation_idempotent():
    """Test rename operation idempotency."""
    with tempfile.TemporaryDirectory() as tmpdir:
        old_path = os.path.join(tmpdir, "old.txt")
        new_path = os.path.join(tmpdir, "new.txt")
        
        # Create source file
        Path(old_path).write_text("test content")
        
        # Create operation
        op = RenameOperation(
            target="/test/file.txt",
            before={"path": old_path},
            after={"path": new_path}
        )
        
        # First apply
        op.apply()
        assert Path(new_path).exists()
        assert not Path(old_path).exists()
        
        # Second apply (idempotent - should not fail)
        op.apply()
        assert Path(new_path).exists()
        assert not Path(old_path).exists()
        
        # Rollback
        op.rollback()
        assert Path(old_path).exists()
        assert not Path(new_path).exists()
        
        # Second rollback (idempotent)
        op.rollback()
        assert Path(old_path).exists()
        assert not Path(new_path).exists()


def test_set_enabled_operation():
    """Test set_enabled operation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target_path = os.path.join(tmpdir, "module.conf")
        disabled_path = target_path + ".disabled"
        
        # Create enabled file
        Path(target_path).write_text("config content")
        
        # Create disable operation
        op = SetEnabledOperation(
            target=target_path,
            before={"enabled": True},
            after={"enabled": False}
        )
        
        # Apply disable
        op.apply()
        assert not Path(target_path).exists()
        assert Path(disabled_path).exists()
        
        # Second apply (idempotent)
        op.apply()
        assert not Path(target_path).exists()
        assert Path(disabled_path).exists()
        
        # Rollback (re-enable)
        op.rollback()
        assert Path(target_path).exists()
        assert not Path(disabled_path).exists()


def test_transaction_manager_full_flow():
    """Test full transaction flow with TransactionManager."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "tx.jsonl")
        tm = TransactionManager(log_path)
        
        # Create test file
        test_file = os.path.join(tmpdir, "test.txt")
        new_file = os.path.join(tmpdir, "renamed.txt")
        Path(test_file).write_text("test")
        
        # Begin transaction
        actor = {"service": "test", "user": "test", "host": "localhost"}
        tx_id = tm.begin_tx(actor, "Test rename transaction")
        
        # Append intent (with inverse for rollback)
        operation = {
            "kind": "rename",
            "target": test_file,
            "before": {"path": test_file},
            "after": {"path": new_file},
            "inverse": {
                "kind": "rename",
                "target": new_file,
                "before": {"path": new_file},
                "after": {"path": test_file},
            },
        }

        tm.append_intent(tx_id, 1, actor, operation)

        # Apply transaction
        result = tm.apply_tx(tx_id)
        assert result["success"] is True
        assert Path(new_file).exists()
        assert not Path(test_file).exists()

        # Rollback
        rollback_result = tm.rollback_tx(tx_id)
        assert rollback_result["success"] is True
        assert Path(test_file).exists()
        assert not Path(new_file).exists()


def test_transaction_log_fallback_path_when_unwritable():
    """Falls back to a writable temp path if /data is unavailable."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("copilot_core.log_fixer_tx.transaction_log.Path.mkdir") as mock_mkdir:
            mock_mkdir.side_effect = [PermissionError("denied"), None]
            with patch.dict(os.environ, {"COPILOT_TX_LOG_DIR": tmpdir}):
                log = TransactionLog("/data/logs/log_fixer_tx.jsonl")
        assert str(log.log_path).startswith(tmpdir)
        assert mock_mkdir.call_count == 2


def test_recovery_in_flight():
    """Test recovery of in-flight transactions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "tx.jsonl")
        tm = TransactionManager(log_path)
        
        # Create test file
        test_file = os.path.join(tmpdir, "test.txt")
        new_file = os.path.join(tmpdir, "renamed.txt")
        Path(test_file).write_text("test")
        
        # Simulate incomplete transaction (intent without apply)
        actor = {"service": "test", "user": "test", "host": "localhost"}
        tx_id = tm.begin_tx(actor, "Test incomplete transaction")
        
        operation = {
            "kind": "rename",
            "target": test_file,
            "before": {"path": test_file},
            "after": {"path": new_file},
            "inverse": {
                "kind": "rename",
                "target": new_file,
                "before": {"path": new_file},
                "after": {"path": test_file},
            },
        }

        tm.append_intent(tx_id, 1, actor, operation)

        # Don't apply - simulate crash

        # New manager instance (simulates restart)
        tm2 = TransactionManager(log_path)
        
        # Check in-flight
        in_flight = tm2.log.list_in_flight_tx()
        assert tx_id in in_flight
        
        # Recover
        report = tm2.recover()
        assert len(report.in_flight_tx) > 0
        
        # Check that transaction was rolled back
        state = tm2.log.get_tx_state(tx_id)
        assert state == "rolled_back"


if __name__ == "__main__":
    # Run basic tests
    print("Running test_transaction_log_basic...")
    test_transaction_log_basic()
    print("✓ PASS")
    
    print("Running test_rename_operation_idempotent...")
    test_rename_operation_idempotent()
    print("✓ PASS")
    
    print("Running test_set_enabled_operation...")
    test_set_enabled_operation()
    print("✓ PASS")
    
    print("Running test_transaction_manager_full_flow...")
    test_transaction_manager_full_flow()
    print("✓ PASS")
    
    print("Running test_recovery_in_flight...")
    test_recovery_in_flight()
    print("✓ PASS")
    
    print("\nAll tests passed! ✓")
