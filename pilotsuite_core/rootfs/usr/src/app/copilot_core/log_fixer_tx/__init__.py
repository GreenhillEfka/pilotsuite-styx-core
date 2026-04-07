"""
log_fixer_tx v0.1 - Transaction Log für reversible rename/enable/disable

Append-only Transaction Log mit Write-Ahead Logging (WAL),
idempotenten Operationen und Crash-Recovery.
"""

from .transaction_log import TransactionLog
from .operations import RenameOperation, SetEnabledOperation
from .recovery import RecoveryManager

__all__ = [
    "TransactionLog",
    "RenameOperation",
    "SetEnabledOperation",
    "RecoveryManager",
]

__version__ = "0.1.0"
