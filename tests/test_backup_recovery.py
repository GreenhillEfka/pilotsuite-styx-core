"""Tests for Backup & Recovery Engine — Slice 23."""
import pytest
from copilot_core.backup.engine import (
    BackupRecoveryEngine,
    BackupType,
    BackupStatus,
    RecoveryStatus,
    create_backup_recovery_engine,
)
from datetime import datetime, timezone, timedelta


class TestBackupRecoveryEngine:
    """Test backup/recovery engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_backup_recovery_engine()
        assert engine is not None
    
    def test_create_full_backup(self):
        """Test creating full backup."""
        engine = BackupRecoveryEngine()
        
        backup_id = engine.create_backup(backup_type=BackupType.FULL)
        
        assert backup_id is not None
        assert backup_id.startswith("backup_")
        assert backup_id in engine._manifests
        
        manifest = engine._manifests[backup_id]
        assert manifest.backup_type == BackupType.FULL
        assert manifest.status == BackupStatus.COMPLETED
    
    def test_create_incremental_backup(self):
        """Test creating incremental backup."""
        engine = BackupRecoveryEngine()
        
        backup_id = engine.create_backup(backup_type=BackupType.INCREMENTAL)
        
        assert backup_id is not None
        manifest = engine._manifests[backup_id]
        assert manifest.backup_type == BackupType.INCREMENTAL
    
    def test_create_config_only_backup(self):
        """Test creating config-only backup."""
        engine = BackupRecoveryEngine()
        
        backup_id = engine.create_backup(backup_type=BackupType.CONFIG_ONLY)
        
        manifest = engine._manifests[backup_id]
        assert manifest.backup_type == BackupType.CONFIG_ONLY
    
    def test_backup_has_checksum(self):
        """Test that backup has checksum."""
        engine = BackupRecoveryEngine()
        
        backup_id = engine.create_backup(backup_type=BackupType.FULL)
        manifest = engine._manifests[backup_id]
        
        assert manifest.checksum != ""
        assert len(manifest.checksum) == 64  # SHA256 hex length
    
    def test_backup_has_size(self):
        """Test that backup has size."""
        engine = BackupRecoveryEngine()
        
        backup_id = engine.create_backup(backup_type=BackupType.FULL)
        manifest = engine._manifests[backup_id]
        
        assert manifest.size_bytes > 0
    
    def test_verify_backup_success(self):
        """Test successful backup verification."""
        engine = BackupRecoveryEngine()
        
        backup_id = engine.create_backup(backup_type=BackupType.FULL)
        
        result = engine.verify_backup(backup_id)
        
        assert result is True
        assert engine._manifests[backup_id].verified is True
        assert engine._manifests[backup_id].status == BackupStatus.VERIFIED
    
    def test_verify_unknown_backup(self):
        """Test verifying unknown backup."""
        engine = BackupRecoveryEngine()
        
        result = engine.verify_backup("unknown_backup")
        
        assert result is False
    
    def test_verify_incomplete_backup(self):
        """Test verifying incomplete backup."""
        engine = BackupRecoveryEngine()
        
        # Create backup and manually set to pending
        backup_id = engine.create_backup(backup_type=BackupType.FULL)
        engine._manifests[backup_id].status = BackupStatus.PENDING
        
        result = engine.verify_backup(backup_id)
        
        assert result is False
    
    def test_create_recovery_plan(self):
        """Test creating recovery plan."""
        engine = BackupRecoveryEngine()
        
        backup_id = engine.create_backup(backup_type=BackupType.FULL)
        
        recovery_id = engine.create_recovery_plan(backup_id)
        
        assert recovery_id is not None
        assert recovery_id.startswith("recovery_")
        assert recovery_id in engine._recovery_plans
        
        plan = engine._recovery_plans[recovery_id]
        assert plan.backup_id == backup_id
        assert plan.status == RecoveryStatus.PENDING
    
    def test_create_recovery_plan_unknown_backup(self):
        """Test creating recovery plan for unknown backup."""
        engine = BackupRecoveryEngine()
        
        recovery_id = engine.create_recovery_plan("unknown_backup")
        
        assert recovery_id == ""
    
    def test_execute_recovery(self):
        """Test executing recovery."""
        engine = BackupRecoveryEngine()
        
        backup_id = engine.create_backup(backup_type=BackupType.FULL)
        recovery_id = engine.create_recovery_plan(backup_id)
        
        result = engine.execute_recovery(recovery_id)
        
        assert result is True
        assert engine._recovery_plans[recovery_id].status == RecoveryStatus.COMPLETED
        assert engine._recovery_plans[recovery_id].items_restored > 0
    
    def test_execute_unknown_recovery(self):
        """Test executing unknown recovery."""
        engine = BackupRecoveryEngine()
        
        result = engine.execute_recovery("unknown_recovery")
        
        assert result is False
    
    def test_list_backups(self):
        """Test listing backups."""
        engine = BackupRecoveryEngine()
        
        # Create multiple backups
        for i in range(5):
            engine.create_backup(backup_type=BackupType.FULL)
        
        backups = engine.list_backups(limit=10)
        
        assert len(backups) == 5
    
    def test_list_backups_filtered_by_type(self):
        """Test listing backups filtered by type."""
        engine = BackupRecoveryEngine()
        
        engine.create_backup(backup_type=BackupType.FULL)
        engine.create_backup(backup_type=BackupType.FULL)
        engine.create_backup(backup_type=BackupType.INCREMENTAL)
        engine.create_backup(backup_type=BackupType.INCREMENTAL)
        
        full_backups = engine.list_backups(backup_type=BackupType.FULL)
        incremental_backups = engine.list_backups(backup_type=BackupType.INCREMENTAL)
        
        assert len(full_backups) == 2
        assert len(incremental_backups) == 2
    
    def test_list_backups_filtered_by_status(self):
        """Test listing backups filtered by status."""
        engine = BackupRecoveryEngine()
        
        engine.create_backup(backup_type=BackupType.FULL)
        engine.create_backup(backup_type=BackupType.FULL)
        
        completed = engine.list_backups(status=BackupStatus.COMPLETED)
        failed = engine.list_backups(status=BackupStatus.FAILED)
        
        assert len(completed) == 2
        assert len(failed) == 0
    
    def test_list_backups_sorted_newest_first(self):
        """Test that backups are sorted newest first."""
        engine = BackupRecoveryEngine()
        
        # Create backups with slight delays
        for i in range(3):
            engine.create_backup(backup_type=BackupType.FULL)
        
        backups = engine.list_backups(limit=10)
        
        # Verify sorted by created_at (newest first)
        for i in range(len(backups) - 1):
            assert backups[i]["created_at"] >= backups[i + 1]["created_at"]
    
    def test_get_backup(self):
        """Test getting backup details."""
        engine = BackupRecoveryEngine()
        
        backup_id = engine.create_backup(backup_type=BackupType.FULL)
        
        backup = engine.get_backup(backup_id)
        
        assert backup is not None
        assert backup["backup_id"] == backup_id
        assert backup["backup_type"] == "full"
    
    def test_get_unknown_backup(self):
        """Test getting unknown backup."""
        engine = BackupRecoveryEngine()
        
        backup = engine.get_backup("unknown_backup")
        
        assert backup is None
    
    def test_delete_backup(self):
        """Test deleting backup."""
        engine = BackupRecoveryEngine()
        
        backup_id = engine.create_backup(backup_type=BackupType.FULL)
        
        result = engine.delete_backup(backup_id)
        
        assert result is True
        assert backup_id not in engine._manifests
    
    def test_delete_unknown_backup(self):
        """Test deleting unknown backup."""
        engine = BackupRecoveryEngine()
        
        result = engine.delete_backup("unknown_backup")
        
        assert result is False
    
    def test_cleanup_expired_backups(self):
        """Test cleaning up expired backups."""
        engine = BackupRecoveryEngine()
        
        # Create backup with short retention
        backup_id = engine.create_backup(backup_type=BackupType.FULL)
        
        # Manually set to expired
        engine._manifests[backup_id].expires_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        
        cleaned = engine.cleanup_expired_backups()
        
        assert cleaned == 1
        assert backup_id not in engine._manifests
    
    def test_get_backup_summary(self):
        """Test backup summary."""
        engine = BackupRecoveryEngine()
        
        # Create various backups
        engine.create_backup(backup_type=BackupType.FULL)
        engine.create_backup(backup_type=BackupType.FULL)
        engine.create_backup(backup_type=BackupType.INCREMENTAL)
        
        summary = engine.get_backup_summary()
        
        assert summary["total_backups"] == 3
        assert summary["completed_backups"] == 3
        assert summary["total_size_bytes"] > 0
        assert "total_size_mb" in summary
    
    def test_schedule_backup(self):
        """Test configuring backup schedule."""
        engine = BackupRecoveryEngine()
        
        engine.schedule_backup("custom", interval_days=3, retention_days=60)
        
        assert "custom" in engine._backup_schedule
        assert engine._backup_schedule["custom"]["interval_days"] == 3
        assert engine._backup_schedule["custom"]["retention_days"] == 60
    
    def test_get_next_scheduled_backup(self):
        """Test getting next scheduled backup info."""
        engine = BackupRecoveryEngine()
        
        # Create some backups
        engine.create_backup(backup_type=BackupType.FULL)
        engine.create_backup(backup_type=BackupType.INCREMENTAL)
        
        schedule = engine.get_next_scheduled_backup()
        
        assert "full" in schedule
        assert "incremental" in schedule
        assert "next_run" in schedule["full"]
        assert "interval_days" in schedule["full"]
    
    def test_backup_manifest_to_dict(self):
        """Test backup manifest serialization."""
        from copilot_core.backup.engine import BackupManifest
        
        manifest = BackupManifest(
            backup_id="backup_test",
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            created_at="2026-03-31T00:00:00Z",
            completed_at="2026-03-31T00:10:00Z",
            size_bytes=1024000,
            checksum="abc123",
            source_paths=["/config"],
            destination_path="/backups/backup_test.tar.gz",
            encrypted=True,
            compression="gzip",
            retention_days=30,
            expires_at="2026-04-30T00:00:00Z",
        )
        
        d = manifest.to_dict()
        
        assert d["backup_id"] == "backup_test"
        assert d["backup_type"] == "full"
        assert d["status"] == "completed"
        assert d["encrypted"] is True
        assert d["size_bytes"] == 1024000
    
    def test_recovery_plan_to_dict(self):
        """Test recovery plan serialization."""
        from copilot_core.backup.engine import RecoveryPlan
        
        plan = RecoveryPlan(
            recovery_id="recovery_test",
            backup_id="backup_test",
            status=RecoveryStatus.COMPLETED,
            target_paths=["/config"],
            started_at="2026-03-31T00:00:00Z",
            completed_at="2026-03-31T00:05:00Z",
            items_restored=5,
            items_failed=0,
        )
        
        d = plan.to_dict()
        
        assert d["recovery_id"] == "recovery_test"
        assert d["backup_id"] == "backup_test"
        assert d["status"] == "completed"
        assert d["items_restored"] == 5
        assert d["items_failed"] == 0
    
    def test_backup_encryption_flag(self):
        """Test backup encryption flag."""
        engine = BackupRecoveryEngine()
        
        # Create encrypted backup
        backup_id_enc = engine.create_backup(backup_type=BackupType.FULL, encrypted=True)
        
        # Create unencrypted backup
        backup_id_unenc = engine.create_backup(backup_type=BackupType.FULL, encrypted=False)
        
        assert engine._manifests[backup_id_enc].encrypted is True
        assert engine._manifests[backup_id_unenc].encrypted is False
    
    def test_backup_custom_paths(self):
        """Test backup with custom source paths."""
        engine = BackupRecoveryEngine()
        
        custom_paths = ["/custom/path/1", "/custom/path/2"]
        backup_id = engine.create_backup(
            backup_type=BackupType.FULL,
            source_paths=custom_paths,
        )
        
        manifest = engine._manifests[backup_id]
        assert manifest.source_paths == custom_paths
    
    def test_recovery_plan_custom_targets(self):
        """Test recovery plan with custom target paths."""
        engine = BackupRecoveryEngine()
        
        backup_id = engine.create_backup(backup_type=BackupType.FULL)
        
        custom_targets = ["/restore/path"]
        recovery_id = engine.create_recovery_plan(backup_id, target_paths=custom_targets)
        
        plan = engine._recovery_plans[recovery_id]
        assert plan.target_paths == custom_targets
    
    def test_backup_retention_expires_at(self):
        """Test backup expiration calculation."""
        engine = BackupRecoveryEngine()
        
        backup_id = engine.create_backup(backup_type=BackupType.FULL)
        
        manifest = engine._manifests[backup_id]
        assert manifest.expires_at is not None
        
        # Should be ~90 days in future for full backup
        expires = datetime.fromisoformat(manifest.expires_at)
        now = datetime.now(timezone.utc)
        days_until_expiry = (expires - now).days
        
        assert days_until_expiry >= 89  # ~90 days retention for full
