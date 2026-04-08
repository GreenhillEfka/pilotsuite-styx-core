"""
Operations - Idempotent rename and set_enabled operations
"""
import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List


# Security: Allowed paths for rename operations
ALLOWED_RENAME_PATHS: List[str] = [
    "/config/homeassistant",
    "/config/workspace",
    "/config/www",
    "/config/custom_components",
]


def validate_rename_path(path: str) -> bool:
    """
    Validate that a path is within allowed directories.
    
    Security fix: Prevent arbitrary file operations that could lead to
    privilege escalation or data exfiltration.
    
    Args:
        path: Path to validate
        
    Returns:
        True if path is within allowed directories, False otherwise
    """
    try:
        resolved = Path(path).resolve()
        return any(str(resolved).startswith(allowed) for allowed in ALLOWED_RENAME_PATHS)
    except Exception:
        return False


class OperationError(Exception):
    """Base exception for operation errors."""
    pass


class ConflictError(OperationError):
    """Raised when a conflict is detected (e.g., both paths exist)."""
    pass


class BaseOperation:
    """Base class for all operations."""
    
    def __init__(self, target: str, before: Dict[str, Any], after: Dict[str, Any]):
        self.target = target
        self.before = before
        self.after = after
        
    def get_inverse(self) -> Dict[str, Any]:
        """Get inverse operation for rollback."""
        raise NotImplementedError
        
    def apply(self) -> None:
        """Apply the operation (idempotent)."""
        raise NotImplementedError
        
    def rollback(self) -> None:
        """Rollback the operation (idempotent)."""
        raise NotImplementedError


class RenameOperation(BaseOperation):
    """
    Rename operation - moves a file or directory.
    
    Idempotent:
    - If after.path exists and before.path doesn't → already applied
    - If before.path exists and after.path doesn't → apply rename
    - If both exist → conflict (FAIL)
    - If neither exists → FAIL (already deleted or never existed)
    """
    
    KIND = "rename"
    
    def __init__(self, target: str, before: Dict[str, Any], after: Dict[str, Any]):
        super().__init__(target, before, after)
        self.before_path = Path(before["path"])
        self.after_path = Path(after["path"])
        
    def get_inverse(self) -> Dict[str, Any]:
        """Get inverse operation."""
        return {
            "kind": self.KIND,
            "target": self.target,
            "before": {"path": str(self.after_path)},
            "after": {"path": str(self.before_path)},
        }
        
    def apply(self) -> None:
        """Apply rename operation (idempotent)."""
        # Security: Validate paths before any operation
        if not validate_rename_path(str(self.before_path)):
            raise OperationError(
                f"Security: Source path not allowed: {self.before_path}"
            )
        if not validate_rename_path(str(self.after_path)):
            raise OperationError(
                f"Security: Destination path not allowed: {self.after_path}"
            )
        
        before_exists = self.before_path.exists()
        after_exists = self.after_path.exists()
        
        if after_exists and not before_exists:
            # Already applied
            return
            
        if before_exists and not after_exists:
            # Apply rename
            self._do_rename(self.before_path, self.after_path)
            return
            
        if before_exists and after_exists:
            # Conflict - both exist
            raise ConflictError(
                f"Rename conflict: both {self.before_path} and {self.after_path} exist"
            )
            
        if not before_exists and not after_exists:
            # Neither exists
            raise OperationError(
                f"Rename failed: neither {self.before_path} nor {self.after_path} exist"
            )
            
    def rollback(self) -> None:
        """Rollback rename operation (idempotent)."""
        # Security: Validate paths before any operation
        if not validate_rename_path(str(self.before_path)):
            raise OperationError(
                f"Security: Source path not allowed: {self.before_path}"
            )
        if not validate_rename_path(str(self.after_path)):
            raise OperationError(
                f"Security: Destination path not allowed: {self.after_path}"
            )
        
        # Rollback is just inverse apply
        before_exists = self.after_path.exists()
        after_exists = self.before_path.exists()
        
        if after_exists and not before_exists:
            # Already rolled back
            return
            
        if before_exists and not after_exists:
            # Apply rollback (inverse rename)
            self._do_rename(self.after_path, self.before_path)
            return
            
        if before_exists and after_exists:
            # Conflict
            raise ConflictError(
                f"Rollback conflict: both {self.after_path} and {self.before_path} exist"
            )
            
        if not before_exists and not after_exists:
            # Neither exists
            raise OperationError(
                f"Rollback failed: neither {self.after_path} nor {self.before_path} exist"
            )
            
    def _do_rename(self, src: Path, dst: Path):
        """Perform the actual rename."""
        try:
            # Ensure parent directory exists
            dst.parent.mkdir(parents=True, exist_ok=True)
            
            # Use shutil.move for cross-filesystem support
            shutil.move(str(src), str(dst))
        except Exception as e:
            raise OperationError(f"Rename failed: {e}") from e


