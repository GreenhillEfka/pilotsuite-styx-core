"""Security Hardening — Additional security utilities for PilotSuite Core."""
from __future__ import annotations

import logging
import secrets
import hashlib
import hmac
from typing import Optional, Dict, Any
from dataclasses import dataclass
import time
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os

logger = logging.getLogger(__name__)


# =============================================================================
# SECURE TOKEN GENERATION
# =============================================================================

class SecureTokenGenerator:
    """Cryptographically secure token generator."""

    def __init__(self, token_length: int = 32):
        """
        Initialize token generator.
        
        Args:
            token_length: Length of token in bytes (default 32 = 256 bits)
        """
        self._token_length = token_length

    def generate(self, prefix: Optional[str] = None) -> str:
        """
        Generate secure random token.
        
        Args:
            prefix: Optional prefix for token (e.g., "sk_", "pk_")
        
        Returns:
            Secure random token (URL-safe base64)
        """
        random_bytes = secrets.token_bytes(self._token_length)
        token = base64.urlsafe_b64encode(random_bytes).decode('ascii')
        
        if prefix:
            token = f"{prefix}{token}"
        
        return token

    def generate_api_key(self) -> str:
        """Generate API key with prefix."""
        return self.generate("sk_")

    def generate_public_key(self) -> str:
        """Generate public key with prefix."""
        return self.generate("pk_")

    def verify_token(self, token: str, expected_prefix: Optional[str] = None) -> bool:
        """Verify token format."""
        if expected_prefix and not token.startswith(expected_prefix):
            return False
        
        # Check minimum length
        token_part = token[len(expected_prefix):] if expected_prefix else token
        return len(token_part) >= 44  # 32 bytes base64 encoded


# =============================================================================
# PASSWORD HASHING
# =============================================================================

class PasswordHasher:
    """Secure password hashing with PBKDF2."""

    def __init__(self, iterations: int = 100000):
        """
        Initialize password hasher.
        
        Args:
            iterations: PBKDF2 iterations (default 100k for OWASP compliance)
        """
        self._iterations = iterations

    def hash(self, password: str, salt: Optional[bytes] = None) -> Dict[str, str]:
        """
        Hash password with salt.
        
        Args:
            password: Plain text password
            salt: Optional salt (generated if not provided)
        
        Returns:
            Dict with salt and hash (both base64 encoded)
        """
        if salt is None:
            salt = os.urandom(16)
        
        # Derive key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self._iterations,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        
        return {
            "salt": base64.urlsafe_b64encode(salt).decode('ascii'),
            "hash": key.decode('ascii'),
            "iterations": self._iterations,
        }

    def verify(self, password: str, salt_b64: str, hash_b64: str) -> bool:
        """
        Verify password against hash.
        
        Args:
            password: Plain text password to verify
            salt_b64: Salt (base64 encoded)
            hash_b64: Expected hash (base64 encoded)
        
        Returns:
            True if password matches
        """
        salt = base64.urlsafe_b64decode(salt_b64.encode())
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self._iterations,
        )
        
        try:
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            return hmac.compare_digest(key, hash_b64.encode())
        except Exception:
            return False


# =============================================================================
# ENCRYPTION AT REST
# =============================================================================

class EncryptionAtRest:
    """Encrypt sensitive data at rest using Fernet (symmetric encryption)."""

    def __init__(self, key: Optional[bytes] = None):
        """
        Initialize encryption.
        
        Args:
            key: Encryption key (32 bytes, generated if not provided)
        """
        if key is None:
            key = Fernet.generate_key()
        
        self._fernet = Fernet(key)
        self._key_hash = hashlib.sha256(key).hexdigest()[:16]

    def encrypt(self, data: bytes) -> bytes:
        """Encrypt data."""
        return self._fernet.encrypt(data)

    def decrypt(self, encrypted_data: bytes) -> bytes:
        """Decrypt data."""
        return self._fernet.decrypt(encrypted_data)

    def encrypt_json(self, data: Dict[str, Any]) -> str:
        """Encrypt JSON data."""
        import json
        json_bytes = json.dumps(data).encode('utf-8')
        encrypted = self.encrypt(json_bytes)
        return base64.urlsafe_b64encode(encrypted).decode('ascii')

    def decrypt_json(self, encrypted_data: str) -> Dict[str, Any]:
        """Decrypt JSON data."""
        import json
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode('ascii'))
        decrypted = self.decrypt(encrypted_bytes)
        return json.loads(decrypted.decode('utf-8'))

    def get_key_hash(self) -> str:
        """Get key hash for verification."""
        return self._key_hash


# =============================================================================
# API KEY STORAGE (ENCRYPTED)
# =============================================================================

@dataclass
class APIKeyRecord:
    """API key record."""
    key_hash: str  # Hashed key for comparison
    encrypted_key: str  # Encrypted original key
    scope: str
    created_at: float
    expires_at: Optional[float]
    last_used: Optional[float] = None
    usage_count: int = 0


