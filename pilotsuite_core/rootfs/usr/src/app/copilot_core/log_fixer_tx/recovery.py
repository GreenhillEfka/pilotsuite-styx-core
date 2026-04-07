"""
Recovery Manager - Handles crash recovery and in-flight transactions
"""
from typing import Dict, List, Any, Optional
from .transaction_log import TransactionLog
from .operations import create_operation, OperationError


class RecoveryReport:
    """Recovery report with details of what was recovered."""
    
    def __init__(self):
        self.in_flight_tx: List[str] = []
        self.rolled_back_tx: List[str] = []
        self.failed_tx: List[Dict[str, Any]] = []
        self.skipped_tx: List[str] = []
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "in_flight_count": len(self.in_flight_tx),
            "rolled_back_count": len(self.rolled_back_tx),
            "failed_count": len(self.failed_tx),
            "skipped_count": len(self.skipped_tx),
            "in_flight_tx": self.in_flight_tx,
            "rolled_back_tx": self.rolled_back_tx,
            "failed_tx": self.failed_tx,
            "skipped_tx": self.skipped_tx,
        }


class RecoveryManager:
    """
    Recovery Manager for crash-safety.
    
    Strategy v0.1 (simple, safe):
    - in-flight transactions → attempt rollback
    - applied transactions → leave as-is (no auto-rollback)
    """
    
    def __init__(self, transaction_log: TransactionLog):
        self.log = transaction_log
        
    def recover(self) -> RecoveryReport:
        """
        Perform recovery on startup or before new transactions.
        
        Returns:
            RecoveryReport with details
        """
        report = RecoveryReport()
        
        # Find all in-flight transactions
        in_flight = self.log.list_in_flight_tx()
        report.in_flight_tx = in_flight
        
        # Attempt rollback for each in-flight transaction
        for tx_id in in_flight:
            try:
                self._rollback_tx(tx_id)
                report.rolled_back_tx.append(tx_id)
            except Exception as e:
                report.failed_tx.append({
                    "tx_id": tx_id,
                    "error": str(e),
                })
                
        return report
        
    def _rollback_tx(self, tx_id: str) -> None:
        """
        Rollback a specific transaction.
        
        Args:
            tx_id: Transaction ID
        """
        records = self.log.get_tx_records(tx_id)
        
        # Get all INTENT records
        intent_records = [r for r in records if r.get("type") == "INTENT"]
        
        # Sort by seq in reverse order (LIFO)
        intent_records.sort(key=lambda r: r.get("seq", 0), reverse=True)
        
        # Rollback each operation
        for record in intent_records:
            seq = record.get("seq")
            op_dict = record.get("op")
            
            try:
                # Get inverse operation
                inverse_op_dict = op_dict.get("inverse")
                if not inverse_op_dict:
                    raise OperationError("No inverse operation defined")
                    
                # Create and execute inverse operation
                inverse_op = create_operation(inverse_op_dict)
                inverse_op.apply()
                
                # Log successful rollback
                self.log.append_outcome(tx_id, seq, "ROLLED_BACK")
                
            except Exception as e:
                # Log failed rollback
                error_dict = {
                    "name": type(e).__name__,
                    "message": str(e),
                }
                self.log.append_outcome(tx_id, seq, "FAILED", error=error_dict)
                raise


class TransactionManager:
    """
    High-level transaction manager.
    
    Provides convenient API for:
    - beginTx()
    - appendIntent()
    - applyTx()
    - rollbackTx()
    - recover()
    """
    
    def __init__(self, log_path: str = "/data/logs/log_fixer_tx.jsonl"):
        self.log = TransactionLog(log_path)
        self.recovery = RecoveryManager(self.log)
        
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
            meta: Optional metadata
            
        Returns:
            Transaction ID
        """
        return self.log.begin_tx(actor, reason, meta)
        
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
        Append INTENT record.
        
        Args:
            tx_id: Transaction ID
            seq: Sequence number
            actor: Actor info
            operation: Operation dict
            reason: Optional reason
            meta: Optional metadata
            
        Returns:
            Intent record
        """
        return self.log.append_intent(tx_id, seq, actor, operation, reason, meta)
        
    def apply_tx(self, tx_id: str) -> Dict[str, Any]:
        """
        Apply all operations in a transaction.
        
        Args:
            tx_id: Transaction ID
            
        Returns:
            Outcome dict
        """
        records = self.log.get_tx_records(tx_id)
        intent_records = [r for r in records if r.get("type") == "INTENT"]
        
        # Sort by seq
        intent_records.sort(key=lambda r: r.get("seq", 0))
        
        results = []
        
        for record in intent_records:
            seq = record.get("seq")
            op_dict = record.get("op")
            
            try:
                # Create and apply operation
                operation = create_operation(op_dict)
                operation.apply()
                
                # Log success
                outcome = self.log.append_outcome(tx_id, seq, "APPLIED")
                results.append({"seq": seq, "status": "APPLIED"})
                
            except Exception as e:
                # Log failure
                error_dict = {
                    "name": type(e).__name__,
                    "message": str(e),
                }
                self.log.append_outcome(tx_id, seq, "FAILED", error=error_dict)
                results.append({"seq": seq, "status": "FAILED", "error": str(e)})
                
                # Stop on first error
                break
                
        return {
            "tx_id": tx_id,
            "results": results,
            "success": all(r["status"] == "APPLIED" for r in results),
        }
        
    def rollback_tx(self, tx_id: str) -> Dict[str, Any]:
        """
        Manually rollback a transaction.
        
        Args:
            tx_id: Transaction ID
            
        Returns:
            Outcome dict
        """
        try:
            self.recovery._rollback_tx(tx_id)
            return {"tx_id": tx_id, "success": True}
        except Exception as e:
            return {"tx_id": tx_id, "success": False, "error": str(e)}
            
    def recover(self) -> RecoveryReport:
        """
        Perform recovery (on startup or manually).
        
        Returns:
            RecoveryReport
        """
        return self.recovery.recover()
        
    def list_transactions(self) -> List[Dict[str, Any]]:
        """
        List all transactions with their current state.
        
        Returns:
            List of transaction dicts
        """
        all_records = self.log.read_all_records()
        tx_ids = set(r.get("txId") for r in all_records if r.get("txId"))
        
        transactions = []
        for tx_id in sorted(tx_ids):
            state = self.log.get_tx_state(tx_id)
            records = self.log.get_tx_records(tx_id)
            
            # Get first record for metadata
            first_record = records[0] if records else {}
            
            transactions.append({
                "tx_id": tx_id,
                "state": state,
                "timestamp": first_record.get("ts"),
                "actor": first_record.get("actor"),
                "reason": first_record.get("reason"),
                "operation_count": len([r for r in records if r.get("type") == "INTENT"]),
            })
            
        return transactions