class SetEnabledOperation(BaseOperation):
    """
    Set enabled/disabled state operation.
    
    Two strategies:
    1. File marker: module.ext ↔ module.ext.disabled
    2. Config flag: enabled: true/false in JSON/YAML (future)
    
    v0.1 uses file marker strategy.
    
    Idempotent:
    - If current state == after.enabled → already applied
    - Otherwise → change state
    """
    
    KIND = "set_enabled"
    
    def __init__(self, target: str, before: Dict[str, Any], after: Dict[str, Any]):
        super().__init__(target, before, after)
        self.target_path = Path(target)
        self.disabled_path = Path(str(target) + ".disabled")
        self.before_enabled = before["enabled"]
        self.after_enabled = after["enabled"]
        
    def get_inverse(self) -> Dict[str, Any]:
        """Get inverse operation."""
        return {
            "kind": self.KIND,
            "target": self.target,
            "before": {"enabled": self.after_enabled},
            "after": {"enabled": self.before_enabled},
        }
        
    def _get_current_state(self) -> bool:
        """Get current enabled state."""
        # If .disabled file exists → disabled (False)
        # Otherwise → enabled (True)
        if self.disabled_path.exists():
            return False
        elif self.target_path.exists():
            return True
        else:
            raise OperationError(f"Target {self.target_path} does not exist")
            
    def apply(self) -> None:
        """Apply set_enabled operation (idempotent)."""
        try:
            current = self._get_current_state()
        except OperationError:
            # Target doesn't exist - create it if we're enabling
            if self.after_enabled:
                self.target_path.touch()
                return
            else:
                raise
                
        if current == self.after_enabled:
            # Already in desired state
            return
            
        # Change state
        if self.after_enabled:
            # Enable: rename .disabled → base
            if self.disabled_path.exists():
                shutil.move(str(self.disabled_path), str(self.target_path))
        else:
            # Disable: rename base → .disabled
            if self.target_path.exists():
                shutil.move(str(self.target_path), str(self.disabled_path))
                
    def rollback(self) -> None:
        """Rollback set_enabled operation (idempotent)."""
        try:
            current = self._get_current_state()
        except OperationError:
            # Target doesn't exist
            if self.before_enabled:
                self.target_path.touch()
                return
            else:
                raise
                
        if current == self.before_enabled:
            # Already in original state
            return
            
        # Restore original state
        if self.before_enabled:
            # Re-enable
            if self.disabled_path.exists():
                shutil.move(str(self.disabled_path), str(self.target_path))
        else:
            # Re-disable
            if self.target_path.exists():
                shutil.move(str(self.target_path), str(self.disabled_path))


def create_operation(op_dict: Dict[str, Any]) -> BaseOperation:
    """
    Factory function to create operation from dict.
    
    Args:
        op_dict: Operation dict with {kind, target, before, after}
        
    Returns:
        Operation instance
    """
    kind = op_dict["kind"]
    target = op_dict["target"]
    before = op_dict["before"]
    after = op_dict["after"]
    
    if kind == RenameOperation.KIND:
        return RenameOperation(target, before, after)
    elif kind == SetEnabledOperation.KIND:
        return SetEnabledOperation(target, before, after)
    else:
        raise ValueError(f"Unknown operation kind: {kind}")
