"""Secure Data Transfer — encrypted bulk transfer layer for Multi-Home Sync.

Handles large configuration snapshots and entity state maps with:
- AES-256-GCM encryption of payload bodies
- Streaming upload/download for large datasets
- Integrity verification via SHA-256 checksums
- Chunked transfer for payloads > 1 MB
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import struct
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Iterator, Optional

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


# AES-GCM helpers — uses Python's built-in cryptography module (or fallback)
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _HAS_AESGCM = True
except ImportError:
    _HAS_AESGCM = False


class TransferError(Exception):
    """Raised on transfer failures."""


# -----------------------------------------------------------------------------


@dataclass
class TransferChunk:
    """Single chunk of a chunked transfer."""
    index: int
    total: int
    data_b64: str
    checksum: str  # SHA-256 of raw bytes


@dataclass
class TransferManifest:
    """Metadata header for a multi-chunk transfer."""
    transfer_id: str
    total_bytes: int
    total_chunks: int
    checksum: str  # SHA-256 of all raw bytes concatenated
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TransferResult:
    """Outcome of a send or receive operation."""
    ok: bool
    transfer_id: str
    bytes_transferred: int
    duration_ms: float
    error: Optional[str] = None
    manifest: Optional[TransferManifest] = None


# -----------------------------------------------------------------------------


class EncryptedPayload:
    """AES-256-GCM encrypted blob with IV prepended.

    Format: [12-byte IV][ciphertext][16-byte auth tag]
    """

    NONCE_SIZE = 12
    KEY_SIZE = 32  # AES-256

    def __init__(self, key: Optional[bytes] = None):
        if key is None:
            key = secrets.token_bytes(self.KEY_SIZE)
        if len(key) != self.KEY_SIZE:
            raise ValueError(f"Key must be {self.KEY_SIZE} bytes")
        self._key = key
        if _HAS_AESGCM:
            self._aesgcm = AESGCM(key)
        else:
            self._aesgcm = None
            logger.warning("AESGCM not available; encryption disabled")

    @property
    def key_b64(self) -> str:
        """Export key as base64 (used for key exchange between homes)."""
        return base64.b64encode(self._key).decode()

    @staticmethod
    def from_key_b64(key_b64: str) "EncryptedPayload":
        return EncryptedPayload(base64.b64decode(key_b64))

    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt plaintext. Returns raw bytes (IV + ciphertext + tag)."""
        if self._aesgcm is None:
            return plaintext  # Fallback: no encryption
        nonce = secrets.token_bytes(EncryptedPayload.NONCE_SIZE)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, None)
        return nonce + ciphertext

    def decrypt(self, data: bytes) -> bytes:
        """Decrypt IV-prefixed blob back to plaintext."""
        if self._aesgcm is None:
            return data
        if len(data) < EncryptedPayload.NONCE_SIZE + 16:
            raise TransferError("Ciphertext too short")
        nonce = data[: EncryptedPayload.NONCE_SIZE]
        ciphertext = data[EncryptedPayload.NONCE_SIZE :]
        return self._aesgcm.decrypt(nonce, ciphertext, None)

    def encrypt_dict(self, d: dict[str, Any]) -> str:
        """Encrypt a JSON-serializable dict. Returns base64 string."""
        plaintext = json.dumps(d, default=str).encode()
        return base64.b64encode(self.encrypt(plaintext)).decode()

    def decrypt_dict(self, data_b64: str) -> dict[str, Any]:
        """Decrypt base64 string back to dict."""
        raw = base64.b64decode(data_b64)
        plaintext = self.decrypt(raw)
        return json.loads(plaintext.decode())


# -----------------------------------------------------------------------------


