"""Hash Calculator — SHA-256 Blueprint Signatures.

Computes deterministic SHA-256 fingerprints for automation blueprints
so that drift detection can reliably compare versions over time.

The hash is computed over the canonical YAML representation:
  1. YAML is parsed and re-serialized with sorted keys (Django-style canonical form)
  2. Only the blueprint body (triggers, conditions, actions) is hashed,
     not metadata like version, source, or last_modified.
  3. Comments and formatting whitespace are normalized away.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, Optional

import yaml

_LOGGER = logging.getLogger(__name__)

# Fields that are excluded from the hash because they are expected to
# change between imports (version, source, last_modified, etc.)
_METADATA_EXCLUDE = frozenset({
    "version",
    "source",
    "last_modified",
    "last_updated",
    "imported_at",
    "imported_by",
    "id",
    "blueprint_id",
})


def _canonical_dict(data: Any) -> Any:
    """Recursively normalise a dict/list/scalar to canonical sorted form."""
    if isinstance(data, dict):
        return sorted(
            (k, _canonical_dict(v)) for k, v in data.items() if k not in _METADATA_EXCLUDE
        )
    if isinstance(data, list):
        return [_canonical_dict(item) for item in data]
    return data


def _canonical_yaml(blueprint: Dict[str, Any]) -> str:
    """Render a blueprint dict as canonical YAML with sorted keys."""
    canonical = _canonical_dict(blueprint)
    # yaml.safe_dump with default_flow_style=False gives clean block style
    return yaml.safe_dump(
        canonical,
        default_flow_style=False,
        sort_keys=False,  # keys already sorted by _canonical_dict
        allow_unicode=True,
    )


def compute_blueprint_hash(blueprint: Dict[str, Any]) -> str:
    """Compute SHA-256 fingerprint of a blueprint.

    Args:
        blueprint: Parsed blueprint dict (as returned by yaml.safe_load).

    Returns:
        64-character hexadecimal SHA-256 digest.
    """
    try:
        canonical = _canonical_yaml(blueprint).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()
    except Exception as exc:
        _LOGGER.warning("Failed to compute canonical hash, falling back to raw YAML: %s", exc)
        raw = yaml.safe_dump(blueprint, default_flow_style=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


def compute_yaml_hash(yaml_content: str) -> str:
    """Compute SHA-256 fingerprint directly from YAML string.

    Parses the YAML first so that two syntactically different but semantically
    identical YAML strings produce the same hash.

    Args:
        yaml_content: Raw YAML string.

    Returns:
        64-character hexadecimal SHA-256 digest.
    """
    try:
        data = yaml.safe_load(yaml_content)
        if data is None:
            data = {}
        return compute_blueprint_hash(data)
    except Exception as exc:
        _LOGGER.warning("Failed to parse YAML for hashing, using raw string: %s", exc)
        return hashlib.sha256(yaml_content.encode("utf-8")).hexdigest()


def verify_blueprint_integrity(blueprint: Dict[str, Any], expected_hash: str) -> bool:
    """Check whether a blueprint matches the given hash.

    Args:
        blueprint: Parsed blueprint dict.
        expected_hash: SHA-256 hex digest previously stored as canonical.

    Returns:
        True if the blueprint's current hash matches expected_hash.
    """
    current = compute_blueprint_hash(blueprint)
    return current == expected_hash