class APIKeyStore:
    """Secure API key storage with encryption."""

    def __init__(self, encryption_key: bytes):
        """
        Initialize API key store.
        
        Args:
            encryption_key: Key for encrypting stored API keys
        """
        self._encryption = EncryptionAtRest(encryption_key)
        self._keys: Dict[str, APIKeyRecord] = {}  # key_hash -> record

    def add_key(
        self,
        api_key: str,
        scope: str = "read",
        expires_in_hours: Optional[int] = None,
    ) -> str:
        """
        Add API key to store.
        
        Args:
            api_key: Plain text API key
            scope: Key scope (read, write, admin)
            expires_in_hours: Optional expiration
        
        Returns:
            Key hash (for reference)
        """
        # Hash key for lookup
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Encrypt key for storage
        encrypted_key = self._encryption.encrypt_json({
            "key": api_key,
            "scope": scope,
        })
        
        # Create record
        now = time.time()
        record = APIKeyRecord(
            key_hash=key_hash,
            encrypted_key=encrypted_key,
            scope=scope,
            created_at=now,
            expires_at=now + (expires_in_hours * 3600) if expires_in_hours else None,
        )
        
        self._keys[key_hash] = record
        logger.info(f"API key added: {key_hash[:8]}... (scope: {scope})")
        
        return key_hash

    def verify_key(self, api_key: str) -> Optional[Dict]:
        """
        Verify API key and return metadata.
        
        Args:
            api_key: Plain text API key
        
        Returns:
            Key metadata if valid, None otherwise
        """
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        if key_hash not in self._keys:
            return None
        
        record = self._keys[key_hash]
        
        # Check expiration
        if record.expires_at and time.time() > record.expires_at:
            logger.warning(f"API key expired: {key_hash[:8]}...")
            return None
        
        # Update last used
        record.last_used = time.time()
        record.usage_count += 1
        
        return {
            "scope": record.scope,
            "created_at": record.created_at,
            "expires_at": record.expires_at,
            "last_used": record.last_used,
            "usage_count": record.usage_count,
        }

    def revoke_key(self, api_key: str) -> bool:
        """
        Revoke API key.
        
        Args:
            api_key: Plain text API key
        
        Returns:
            True if revoked, False if not found
        """
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        if key_hash in self._keys:
            del self._keys[key_hash]
            logger.info(f"API key revoked: {key_hash[:8]}...")
            return True
        
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Get API key store statistics."""
        now = time.time()
        active = sum(1 for r in self._keys.values() if not r.expires_at or r.expires_at > now)
        expired = len(self._keys) - active
        
        return {
            "total_keys": len(self._keys),
            "active_keys": active,
            "expired_keys": expired,
            "total_usage": sum(r.usage_count for r in self._keys.values()),
        }


# =============================================================================
# SECURITY UTILITIES
# =============================================================================

class SecurityUtils:
    """General security utilities."""

    @staticmethod
    def constant_time_compare(a: str, b: str) -> bool:
        """Constant-time string comparison to prevent timing attacks."""
        return hmac.compare_digest(a.encode(), b.encode())

    @staticmethod
    def sanitize_input(text: str, max_length: int = 10000) -> str:
        """Sanitize user input."""
        if not text:
            return ""
        
        # Truncate
        text = text[:max_length]
        
        # Remove null bytes
        text = text.replace('\x00', '')
        
        return text

    @staticmethod
    def validate_api_key_format(api_key: str) -> bool:
        """Validate API key format."""
        if not api_key:
            return False
        
        # Check minimum length
        if len(api_key) < 32:
            return False
        
        # Check for prefix
        if not api_key.startswith(("sk_", "pk_", "api_")):
            logger.warning("API key missing standard prefix")
        
        return True

    @staticmethod
    def get_security_headers() -> Dict[str, str]:
        """Get recommended security headers."""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }


# =============================================================================
# GLOBAL INSTANCES
# =============================================================================

_default_token_generator: Optional[SecureTokenGenerator] = None
_default_password_hasher: Optional[PasswordHasher] = None
_default_api_key_store: Optional[APIKeyStore] = None


def init_security(encryption_key: Optional[bytes] = None) -> Dict[str, Any]:
    """Initialize security components."""
    global _default_token_generator, _default_password_hasher, _default_api_key_store
    
    _default_token_generator = SecureTokenGenerator(token_length=32)
    _default_password_hasher = PasswordHasher(iterations=100000)
    
    if encryption_key is None:
        encryption_key = os.urandom(32)
    
    _default_api_key_store = APIKeyStore(encryption_key)
    
    logger.info("Security components initialized")
    
    return {
        "token_generator": _default_token_generator,
        "password_hasher": _default_password_hasher,
        "api_key_store": _default_api_key_store,
        "encryption_key_hash": hashlib.sha256(encryption_key).hexdigest()[:16],
    }


def get_token_generator() -> SecureTokenGenerator:
    """Get default token generator."""
    global _default_token_generator
    if not _default_token_generator:
        _default_token_generator = SecureTokenGenerator()
    return _default_token_generator


def get_api_key_store() -> APIKeyStore:
    """Get default API key store."""
    global _default_api_key_store
    if not _default_api_key_store:
        raise RuntimeError("Security not initialized. Call init_security() first.")
    return _default_api_key_store
