"""Security Logging for suspicious activity detection.

Provides comprehensive logging for:
- Rate limit violations
- Malicious input attempts
- Authentication failures
- Suspicious requests
- Security events
"""

from __future__ import annotations

import os
import json
import time
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class SecurityLogger:
    """Security event logger.
    
    Logs all security-relevant events to a dedicated log file
    and the standard application log.
    """
    
    def __init__(
        self,
        log_file: Optional[str] = None,
        log_level: int = logging.INFO,
        max_log_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
    ):
        """Initialize security logger.
        
        Args:
            log_file: Path to security log file (default: security.log in app data dir)
            log_level: Logging level
            max_log_size: Maximum log file size before rotation
            backup_count: Number of backup logs to keep
        """
        self.log_level = log_level
        
        # Determine log file path
        if log_file is None:
            # Default to app data directory
            data_dir = Path("/data") if Path("/data").exists() else Path(".")
            log_file = str(data_dir / "security.log")
        
        self.log_file = log_file
        
        # Setup file handler with rotation
        self._setup_logger(max_log_size, backup_count)
    
    def _setup_logger(self, max_log_size: int, backup_count: int) -> None:
        """Setup logging handlers."""
        self._security_logger = logging.getLogger("security")
        self._security_logger.setLevel(self.log_level)
        
        # Remove existing handlers
        self._security_logger.handlers = []
        
        # File handler with rotation
        try:
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                self.log_file,
                maxBytes=max_log_size,
                backupCount=backup_count,
            )
            file_handler.setLevel(self.log_level)
            
            # Format with timestamp and details
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(event_type)s | %(client)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(formatter)
            self._security_logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Could not setup security log file: {e}")
            # Fall back to console-only logging
        
        # Also log to console
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(logging.Formatter(
            "%(asctime)s | SECURITY | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        self._security_logger.addHandler(console_handler)
    
    def _log_event(
        self,
        event_type: str,
        client: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        level: int = logging.WARNING,
    ) -> None:
        """Log a security event.
        
        Args:
            event_type: Type of security event
            client: Client identifier
            message: Event message
            details: Additional event details
            level: Logging level
        """
        # Add extra fields for structured logging
        extra = {
            "event_type": event_type,
            "client": client,
        }
        
        log_message = message
        if details:
            log_message = f"{message} | {json.dumps(details)}"
        
        self._security_logger.log(level, log_message, extra=extra)
        
        # Also log to main logger for visibility
        logger.log(level, f"[{event_type}] {client}: {message}")
    
    def log_rate_limit_exceeded(
        self,
        client: str,
        endpoint: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log rate limit violation.
        
        Args:
            client: Client identifier
            endpoint: API endpoint
            details: Additional details
        """
        self._log_event(
            event_type="RATE_LIMIT_EXCEEDED",
            client=client,
            message=f"Rate limit exceeded on {endpoint}",
            details=details or {"endpoint": endpoint},
            level=logging.WARNING,
        )
    
    def log_malicious_input(
        self,
        client: str,
        endpoint: str,
        pattern: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log malicious input detection.
        
        Args:
            client: Client identifier
            endpoint: API endpoint
            pattern: Detected malicious pattern
            details: Additional details
        """
        self._log_event(
            event_type="MALICIOUS_INPUT",
            client=client,
            message=f"Malicious input detected on {endpoint}: {pattern}",
            details=details or {"endpoint": endpoint, "pattern": pattern},
            level=logging.WARNING,
        )
    
    def log_sql_injection_attempt(
        self,
        client: str,
        endpoint: str,
        pattern: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log SQL injection attempt.
        
        Args:
            client: Client identifier
            endpoint: API endpoint
            pattern: Detected SQL injection pattern
            details: Additional details
        """
        self._log_event(
            event_type="SQL_INJECTION_ATTEMPT",
            client=client,
            message=f"SQL injection attempt on {endpoint}: {pattern}",
            details=details or {"endpoint": endpoint, "pattern": pattern},
            level=logging.CRITICAL,
        )
    
    def log_xss_attempt(
        self,
        client: str,
        endpoint: str,
        pattern: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log XSS attempt.
        
        Args:
            client: Client identifier
            endpoint: API endpoint
            pattern: Detected XSS pattern
            details: Additional details
        """
        self._log_event(
            event_type="XSS_ATTEMPT",
            client=client,
            message=f"XSS attempt on {endpoint}: {pattern}",
            details=details or {"endpoint": endpoint, "pattern": pattern},
            level=logging.CRITICAL,
        )
    
    def log_path_traversal_attempt(
        self,
        client: str,
        endpoint: str,
        pattern: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log path traversal attempt.
        
        Args:
            client: Client identifier
            endpoint: API endpoint
            pattern: Detected path traversal pattern
            details: Additional details
        """
        self._log_event(
            event_type="PATH_TRAVERSAL_ATTEMPT",
            client=client,
            message=f"Path traversal attempt on {endpoint}: {pattern}",
            details=details or {"endpoint": endpoint, "pattern": pattern},
            level=logging.CRITICAL,
        )
    
    def log_auth_failure(
        self,
        client: str,
        endpoint: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log authentication failure.
        
        Args:
            client: Client identifier
            endpoint: API endpoint
            reason: Failure reason
            details: Additional details
        """
        self._log_event(
            event_type="AUTH_FAILURE",
            client=client,
            message=f"Authentication failure on {endpoint}: {reason}",
            details=details or {"endpoint": endpoint, "reason": reason},
            level=logging.WARNING,
        )
    
    def log_auth_success(
        self,
        client: str,
        endpoint: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log successful authentication.
        
        Args:
            client: Client identifier
            endpoint: API endpoint
            details: Additional details
        """
        self._log_event(
            event_type="AUTH_SUCCESS",
            client=client,
            message=f"Successful authentication on {endpoint}",
            details=details or {"endpoint": endpoint},
            level=logging.INFO,
        )
    
    def log_request_size_exceeded(
        self,
        client: str,
        endpoint: str,
        size: int,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log request size limit exceeded.
        
        Args:
            client: Client identifier
            endpoint: API endpoint
            size: Request size in bytes
            details: Additional details
        """
        self._log_event(
            event_type="REQUEST_SIZE_EXCEEDED",
            client=client,
            message=f"Request size exceeded on {endpoint}: {size} bytes",
            details=details or {"endpoint": endpoint, "size": size},
            level=logging.WARNING,
        )
    
    def log_suspicious_request(
        self,
        client: str,
        endpoint: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log suspicious request.
        
        Args:
            client: Client identifier
            endpoint: API endpoint
            reason: Reason for suspicion
            details: Additional details
        """
        self._log_event(
            event_type="SUSPICIOUS_REQUEST",
            client=client,
            message=f"Suspicious request on {endpoint}: {reason}",
            details=details or {"endpoint": endpoint, "reason": reason},
            level=logging.WARNING,
        )
    
    def log_token_rotation(
        self,
        client: str,
        old_token_prefix: str,
        new_token_prefix: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log token rotation event.
        
        Args:
            client: Client identifier
            old_token_prefix: First 8 chars of old token
            new_token_prefix: First 8 chars of new token
            details: Additional details
        """
        self._log_event(
            event_type="TOKEN_ROTATION",
            client=client,
            message=f"Token rotated: {old_token_prefix}... -> {new_token_prefix}...",
            details=details or {
                "old_token_prefix": old_token_prefix,
                "new_token_prefix": new_token_prefix,
            },
            level=logging.INFO,
        )
    
    def log_security_event(
        self,
        event_type: str,
        client: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        level: int = logging.INFO,
    ) -> None:
        """Log a custom security event.
        
        Args:
            event_type: Custom event type
            client: Client identifier
            message: Event message
            details: Additional details
            level: Logging level
        """
        self._log_event(
            event_type=event_type,
            client=client,
            message=message,
            details=details,
            level=level,
        )
    
    def get_recent_events(
        self,
        limit: int = 100,
        event_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent security events from log file.
        
        Args:
            limit: Maximum number of events to return
            event_type: Filter by event type
            
        Returns:
            List of recent events
        """
        events = []
        
        try:
            if not Path(self.log_file).exists():
                return events
            
            with open(self.log_file, "r") as f:
                lines = f.readlines()
                
            for line in reversed(lines[-limit:]):
                if event_type and event_type not in line:
                    continue
                
                # Parse log line (simplified)
                events.append({
                    "raw": line.strip(),
                    "timestamp": datetime.now().isoformat(),
                })
        except Exception as e:
            logger.error(f"Error reading security log: {e}")
        
        return events


# Global security logger instance
_security_logger: Optional[SecurityLogger] = None


def get_security_logger() -> SecurityLogger:
    """Get the global security logger instance."""
    global _security_logger
    if _security_logger is None:
        log_file = os.environ.get("COPILOT_SECURITY_LOG", None)
        log_level = getattr(
            logging,
            os.environ.get("COPILOT_SECURITY_LOG_LEVEL", "INFO").upper(),
            logging.INFO,
        )
        _security_logger = SecurityLogger(log_file=log_file, log_level=log_level)
    return _security_logger
