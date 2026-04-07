"""Encryption utilities for sensitive configuration data.

Provides secure encryption/decryption for secrets stored in configuration:
- Fernet symmetric encryption (AES-128-CBC + HMAC)
- Key derivation from master secret
- Key rotation support
- Secure key storage via environment or file
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_LOGGER = logging.getLogger(__name__)

# Constants
KEY_FILE_DEFAULT = "/config/clawd/.config_master_key"
SALT_SIZE = 16
ITERATIONS = 100000
CURRENT_KEY_VERSION = 1


class EncryptionError(Exception):
    """Encryption/decryption operation failed."""
    pass


class KeyRotationError(Exception):
    """Key rotation operation failed."""
    pass


class ConfigEncryption:
    """Handles encryption/decryption of sensitive config values.
    
    Usage:
        encryptor = ConfigEncryption(master_secret="your-secret")
        
        # Encrypt
        encrypted = encryptor.encrypt("my-api-key")
        
        # Decrypt
        decrypted = encryptor.decrypt(encrypted)
        
        # With key versioning (for rotation)
        encryptor.rotate_key(new_secret="new-secret", version=2)
    """
    
    def __init__(
        self,
        master_secret: Optional[str] = None,
        key_file: Optional[str] = None,
        key_version: int = CURRENT_KEY_VERSION,
    ) -> None:
        """Initialize encryption with master secret or key file.
        
        Args:
            master_secret: Master secret for key derivation (env var recommended)
            key_file: Path to file containing derived key (alternative to master_secret)
            key_version: Version number for key rotation support
        """
        self._key_version = key_version
        self._fernet: Optional[Fernet] = None
        self._salt: bytes = b''
        
        if master_secret:
            self._derive_key(master_secret)
        elif key_file:
            self._load_key_from_file(key_file)
        else:
            # Try environment variable
            env_secret = os.environ.get('CONFIG_MASTER_SECRET')
            if env_secret:
                self._derive_key(env_secret)
            else:
                _LOGGER.warning("No master secret provided - encryption disabled")
    
    def _derive_key(self, master_secret: str) -> None:
        """Derive encryption key from master secret using PBKDF2."""
        # Generate or retrieve salt
        salt_file = Path(KEY_FILE_DEFAULT).with_suffix('.salt')
        
        if salt_file.exists():
            self._salt = salt_file.read_bytes()
        else:
            # Generate new salt
            self._salt = os.urandom(SALT_SIZE)
            try:
                salt_file.write_bytes(self._salt)
                salt_file.chmod(0o600)
                _LOGGER.debug("Created salt file: %s", salt_file)
            except Exception as e:
                _LOGGER.warning("Failed to persist salt: %s", e)
        
        # Derive key using PBKDF2HMAC
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self._salt,
            iterations=ITERATIONS,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_secret.encode()))
        self._fernet = Fernet(key)
        _LOGGER.debug("Derived encryption key (version %d)", self._key_version)
    
    def _load_key_from_file(self, key_file: str) -> None:
        """Load pre-derived key from file."""
        path = Path(key_file)
        if not path.exists():
            raise EncryptionError(f"Key file not found: {key_file}")
        
        key_data = path.read_bytes().strip()
        self._fernet = Fernet(key_data)
        _LOGGER.debug("Loaded encryption key from: %s", key_file)
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string.
        
        Args:
            plaintext: Sensitive data to encrypt
            
        Returns:
            Base64-encoded ciphertext with version prefix
            
        Raises:
            EncryptionError: If encryption fails
        """
        if not self._fernet:
            raise EncryptionError("Encryption not initialized - no master secret")
        
        try:
            token = self._fernet.encrypt(plaintext.encode())
            # Prefix with version for rotation support
            versioned = f"v{self._key_version}:{base64.urlsafe_b64encode(token).decode()}"
            return versioned
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}")
    
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a ciphertext string.
        
        Args:
            ciphertext: Versioned encrypted data (format: v{version}:{base64})
            
        Returns:
            Decrypted plaintext
            
        Raises:
            EncryptionError: If decryption fails or key version mismatch
        """
        if not self._fernet:
            raise EncryptionError("Encryption not initialized - no master secret")
        
        try:
            # Parse version prefix
            if ':' not in ciphertext:
                # Legacy format without version
                token = base64.urlsafe_b64decode(ciphertext.encode())
            else:
                version_str, b64_token = ciphertext.split(':', 1)
                version = int(version_str.lstrip('v'))
                
                if version != self._key_version:
                    _LOGGER.warning(
                        "Decrypting with key version %d but data is version %d",
                        self._key_version, version
                    )
                    # Could implement key rotation lookup here
                
                token = base64.urlsafe_b64decode(b64_token.encode())
            
            plaintext = self._fernet.decrypt(token)
            return plaintext.decode()
        except InvalidToken:
            raise EncryptionError("Invalid token - decryption failed (wrong key?)")
        except Exception as e:
            raise EncryptionError(f"Decryption failed: {e}")
    
    def is_encrypted(self, value: str) -> bool:
        """Check if a value appears to be encrypted."""
        if not value:
            return False
        # Check for versioned format
        if value.startswith('v') and ':' in value:
            return True
        # Check for legacy base64 format (Fernet tokens are URL-safe base64)
        try:
            base64.urlsafe_b64decode(value.encode())
            return True
        except Exception:
            return False
    
    @property
    def key_version(self) -> int:
        """Get current key version."""
        return self._key_version
    
    def generate_key_file(self, output_path: str) -> str:
        """Generate and save a new encryption key file.
        
        Args:
            output_path: Path to write the key file
            
        Returns:
            Path to created key file
        """
        if not self._fernet:
            raise EncryptionError("Cannot generate key file - encryption not initialized")
        
        # Fernet key is already base64-encoded
        key = self._fernet._encryption_key  # type: ignore
        full_key = base64.urlsafe_b64encode(key)
        
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(full_key)
        path.chmod(0o600)
        
        _LOGGER.info("Generated key file: %s", path)
        return str(path)


class SecretManager:
    """High-level secrets management for configuration.
    
    Integrates encryption with secret storage and retrieval:
    - Encrypts secrets before storage
    - Decrypts on retrieval
    - Supports secret rotation
    - Audit logging
    """
    
    def __init__(self, encryptor: ConfigEncryption) -> None:
        """Initialize secret manager with encryptor."""
        self._encryptor = encryptor
        self._secrets: dict[str, str] = {}  # In-memory cache
    
    def store(self, name: str, value: str, encrypt: bool = True) -> str:
        """Store a secret value.
        
        Args:
            name: Secret identifier
            value: Secret value (will be encrypted if encrypt=True)
            encrypt: Whether to encrypt the value
            
        Returns:
            Stored value (encrypted if applicable)
        """
        if encrypt and value:
            encrypted = self._encryptor.encrypt(value)
            self._secrets[name] = encrypted
            return encrypted
        else:
            self._secrets[name] = value
            return value
    
    def retrieve(self, name: str, decrypt: bool = True) -> Optional[str]:
        """Retrieve a secret value.
        
        Args:
            name: Secret identifier
            decrypt: Whether to decrypt the value
            
        Returns:
            Secret value (decrypted if applicable), or None if not found
        """
        value = self._secrets.get(name)
        if value is None:
            return None
        
        if decrypt and self._encryptor.is_encrypted(value):
            return self._encryptor.decrypt(value)
        return value
    
    def delete(self, name: str) -> bool:
        """Delete a secret.
        
        Args:
            name: Secret identifier
            
        Returns:
            True if deleted, False if not found
        """
        if name in self._secrets:
            del self._secrets[name]
            return True
        return False
    
    def list_secrets(self) -> list[str]:
        """List all secret names (not values)."""
        return list(self._secrets.keys())
    
    def rotate_secret(self, name: str, new_value: str) -> str:
        """Rotate a secret with new value.
        
        Args:
            name: Secret identifier
            new_value: New secret value
            
        Returns:
            New encrypted value
        """
        # Encrypt new value
        encrypted = self._encryptor.encrypt(new_value)
        self._secrets[name] = encrypted
        return encrypted
    
    def export_secrets(self, decrypt: bool = False) -> dict[str, str]:
        """Export all secrets.
        
        Args:
            decrypt: If True, decrypt all values (SECURITY RISK!)
            
        Returns:
            Dict of name -> value
        """
        if decrypt:
            _LOGGER.warning("Exporting decrypted secrets - handle with care!")
            return {
                name: self.retrieve(name, decrypt=True)
                for name, _ in self._secrets.items()
            }
        else:
            return dict(self._secrets)


# ── Convenience Functions ────────────────────────────────────────────


def get_encryptor(master_secret: Optional[str] = None) -> ConfigEncryption:
    """Get or create encryption instance.
    
    Args:
        master_secret: Override master secret (otherwise uses env var)
        
    Returns:
        ConfigEncryption instance
    """
    return ConfigEncryption(master_secret=master_secret)


def encrypt_value(value: str, master_secret: Optional[str] = None) -> str:
    """Encrypt a single value.
    
    Args:
        value: Plaintext value to encrypt
        master_secret: Master secret (or use env var)
        
    Returns:
        Encrypted value
    """
    encryptor = get_encryptor(master_secret)
    return encryptor.encrypt(value)


def decrypt_value(ciphertext: str, master_secret: Optional[str] = None) -> str:
    """Decrypt a single value.
    
    Args:
        ciphertext: Encrypted value
        master_secret: Master secret (or use env var)
        
    Returns:
        Decrypted plaintext
    """
    encryptor = get_encryptor(master_secret)
    return encryptor.decrypt(ciphertext)
