"""API Versioning constants and utilities (v5.0.0).

Provides version headers, deprecation warnings, and Accept-Version parsing.
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Current API version
API_VERSION = "1.0"

# Supported API versions
SUPPORTED_VERSIONS = {"1.0"}

# Deprecated endpoint patterns: path_prefix -> {sunset_date, successor}
DEPRECATED_ENDPOINTS: Dict[str, Dict[str, str]] = {
    # Example for future use:
    # "/api/v1/graph/snapshot.svg": {
    #     "sunset": "2026-09-01",
    #     "successor": "/api/v2/graph/snapshot",
    # },
}


def parse_accept_version(header_value: Optional[str]) -> str:
    """Parse the Accept-Version header.

    Returns the requested API version, or the current version if not specified.
    """
    if not header_value:
        return API_VERSION

    version = header_value.strip()

    # Normalize: "1" -> "1.0"
    if "." not in version:
        version = f"{version}.0"

    if version not in SUPPORTED_VERSIONS:
        logger.debug("Unsupported API version requested: %s", version)
        return API_VERSION

    return version


def get_deprecation_info(path: str) -> Optional[Dict[str, str]]:
    """Check if an endpoint path is deprecated.

    Returns deprecation info dict or None.
    """
    for prefix, info in DEPRECATED_ENDPOINTS.items():
        if path.startswith(prefix):
            return info
    return None
