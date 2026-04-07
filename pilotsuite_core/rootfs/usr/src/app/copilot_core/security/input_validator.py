"""Input Validation for API endpoints.

Provides comprehensive input validation including:
- SQL Injection detection
- XSS (Cross-Site Scripting) prevention
- Path Traversal protection
- Request size limiting
- Input sanitization
"""

from __future__ import annotations

import re
import os
import logging
import html
from typing import Any, Dict, List, Optional, Tuple, Union
from functools import wraps

from flask import request, jsonify, g

logger = logging.getLogger(__name__)


class InputValidator:
    """Comprehensive input validator for API requests.
    
    Features:
    - SQL Injection detection
    - XSS prevention
    - Path Traversal protection
    - Request size validation (1MB max)
    - Input sanitization
    """
    
    # SQL Injection patterns
    SQL_INJECTION_PATTERNS = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|TRUNCATE)\b)",
        r"(--|#|/\*)",  # SQL comments
        r"(\bOR\b\s+\d+\s*=\s*\d+)",  # OR 1=1
        r"(\bAND\b\s+\d+\s*=\s*\d+)",  # AND 1=1
        r"(\bOR\b\s+['\"]?\w+['\"]?\s*=\s*['\"]?\w+['\"]?)",  # OR 'a'='a'
        r"(;\s*(SELECT|INSERT|UPDATE|DELETE|DROP))",  # Stacked queries
        r"(\bEXEC(UTE)?\b\s*\()",  # EXEC/EXECUTE
        r"(\bWAITFOR\b\s+\bDELAY\b)",  # Time-based injection
        r"(\bBENCHMARK\b\s*\()",  # MySQL benchmark
        r"(\bSLEEP\b\s*\()",  # Sleep function
        r"(\bLOAD_FILE\b\s*\()",  # File read
        r"(\bINTO\s+\bOUTFILE\b)",  # File write
        r"(\bINFORMATION_SCHEMA\b)",  # Schema access
    ]
    
    # XSS patterns
    XSS_PATTERNS = [
        r"<script[^>]*>",  # Script tags
        r"javascript:",  # JavaScript protocol
        r"on\w+\s*=",  # Event handlers (onclick, onerror, etc.)
        r"<iframe[^>]*>",  # iframe tags
        r"<object[^>]*>",  # object tags
        r"<embed[^>]*>",  # embed tags
        r"<svg[^>]*on\w+\s*=",  # SVG with event handlers
        r"<img[^>]*on\w+\s*=",  # img with event handlers
        r"expression\s*\(",  # CSS expression
        r"url\s*\(\s*['\"]?javascript:",  # CSS JavaScript URL
        r"<\s*/?\s*script",  # Script tags (simplified)
        r"<\s*/?\s*iframe",  # iframe tags (simplified)
        r"<\s*/?\s*object",  # object tags (simplified)
        r"<\s*/?\s*embed",  # embed tags (simplified)
        r"<\s*/?\s*form",  # form tags (simplified)
    ]
    
    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",  # Basic parent directory
        r"\.\.\\",  # Windows parent directory
        r"%2e%2e%2f",  # URL encoded ../
        r"%2e%2e/",  # Partial URL encoding
        r"\.\.%2f",  # Partial URL encoding
        r"%252e%252e%252f",  # Double URL encoding
        r"\.\.%5c",  # Mixed encoding
        r"/etc/passwd",  # Unix password file
        r"/etc/shadow",  # Unix shadow file
        r"c:\\windows",  # Windows directory
        r"c:/windows",  # Windows directory (forward slash)
    ]
    
    # Compiled regex patterns for performance
    _sql_patterns_compiled: List[re.Pattern] = []
    _xss_patterns_compiled: List[re.Pattern] = []
    _path_patterns_compiled: List[re.Pattern] = []
    
    def __init__(
        self,
        max_request_size: int = 1024 * 1024,  # 1MB
        max_field_length: int = 10000,
        max_array_length: int = 1000,
        check_sql_injection: bool = True,
        check_xss: bool = True,
        check_path_traversal: bool = True,
    ):
        """Initialize input validator.
        
        Args:
            max_request_size: Maximum request body size in bytes (default 1MB)
            max_field_length: Maximum length for individual string fields
            max_array_length: Maximum number of items in arrays
            check_sql_injection: Enable SQL injection detection
            check_xss: Enable XSS detection
            check_path_traversal: Enable path traversal detection
        """
        self.max_request_size = max_request_size
        self.max_field_length = max_field_length
        self.max_array_length = max_array_length
        self.check_sql_injection = check_sql_injection
        self.check_xss = check_xss
        self.check_path_traversal = check_path_traversal
        
        # Compile patterns if not already done
        if not self._sql_patterns_compiled:
            self._sql_patterns_compiled = [
                re.compile(pattern, re.IGNORECASE)
                for pattern in self.SQL_INJECTION_PATTERNS
            ]
        if not self._xss_patterns_compiled:
            self._xss_patterns_compiled = [
                re.compile(pattern, re.IGNORECASE)
                for pattern in self.XSS_PATTERNS
            ]
        if not self._path_patterns_compiled:
            self._path_patterns_compiled = [
                re.compile(pattern, re.IGNORECASE)
                for pattern in self.PATH_TRAVERSAL_PATTERNS
            ]
    
    def validate_request_size(self) -> Tuple[bool, Optional[str]]:
        """Validate request size.
        
        Returns:
            Tuple of (valid: bool, error_message: str or None)
        """
        try:
            content_length = request.content_length
            if content_length and content_length > self.max_request_size:
                return False, f"Request too large (max {self.max_request_size // 1024}KB)"
            return True, None
        except (AttributeError, RuntimeError):
            # Outside request context or content_length not available
            return True, None
    
    def _check_sql_injection_pattern(self, value: str) -> Tuple[bool, Optional[str]]:
        """Check for SQL injection patterns.
        
        Args:
            value: String value to check
            
        Returns:
            Tuple of (safe: bool, pattern_matched: str or None)
        """
        if not self.check_sql_injection:
            return True, None
        
        for pattern in self._sql_patterns_compiled:
            if pattern.search(value):
                logger.warning(f"SQL injection pattern detected: {pattern.pattern[:50]}")
                return False, pattern.pattern[:50]
        
        return True, None
    
    def _check_xss_pattern(self, value: str) -> Tuple[bool, Optional[str]]:
        """Check for XSS patterns.
        
        Args:
            value: String value to check
            
        Returns:
            Tuple of (safe: bool, pattern_matched: str or None)
        """
        if not self.check_xss:
            return True, None
        
        for pattern in self._xss_patterns_compiled:
            if pattern.search(value):
                logger.warning(f"XSS pattern detected: {pattern.pattern[:50]}")
                return False, pattern.pattern[:50]
        
        return True, None
    
    def _check_path_traversal_pattern(self, value: str) -> Tuple[bool, Optional[str]]:
        """Check for path traversal patterns.
        
        Args:
            value: String value to check
            
        Returns:
            Tuple of (safe: bool, pattern_matched: str or None)
        """
        if not self.check_path_traversal:
            return True, None
        
        for pattern in self._path_patterns_compiled:
            if pattern.search(value):
                logger.warning(f"Path traversal pattern detected: {pattern.pattern[:50]}")
                return False, pattern.pattern[:50]
        
        return True, None
    
    def validate_string(
        self,
        value: str,
        field_name: str = "input",
        checks: Optional[List[str]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Validate a string value.
        
        Args:
            value: String to validate
            field_name: Name of the field (for error messages)
            checks: List of checks to perform (sql, xss, path, length)
            
        Returns:
            Tuple of (valid: bool, error_message: str or None)
        """
        if checks is None:
            checks = ["sql", "xss", "path", "length"]
        
        # Check length
        if "length" in checks and len(value) > self.max_field_length:
            return False, f"Field '{field_name}' exceeds maximum length ({self.max_field_length})"
        
        # Check SQL injection
        if "sql" in checks and self.check_sql_injection:
            safe, pattern = self._check_sql_injection_pattern(value)
            if not safe:
                return False, f"Potentially dangerous SQL pattern detected in '{field_name}'"
        
        # Check XSS
        if "xss" in checks and self.check_xss:
            safe, pattern = self._check_xss_pattern(value)
            if not safe:
                return False, f"Potentially dangerous XSS pattern detected in '{field_name}'"
        
        # Check path traversal
        if "path" in checks and self.check_path_traversal:
            safe, pattern = self._check_path_traversal_pattern(value)
            if not safe:
                return False, f"Potentially dangerous path traversal pattern detected in '{field_name}'"
        
        return True, None
    
    def validate_dict(
        self,
        data: Dict[str, Any],
        checks: Optional[List[str]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Validate all string values in a dictionary.
        
        Args:
            data: Dictionary to validate
            checks: List of checks to perform
            
        Returns:
            Tuple of (valid: bool, error_message: str or None)
        """
        if not isinstance(data, dict):
            return False, "Input must be a dictionary"
        
        for key, value in data.items():
            if isinstance(value, str):
                valid, error = self.validate_string(value, key, checks)
                if not valid:
                    return False, error
            elif isinstance(value, dict):
                valid, error = self.validate_dict(value, checks)
                if not valid:
                    return False, error
            elif isinstance(value, list):
                if len(value) > self.max_array_length:
                    return False, f"Array '{key}' exceeds maximum length ({self.max_array_length})"
                for item in value:
                    if isinstance(item, str):
                        valid, error = self.validate_string(f"{key}[]", checks=checks)
                        if not valid:
                            return False, error
        
        return True, None
    
    def sanitize_string(self, value: str) -> str:
        """Sanitize a string by escaping dangerous characters.
        
        Args:
            value: String to sanitize
            
        Returns:
            Sanitized string
        """
        if not value:
            return value
        
        # HTML escape to prevent XSS
        sanitized = html.escape(value, quote=True)
        
        # Remove null bytes
        sanitized = sanitized.replace("\x00", "")
        
        return sanitized
    
    def sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize all string values in a dictionary.
        
        Args:
            data: Dictionary to sanitize
            
        Returns:
            Sanitized dictionary
        """
        if not isinstance(data, dict):
            return data
        
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.sanitize_string(value)
            elif isinstance(value, dict):
                result[key] = self.sanitize_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    self.sanitize_string(item) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                result[key] = value
        
        return result


# Global validator instance
_validator: Optional[InputValidator] = None


def get_validator() -> InputValidator:
    """Get the global input validator instance."""
    global _validator
    if _validator is None:
        max_size = int(os.environ.get("COPILOT_MAX_REQUEST_SIZE", 1024 * 1024))
        _validator = InputValidator(max_request_size=max_size)
    return _validator


def validate_input(
    checks: Optional[List[str]] = None,
    skip_sanitization: bool = False,
):
    """Decorator to validate input for an endpoint.
    
    Args:
        checks: List of checks to perform (sql, xss, path, length, size)
        skip_sanitization: Skip automatic sanitization
        
    Returns:
        Decorator function
        
    Example:
        @bp.post("/users")
        @validate_input(checks=["sql", "xss"])
        def create_user(data):
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            validator = get_validator()
            
            # Check request size
            if "size" in (checks or ["size"]):
                valid, error = validator.validate_request_size()
                if not valid:
                    from .security_logs import get_security_logger
                    sec_logger = get_security_logger()
                    sec_logger.log_request_size_exceeded(
                        validator.get_client_key(),
                        request.path,
                        request.content_length or 0,
                    )
                    return jsonify({
                        "ok": False,
                        "error": "request_too_large",
                        "message": error,
                    }), 413
            
            # Validate JSON body
            try:
                data = request.get_json(silent=True)
                if data:
                    check_list = checks or ["sql", "xss", "path", "length"]
                    valid, error = validator.validate_dict(data, checks=check_list)
                    if not valid:
                        from .security_logs import get_security_logger
                        sec_logger = get_security_logger()
                        sec_logger.log_malicious_input(
                            validator.get_client_key(),
                            request.path,
                            error,
                        )
                        return jsonify({
                            "ok": False,
                            "error": "invalid_input",
                            "message": error,
                        }), 400
                    
                    # Sanitize and store in Flask g object
                    if not skip_sanitization:
                        g.sanitized_data = validator.sanitize_dict(data)
                    else:
                        g.sanitized_data = data
            except Exception as e:
                logger.error(f"Input validation error: {e}")
                return jsonify({
                    "ok": False,
                    "error": "validation_error",
                    "message": "Failed to validate input",
                }), 400
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def sanitize_input(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize input data.
    
    Args:
        data: Dictionary to sanitize
        
    Returns:
        Sanitized dictionary
    """
    validator = get_validator()
    return validator.sanitize_dict(data)


# Helper methods for InputValidator
def _get_client_key(self) -> str:
    """Extract client key from current request."""
    try:
        api_key = request.headers.get("X-API-Key", "").strip()
        if api_key:
            return f"apikey:{api_key[:16]}"
        
        auth_token = request.headers.get("X-Auth-Token", "").strip()
        if auth_token:
            return f"token:{auth_token[:16]}"
        
        auth_header = request.headers.get("Authorization", "").strip()
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            if token:
                return f"bearer:{token[:16]}"
        
        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
        return f"ip:{client_ip}"
    except RuntimeError:
        return "unknown"


# Add helper method to InputValidator class
InputValidator.get_client_key = _get_client_key