class SecureTransfer:
    """Handles encrypted, chunked data transfer between homes.

    Small payloads (< 1 MB) are sent in a single chunk.
    Larger payloads are split into 512 KB chunks, each with its own
    SHA-256 checksum and assembled on the receiving side.
    """

    CHUNK_SIZE = 512 * 1024  # 512 KB
    DEFAULT_TRANSFER_DIR = "/data/multihome/transfers"

    def __init__(
        self,
        shared_secret: str,
        transfer_dir: str = DEFAULT_TRANSFER_DIR,
    ):
        self._shared_secret = shared_secret.encode()
        self._transfer_dir = Path(transfer_dir)
        self._transfer_dir.mkdir(parents=True, exist_ok=True)
        # Derive the AES key from the shared secret (HKDF-lite)
        self._aes_key = hashlib.sha256(self._shared_secret).digest()
        self._cipher = EncryptedPayload(self._aes_key)

    # -------------------------------------------------------------------------
    # High-level send / receive
    # -------------------------------------------------------------------------

    def send_dict(
        self,
        data: dict[str, Any],
        transfer_id: Optional[str] = None,
    ) -> tuple[str, str]:
        """Encrypt and prepare a dict for transfer.

        Returns (transfer_id, encrypted_b64).
        """
        transfer_id = transfer_id or secrets.token_hex(16)
        payload_b64 = self._cipher.encrypt_dict(data)
        return transfer_id, payload_b64

    def receive_dict(self, transfer_id: str, encrypted_b64: str) -> dict[str, Any]:
        """Decrypt a transfer payload back to a dict."""
        return self._cipher.decrypt_dict(encrypted_b64)

    def create_chunks(
        self,
        raw_bytes: bytes,
        transfer_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> tuple[TransferManifest, list[TransferChunk]]:
        """Split large data into integrity-checked chunks.

        Returns (manifest, list of chunks).
        """
        transfer_id = transfer_id or secrets.token_hex(16)
        total = len(raw_bytes)
        total_chunks = (total + self.CHUNK_SIZE - 1) // self.CHUNK_SIZE
        full_checksum = hashlib.sha256(raw_bytes).hexdigest()

        manifest = TransferManifest(
            transfer_id=transfer_id,
            total_bytes=total,
            total_chunks=total_chunks,
            checksum=full_checksum,
            created_at=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
        )

        chunks = []
        for i in range(total_chunks):
            start = i * self.CHUNK_SIZE
            chunk_bytes = raw_bytes[start : start + self.CHUNK_SIZE]
            chunk = TransferChunk(
                index=i,
                total=total_chunks,
                data_b64=base64.b64encode(chunk_bytes).decode(),
                checksum=hashlib.sha256(chunk_bytes).hexdigest(),
            )
            chunks.append(chunk)

        return manifest, chunks

    def assemble_chunks(
        self,
        manifest: TransferManifest,
        chunks: list[TransferChunk],
    ) -> bytes:
        """Reassemble chunks into original bytes, verifying integrity."""
        if len(chunks) != manifest.total_chunks:
            raise TransferError(
                f"Chunk count mismatch: expected {manifest.total_chunks}, got {len(chunks)}"
            )

        # Sort by index just in case
        sorted_chunks = sorted(chunks, key=lambda c: c.index)
        raw_parts = []
        for chunk in sorted_chunks:
            if chunk.checksum != hashlib.sha256(base64.b64decode(chunk.data_b64)).hexdigest():
                raise TransferError(f"Checksum mismatch on chunk {chunk.index}")
            raw_parts.append(base64.b64decode(chunk.data_b64))

        assembled = b"".join(raw_parts)
        if hashlib.sha256(assembled).hexdigest() != manifest.checksum:
            raise TransferError("Transfer manifest checksum mismatch")

        return assembled

    # -------------------------------------------------------------------------
    # Streaming helpers (for very large transfers)
    # -------------------------------------------------------------------------

    def stream_encrypt(self, fh: BinaryIO, chunk_size: int = CHUNK_SIZE) -> Iterator[bytes]:
        """Yield encrypted chunks from a binary file handle.

        Each yielded item is a `TransferChunk`-compatible dict with
        (index, total, data_b64, checksum) — suitable for JSON serialization.
        """
        index = 0
        while True:
            block = fh.read(chunk_size)
            if not block:
                break
            encrypted = self._cipher.encrypt(block)
            yield {
                "index": index,
                "data_b64": base64.b64encode(encrypted).decode(),
                "checksum": hashlib.sha256(block).hexdigest(),
            }
            index += 1

    def verify_payload_integrity(self, raw_bytes: bytes, expected_checksum: str) -> bool:
        """Verify SHA-256 checksum of received data."""
        return hashlib.sha256(raw_bytes).hexdigest() == expected_checksum

    # -------------------------------------------------------------------------
    # Shared-secret helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def derive_key_from_secret(secret: str, salt: Optional[str] = None) -> bytes:
        """HKDF-like key derivation from a shared secret."""
        if salt:
            material = secret + salt
        else:
            material = secret
        return hashlib.sha256(material.encode()).digest()
