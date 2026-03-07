#!/usr/bin/env python3
"""
OpenAPI Spec Generator for PilotSuite Styx Core API.

Auto-generates OpenAPI 3.0 specification from all registered API endpoints.
Produces both YAML and JSON output formats.

Usage:
    python openapi_spec.py --output openapi.yaml
    python openapi_spec.py --output openapi.json --format json
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# =============================================================================
# Configuration
# =============================================================================

API_BASE_PATH = Path(__file__).parent.parent / "rootfs" / "usr" / "src" / "app" / "copilot_core"
OUTPUT_DIR = Path(__file__).parent.parent / "docs"

# =============================================================================
# OpenAPI Metadata
# =============================================================================

OPENAPI_INFO = {
    "openapi": "3.0.3",
    "info": {
        "title": "PilotSuite Styx Core API",
        "description": """
# PilotSuite Styx Core API Documentation

Comprehensive REST API documentation for the PilotSuite Styx Core home automation platform.

## Architecture

PilotSuite Styx Core is a modular home automation backend built on Flask, providing:

- **Smart Home Integration**: Native Home Assistant integration with bi-directional sync
- **AI-Powered Automation**: Pattern mining, habitus learning, and predictive automation
- **Multi-Home Support**: Cross-home entity sharing and federated learning
- **Real-time Monitoring**: System health, energy tracking, and network diagnostics
- **Notification Engine**: Multi-channel notifications with digest and scheduling

## Authentication

All API endpoints require authentication via one of the following methods:

### API Key Authentication
Most endpoints use API Key authentication via the `X-API-Key` header:
```
X-API-Key: your-api-key-here
```

### Bearer Token Authentication
Some endpoints (Notifications, Telegram) use Bearer token authentication:
```
Authorization: Bearer your-token-here
```

## Versioning

API versioning is supported via the `Accept-Version` header:
```
Accept-Version: v1
```

Deprecated endpoints include `Deprecation` and `Sunset` headers in responses.

## Response Format

All responses follow a consistent JSON structure:
```json
{
  "status": "success",
  "data": { ... },
  "metadata": {
    "timestamp": "2026-03-01T10:00:00Z",
    "version": "v1"
  }
}
```

Error responses include:
```json
{
  "status": "error",
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": { ... }
  }
}
```
""",
        "version": "13.1.0",
        "contact": {
            "name": "PilotSuite",
            "url": "https://github.com/GreenhillEfka/pilotsuite-styx-core"
        },
        "license": {
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT"
        }
    },
    "servers": [
        {
            "url": "http://localhost:8909",
            "description": "Local development server"
        },
        {
            "url": "http://homeassistant.local:8909",
            "description": "Home Assistant network server"
        },
        {
            "url": "https://pilotsuite.example.com/api",
            "description": "Production server"
        }
    ],
    "tags": [],
    "security": [
        {"apiKeyAuth": []},
        {"bearerAuth": []}
    ]
}

# =============================================================================
# API Module Definitions
# =============================================================================

@dataclass
class APIEndpoint:
    """Represents a single API endpoint."""
    path: str
    method: str
    summary: str
    description: str
    operation_id: str
    tags: List[str]
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    request_body: Optional[Dict[str, Any]] = None
    responses: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    security: Optional[List[Dict[str, List[str]]]] = None
    deprecated: bool = False


@dataclass
class APIModule:
    """Represents an API module with multiple endpoints."""
    name: str
    description: str
    base_path: str
    endpoints: List[APIEndpoint] = field(default_factory=list)
    auth_type: str = "apiKey"  # apiKey, bearer, none


# =============================================================================
# API Module Registry
# =============================================================================

API_MODULES: List[APIModule] = [
    # Core Infrastructure APIs
    APIModule(
        name="System Health",
        description="System health monitoring, diagnostics, and performance metrics",
        base_path="/api/v1/system_health",
        auth_type="apiKey",
        endpoints=[
            APIEndpoint(
                path="/api/v1/system_health",
                method="GET",
                summary="Get complete system health status",
                description="Returns comprehensive system health including CPU, memory, disk, network, and service status.",
                operation_id="getSystemHealth",
                tags=["System Health"],
                responses={
                    "200": {
                        "description": "System health status",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string", "example": "healthy"},
                                        "cpu": {
                                            "type": "object",
                                            "properties": {
                                                "usage_percent": {"type": "number", "example": 23.5},
                                                "cores": {"type": "integer", "example": 4},
                                                "temperature": {"type": "number", "example": 45.2}
                                            }
                                        },
                                        "memory": {
                                            "type": "object",
                                            "properties": {
                                                "total_mb": {"type": "integer", "example": 8192},
                                                "used_mb": {"type": "integer", "example": 4096},
                                                "percent": {"type": "number", "example": 50.0}
                                            }
                                        },
                                        "disk": {
                                            "type": "object",
                                            "properties": {
                                                "total_gb": {"type": "number", "example": 128},
                                                "used_gb": {"type": "number", "example": 64},
                                                "percent": {"type": "number", "example": 50.0}
                                            }
                                        },
                                        "services": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "name": {"type": "string"},
                                                    "status": {"type": "string", "enum": ["running", "stopped", "error"]}
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/system_health/zigbee",
                method="GET",
                summary="Get Zigbee mesh health",
                description="Returns Zigbee network health including signal quality, routing tables, and device status.",
                operation_id="getZigbeeHealth",
                tags=["System Health", "Zigbee"],
                parameters=[
                    {
                        "name": "force",
                        "in": "query",
                        "description": "Force refresh from coordinator",
                        "required": False,
                        "schema": {"type": "boolean", "default": False}
                    }
                ],
                responses={
                    "200": {
                        "description": "Zigbee mesh health",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "coordinator": {
                                            "type": "object",
                                            "properties": {
                                                "ieee": {"type": "string", "example": "00:12:4b:00:12:34:56:78"},
                                                "status": {"type": "string"},
                                                "channel": {"type": "integer", "example": 15}
                                            }
                                        },
                                        "devices": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "ieee": {"type": "string"},
                                                    "nwk": {"type": "string"},
                                                    "lqi": {"type": "integer"},
                                                    "rssi": {"type": "integer"}
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/system_health/zwave",
                method="GET",
                summary="Get Z-Wave mesh health",
                description="Returns Z-Wave network health including node status, routing, and signal quality.",
                operation_id="getZWaveHealth",
                tags=["System Health", "Z-Wave"],
                responses={
                    "200": {
                        "description": "Z-Wave mesh health"
                    }
                }
            )
        ]
    ),
    
    APIModule(
        name="Brain Graph",
        description="Knowledge graph for event storage, pattern mining, and neural visualization",
        base_path="/api/v1/graph",
        auth_type="apiKey",
        endpoints=[
            APIEndpoint(
                path="/api/v1/graph/state",
                method="GET",
                summary="Get current graph state as JSON",
                description="Returns the complete graph state including nodes, edges, and metadata.",
                operation_id="getGraphState",
                tags=["Brain Graph"],
                parameters=[
                    {
                        "name": "kind",
                        "in": "query",
                        "description": "Filter by node kind (repeatable)",
                        "required": False,
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "domain",
                        "in": "query",
                        "description": "Filter by domain (repeatable)",
                        "required": False,
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "center",
                        "in": "query",
                        "description": "Center node for neighborhood query",
                        "required": False,
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "hops",
                        "in": "query",
                        "description": "Number of hops for neighborhood",
                        "required": False,
                        "schema": {"type": "integer", "default": 1}
                    },
                    {
                        "name": "limitNodes",
                        "in": "query",
                        "description": "Maximum nodes to return",
                        "required": False,
                        "schema": {"type": "integer", "default": 100}
                    },
                    {
                        "name": "nocache",
                        "in": "query",
                        "description": "Bypass cache",
                        "required": False,
                        "schema": {"type": "boolean", "default": False}
                    }
                ],
                responses={
                    "200": {
                        "description": "Graph state",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "nodes": {"type": "array", "items": {"type": "object"}},
                                        "edges": {"type": "array", "items": {"type": "object"}},
                                        "metadata": {"type": "object"}
                                    }
                                }
                            }
                        }
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/graph/render",
                method="POST",
                summary="Render graph visualization",
                description="Generates SVG or PNG visualization of the graph.",
                operation_id="renderGraph",
                tags=["Brain Graph"],
                request_body={
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "format": {"type": "string", "enum": ["svg", "png"], "default": "svg"},
                                    "layout": {"type": "string", "enum": ["force", "hierarchical", "circular"]},
                                    "filters": {"type": "object"}
                                }
                            }
                        }
                    }
                },
                responses={
                    "200": {
                        "description": "Graph visualization",
                        "content": {
                            "image/svg+xml": {"schema": {"type": "string"}},
                            "image/png": {"schema": {"type": "string", "format": "binary"}}
                        }
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/graph/query",
                method="POST",
                summary="Execute graph query",
                description="Execute complex queries on the knowledge graph.",
                operation_id="queryGraph",
                tags=["Brain Graph"],
                request_body={
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string"},
                                    "parameters": {"type": "object"}
                                }
                            }
                        }
                    }
                },
                responses={
                    "200": {
                        "description": "Query results"
                    }
                }
            )
        ]
    ),
    
    APIModule(
        name="Habitus",
        description="Pattern mining and habitus learning for automation discovery",
        base_path="/api/v1/habitus",
        auth_type="apiKey",
        endpoints=[
            APIEndpoint(
                path="/api/v1/habitus/mine",
                method="POST",
                summary="Trigger habitus pattern mining",
                description="Initiates pattern mining to discover automation candidates from historical data.",
                operation_id="triggerMining",
                tags=["Habitus"],
                request_body={
                    "required": False,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "lookback_hours": {
                                        "type": "integer",
                                        "default": 72,
                                        "description": "How far back to analyze"
                                    },
                                    "force": {
                                        "type": "boolean",
                                        "default": False,
                                        "description": "Force run even if recent"
                                    },
                                    "zone": {
                                        "type": "string",
                                        "description": "Zone ID to filter patterns"
                                    }
                                }
                            }
                        }
                    }
                },
                responses={
                    "200": {
                        "description": "Mining triggered successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string", "example": "started"},
                                        "job_id": {"type": "string"},
                                        "estimated_duration": {"type": "string"}
                                    }
                                }
                            }
                        }
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/habitus/stats",
                method="GET",
                summary="Get mining statistics",
                description="Returns statistics about pattern mining operations.",
                operation_id="getHabitusStats",
                tags=["Habitus"],
                responses={
                    "200": {
                        "description": "Mining statistics"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/habitus/patterns",
                method="GET",
                summary="Get recent patterns",
                description="Returns recently discovered patterns.",
                operation_id="getHabitusPatterns",
                tags=["Habitus"],
                parameters=[
                    {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer", "default": 50}
                    }
                ],
                responses={
                    "200": {
                        "description": "Recent patterns"
                    }
                }
            )
        ]
    ),
    
    APIModule(
        name="Candidates",
        description="Automation candidate management lifecycle",
        base_path="/api/v1/candidates",
        auth_type="apiKey",
        endpoints=[
            APIEndpoint(
                path="/api/v1/candidates",
                method="GET",
                summary="List candidates",
                description="List automation candidates with optional filters.",
                operation_id="listCandidates",
                tags=["Candidates"],
                parameters=[
                    {
                        "name": "state",
                        "in": "query",
                        "description": "Filter by state",
                        "required": False,
                        "schema": {
                            "type": "string",
                            "enum": ["pending", "offered", "accepted", "dismissed", "deferred"]
                        }
                    },
                    {
                        "name": "include_ready_deferred",
                        "in": "query",
                        "description": "Include deferred candidates ready for retry",
                        "required": False,
                        "schema": {"type": "boolean", "default": False}
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "description": "Maximum results",
                        "required": False,
                        "schema": {"type": "integer", "default": 50, "maximum": 200}
                    }
                ],
                responses={
                    "200": {
                        "description": "List of candidates",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "candidates": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/Candidate"}
                                        },
                                        "count": {"type": "integer"}
                                    }
                                }
                            }
                        }
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/candidates",
                method="POST",
                summary="Create candidate",
                description="Create a new automation candidate from pattern discovery.",
                operation_id="createCandidate",
                tags=["Candidates"],
                request_body={
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/CandidateInput"
                            }
                        }
                    }
                },
                responses={
                    "201": {
                        "description": "Candidate created"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/candidates/{candidate_id}",
                method="GET",
                summary="Get candidate details",
                description="Retrieve a specific candidate by ID.",
                operation_id="getCandidate",
                tags=["Candidates"],
                parameters=[
                    {
                        "name": "candidate_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"}
                    }
                ],
                responses={
                    "200": {
                        "description": "Candidate details"
                    },
                    "404": {
                        "description": "Candidate not found"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/candidates/{candidate_id}",
                method="PUT",
                summary="Update candidate state",
                description="Update candidate state (accept/dismiss/defer).",
                operation_id="updateCandidate",
                tags=["Candidates"],
                parameters=[
                    {
                        "name": "candidate_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"}
                    }
                ],
                request_body={
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "state": {
                                        "type": "string",
                                        "enum": ["accepted", "dismissed", "deferred"]
                                    },
                                    "reason": {"type": "string"}
                                }
                            }
                        }
                    }
                },
                responses={
                    "200": {
                        "description": "Candidate updated"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/candidates/stats",
                method="GET",
                summary="Get storage statistics",
                description="Returns candidate storage statistics and health.",
                operation_id="getCandidateStats",
                tags=["Candidates"],
                responses={
                    "200": {
                        "description": "Storage statistics"
                    }
                }
            )
        ]
    ),
    
    APIModule(
        name="Mood",
        description="Zone mood scoring and ambient context",
        base_path="/api/v1/mood",
        auth_type="apiKey",
        endpoints=[
            APIEndpoint(
                path="/api/v1/mood",
                method="GET",
                summary="Get all zone moods",
                description="Returns mood scores for all zones.",
                operation_id="getAllMoods",
                tags=["Mood"],
                responses={
                    "200": {
                        "description": "All zone moods"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/mood/{zone_id}",
                method="GET",
                summary="Get specific zone mood",
                description="Returns mood score for a specific zone.",
                operation_id="getZoneMood",
                tags=["Mood"],
                parameters=[
                    {
                        "name": "zone_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"}
                    }
                ],
                responses={
                    "200": {
                        "description": "Zone mood"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/mood/summary",
                method="GET",
                summary="Get aggregated mood stats",
                description="Returns aggregated mood statistics across all zones.",
                operation_id="getMoodSummary",
                tags=["Mood"],
                responses={
                    "200": {
                        "description": "Mood summary"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/mood/update-media",
                method="POST",
                summary="Update moods from media context",
                description="Updates zone moods based on media player state.",
                operation_id="updateMoodFromMedia",
                tags=["Mood"],
                request_body={
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "music_active": {"type": "boolean"},
                                    "tv_active": {"type": "boolean"},
                                    "primary_player": {"type": "object"}
                                }
                            }
                        }
                    }
                },
                responses={
                    "200": {
                        "description": "Moods updated"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/mood/update-habitus",
                method="POST",
                summary="Update moods from habitus",
                description="Updates zone moods based on habitus patterns.",
                operation_id="updateMoodFromHabitus",
                tags=["Mood"],
                responses={
                    "200": {
                        "description": "Moods updated"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/mood/{zone_id}/suppress-energy-saving",
                method="GET",
                summary="Check energy-saving suppression",
                description="Checks if energy-saving should be suppressed for this zone.",
                operation_id="checkEnergySavingSuppression",
                tags=["Mood"],
                parameters=[
                    {
                        "name": "zone_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"}
                    }
                ],
                responses={
                    "200": {
                        "description": "Suppression status"
                    }
                }
            )
        ]
    ),
    
    # PilotSuite Phase 5 APIs
    APIModule(
        name="Notifications",
        description="Notification engine with multi-channel delivery",
        base_path="/api/v1/notifications",
        auth_type="bearer",
        endpoints=[
            APIEndpoint(
                path="/api/v1/notifications",
                method="GET",
                summary="Get notification history",
                description="Returns notification history with optional filtering.",
                operation_id="getNotifications",
                tags=["Notifications"],
                security=[{"bearerAuth": []}],
                parameters=[
                    {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer", "default": 50}
                    },
                    {
                        "name": "source",
                        "in": "query",
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "unread_only",
                        "in": "query",
                        "schema": {"type": "boolean", "default": False}
                    },
                    {
                        "name": "type",
                        "in": "query",
                        "schema": {
                            "type": "string",
                            "enum": ["mood_change", "alert", "suggestion", "system", "info", "warning"]
                        }
                    }
                ],
                responses={
                    "200": {
                        "description": "Notification history"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/notifications",
                method="POST",
                summary="Create notification",
                description="Creates a new notification.",
                operation_id="createNotification",
                tags=["Notifications"],
                security=[{"bearerAuth": []}],
                request_body={
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/NotificationRequest"
                            }
                        }
                    }
                },
                responses={
                    "201": {
                        "description": "Notification created"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/notifications/digest",
                method="GET",
                summary="Get notification digest",
                description="Returns notification digest summary.",
                operation_id="getNotificationDigest",
                tags=["Notifications"],
                security=[{"bearerAuth": []}],
                responses={
                    "200": {
                        "description": "Notification digest"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/notifications/pending",
                method="GET",
                summary="Get pending notifications",
                description="Returns pending notifications for delivery.",
                operation_id="getPendingNotifications",
                tags=["Notifications"],
                security=[{"bearerAuth": []}],
                responses={
                    "200": {
                        "description": "Pending notifications"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/notifications/stats",
                method="GET",
                summary="Get notification statistics",
                description="Returns notification engine statistics.",
                operation_id="getNotificationStats",
                tags=["Notifications"],
                security=[{"bearerAuth": []}],
                responses={
                    "200": {
                        "description": "Notification statistics"
                    }
                }
            )
        ]
    ),
    
    APIModule(
        name="Sharing",
        description="Cross-home entity sharing and synchronization",
        base_path="/api/v1/sharing",
        auth_type="apiKey",
        endpoints=[
            APIEndpoint(
                path="/api/v1/sharing",
                method="GET",
                summary="Get sharing system status",
                description="Returns combined status of sharing, sync, and discovery services.",
                operation_id="getSharingStatus",
                tags=["Sharing"],
                responses={
                    "200": {
                        "description": "Sharing system status"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/sharing/entities",
                method="GET",
                summary="List shared entities",
                description="Returns all shared entities.",
                operation_id="listSharedEntities",
                tags=["Sharing"],
                responses={
                    "200": {
                        "description": "Shared entities"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/sharing/entities",
                method="POST",
                summary="Register shared entity",
                description="Registers a new entity for cross-home sharing.",
                operation_id="registerSharedEntity",
                tags=["Sharing"],
                request_body={
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/SharedEntity"
                            }
                        }
                    }
                },
                responses={
                    "201": {
                        "description": "Entity registered"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/sharing/sync/status",
                method="GET",
                summary="Get sync status",
                description="Returns synchronization status.",
                operation_id="getSyncStatus",
                tags=["Sharing"],
                responses={
                    "200": {
                        "description": "Sync status"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/sharing/discovery/peers",
                method="GET",
                summary="List discovered peers",
                description="Returns discovered peer CoPilot instances.",
                operation_id="listPeers",
                tags=["Sharing"],
                responses={
                    "200": {
                        "description": "Discovered peers"
                    }
                }
            )
        ]
    ),
    
    APIModule(
        name="Collective Intelligence",
        description="Federated learning across multiple homes",
        base_path="/api/v1/federated",
        auth_type="apiKey",
        endpoints=[
            APIEndpoint(
                path="/api/v1/federated",
                method="GET",
                summary="Get federated learning status",
                description="Returns federated learning system status.",
                operation_id="getFederatedStatus",
                tags=["Federated Learning"],
                responses={
                    "200": {
                        "description": "Federated learning status"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/federated/start",
                method="POST",
                summary="Start federated learning",
                description="Starts the federated learning service.",
                operation_id="startFederated",
                tags=["Federated Learning"],
                responses={
                    "200": {
                        "description": "Service started"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/federated/stop",
                method="POST",
                summary="Stop federated learning",
                description="Stops the federated learning service.",
                operation_id="stopFederated",
                tags=["Federated Learning"],
                responses={
                    "200": {
                        "description": "Service stopped"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/federated/register",
                method="POST",
                summary="Register home node",
                description="Registers a new home node in the federation.",
                operation_id="registerNode",
                tags=["Federated Learning"],
                request_body={
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "home_id": {"type": "string"},
                                    "name": {"type": "string"},
                                    "capabilities": {"type": "array", "items": {"type": "string"}}
                                }
                            }
                        }
                    }
                },
                responses={
                    "201": {
                        "description": "Node registered"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/federated/update",
                method="POST",
                summary="Submit model update",
                description="Submits a local model update to the federation.",
                operation_id="submitUpdate",
                tags=["Federated Learning"],
                responses={
                    "200": {
                        "description": "Update submitted"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/federated/round",
                method="POST",
                summary="Start federated round",
                description="Initiates a new federated learning round.",
                operation_id="startRound",
                tags=["Federated Learning"],
                responses={
                    "200": {
                        "description": "Round started"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/federated/aggregate",
                method="POST",
                summary="Execute aggregation",
                description="Executes model aggregation for a round.",
                operation_id="aggregateRound",
                tags=["Federated Learning"],
                responses={
                    "200": {
                        "description": "Aggregation completed"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/federated/rounds",
                method="GET",
                summary="Get round history",
                description="Returns history of federated learning rounds.",
                operation_id="getRoundHistory",
                tags=["Federated Learning"],
                responses={
                    "200": {
                        "description": "Round history"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/federated/statistics",
                method="GET",
                summary="Get comprehensive statistics",
                description="Returns comprehensive federated learning statistics.",
                operation_id="getFederatedStats",
                tags=["Federated Learning"],
                responses={
                    "200": {
                        "description": "Statistics"
                    }
                }
            )
        ]
    ),
    
    # Additional Core APIs
    APIModule(
        name="Energy",
        description="Energy monitoring and optimization",
        base_path="/api/v1/energy",
        auth_type="apiKey",
        endpoints=[
            APIEndpoint(
                path="/api/v1/energy",
                method="GET",
                summary="Get energy snapshot",
                description="Returns complete energy snapshot.",
                operation_id="getEnergy",
                tags=["Energy"],
                responses={
                    "200": {
                        "description": "Energy snapshot"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/energy/anomalies",
                method="GET",
                summary="Get energy anomalies",
                description="Returns detected energy anomalies.",
                operation_id="getEnergyAnomalies",
                tags=["Energy"],
                responses={
                    "200": {
                        "description": "Energy anomalies"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/energy/sankey",
                method="GET",
                summary="Get energy Sankey diagram",
                description="Returns Sankey diagram data for energy flows.",
                operation_id="getEnergySankey",
                tags=["Energy"],
                responses={
                    "200": {
                        "description": "Sankey diagram data"
                    }
                }
            )
        ]
    ),
    
    APIModule(
        name="UniFi",
        description="UniFi network monitoring",
        base_path="/api/v1/unifi",
        auth_type="bearer",
        endpoints=[
            APIEndpoint(
                path="/api/v1/unifi",
                method="GET",
                summary="Get UniFi network snapshot",
                description="Returns complete UniFi network snapshot.",
                operation_id="getUniFi",
                tags=["UniFi"],
                security=[{"bearerAuth": []}],
                responses={
                    "200": {
                        "description": "UniFi snapshot"
                    }
                }
            )
        ]
    ),
    
    APIModule(
        name="Tags",
        description="Tag system for entity organization",
        base_path="/api/v1/tag-system",
        auth_type="bearer",
        endpoints=[
            APIEndpoint(
                path="/api/v1/tag-system/tags",
                method="GET",
                summary="List tag registry entries",
                description="Returns all tags from the canonical tag registry.",
                operation_id="listTags",
                tags=["Tags"],
                security=[{"bearerAuth": []}],
                responses={
                    "200": {
                        "description": "List of tags"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/tag-system/tags/{tag_id}",
                method="GET",
                summary="Get tag registry entry",
                description="Returns a single tag by id from the canonical tag registry.",
                operation_id="getTag",
                tags=["Tags"],
                security=[{"bearerAuth": []}],
                parameters=[
                    {
                        "name": "tag_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"}
                    }
                ],
                responses={
                    "200": {
                        "description": "Tag details"
                    },
                    "404": {
                        "description": "Tag not found"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/tag-system/assignments",
                method="GET",
                summary="List tag assignments",
                description="Returns tag assignments with optional subject/tag filters.",
                operation_id="listTagAssignments",
                tags=["Tags"],
                security=[{"bearerAuth": []}],
                parameters=[
                    {"name": "subject_id", "in": "query", "required": False, "schema": {"type": "string"}},
                    {"name": "subject_kind", "in": "query", "required": False, "schema": {"type": "string"}},
                    {"name": "tag_id", "in": "query", "required": False, "schema": {"type": "string"}},
                    {"name": "materialized", "in": "query", "required": False, "schema": {"type": "boolean"}},
                    {"name": "limit", "in": "query", "required": False, "schema": {"type": "integer", "default": 200}},
                ],
                responses={
                    "200": {
                        "description": "Tag assignments"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/tag-system/assignments",
                method="POST",
                summary="Create or update tag assignment",
                description="Upserts a tag assignment for a subject.",
                operation_id="upsertTagAssignment",
                tags=["Tags"],
                security=[{"bearerAuth": []}],
                request_body={
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["subject_id", "subject_kind", "tag_id"],
                                "properties": {
                                    "subject_id": {"type": "string"},
                                    "subject_kind": {"type": "string"},
                                    "tag_id": {"type": "string"},
                                    "source": {"type": "string", "default": "core"},
                                    "confidence": {
                                        "type": "number",
                                        "format": "float",
                                        "minimum": 0,
                                        "maximum": 1,
                                    },
                                    "meta": {"type": "object"},
                                    "materialized": {"type": "boolean"},
                                },
                            }
                        }
                    }
                },
                responses={
                    "200": {
                        "description": "Assignment updated"
                    },
                    "201": {
                        "description": "Assignment created"
                    },
                    "400": {
                        "description": "Invalid assignment payload"
                    },
                    "404": {
                        "description": "Tag not found"
                    },
                }
            ),
        ],
    ),
    
    APIModule(
        name="Dev Surface",
        description="Development observability and diagnostics",
        base_path="/api/v1/dev",
        auth_type="apiKey",
        endpoints=[
            APIEndpoint(
                path="/api/v1/dev/logs",
                method="GET",
                summary="Get recent logs",
                description="Returns recent log entries with optional filtering.",
                operation_id="getDevLogs",
                tags=["Dev Surface"],
                parameters=[
                    {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer", "default": 100}
                    },
                    {
                        "name": "level",
                        "in": "query",
                        "schema": {"type": "string", "enum": ["DEBUG", "INFO", "WARNING", "ERROR"]}
                    }
                ],
                responses={
                    "200": {
                        "description": "Log entries"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/dev/errors",
                method="GET",
                summary="Get error summary",
                description="Returns error summary and statistics.",
                operation_id="getErrorSummary",
                tags=["Dev Surface"],
                responses={
                    "200": {
                        "description": "Error summary"
                    }
                }
            )
        ]
    ),
    
    APIModule(
        name="Telegram",
        description="Telegram bot integration",
        base_path="/telegram",
        auth_type="bearer",
        endpoints=[
            APIEndpoint(
                path="/telegram/status",
                method="GET",
                summary="Get Telegram bot status",
                description="Returns Telegram bot status.",
                operation_id="getTelegramStatus",
                tags=["Telegram"],
                security=[{"bearerAuth": []}],
                responses={
                    "200": {
                        "description": "Bot status"
                    }
                }
            ),
            APIEndpoint(
                path="/telegram/send",
                method="POST",
                summary="Send Telegram message",
                description="Sends a proactive message to a Telegram chat.",
                operation_id="sendTelegram",
                tags=["Telegram"],
                security=[{"bearerAuth": []}],
                request_body={
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "chat_id": {"type": "string"},
                                    "text": {"type": "string"}
                                },
                                "required": ["chat_id", "text"]
                            }
                        }
                    }
                },
                responses={
                    "200": {
                        "description": "Message sent"
                    }
                }
            )
        ]
    ),
    
    APIModule(
        name="Hub",
        description="PilotSuite Hub - Central management interface",
        base_path="/api/v1/hub",
        auth_type="bearer",
        endpoints=[
            APIEndpoint(
                path="/api/v1/hub/status",
                method="GET",
                summary="Get Hub status",
                description="Returns complete Hub status including all engines.",
                operation_id="getHubStatus",
                tags=["Hub"],
                security=[{"bearerAuth": []}],
                responses={
                    "200": {
                        "description": "Hub status"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/hub/zones",
                method="GET",
                summary="List zones",
                description="Returns all configured zones.",
                operation_id="listZones",
                tags=["Hub"],
                security=[{"bearerAuth": []}],
                responses={
                    "200": {
                        "description": "List of zones"
                    }
                }
            ),
            APIEndpoint(
                path="/api/v1/hub/modes",
                method="GET",
                summary="List modes",
                description="Returns all configured modes.",
                operation_id="listModes",
                tags=["Hub"],
                security=[{"bearerAuth": []}],
                responses={
                    "200": {
                        "description": "List of modes"
                    }
                }
            )
        ]
    )
]

# =============================================================================
# Schema Definitions
# =============================================================================

COMPONENT_SCHEMAS = {
    "schemas": {
        "Candidate": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Unique candidate identifier"},
                "pattern_id": {"type": "string", "description": "Source pattern ID"},
                "state": {
                    "type": "string",
                    "enum": ["pending", "offered", "accepted", "dismissed", "deferred"],
                    "description": "Current candidate state"
                },
                "title": {"type": "string", "description": "Candidate title"},
                "description": {"type": "string", "description": "Candidate description"},
                "automation_yaml": {"type": "string", "description": "Generated automation YAML"},
                "confidence": {"type": "number", "description": "Confidence score (0-1)"},
                "created_at": {"type": "string", "format": "date-time"},
                "updated_at": {"type": "string", "format": "date-time"},
                "deferred_until": {"type": "string", "format": "date-time"}
            },
            "required": ["id", "state", "title", "created_at"]
        },
        "CandidateInput": {
            "type": "object",
            "properties": {
                "pattern_id": {"type": "string"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "automation_yaml": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1}
            },
            "required": ["pattern_id", "title", "automation_yaml"]
        },
        "NotificationRequest": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Notification title"},
                "message": {"type": "string", "description": "Notification message"},
                "type": {
                    "type": "string",
                    "enum": ["mood_change", "alert", "suggestion", "system", "info", "warning"]
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "normal", "high", "urgent"],
                    "default": "normal"
                },
                "channel": {
                    "type": "string",
                    "enum": ["push", "telegram", "email", "all"]
                },
                "data": {"type": "object", "description": "Additional payload data"}
            },
            "required": ["title", "message"]
        },
        "NotificationResponse": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "status": {"type": "string"},
                "delivered_at": {"type": "string", "format": "date-time"}
            }
        },
        "SharedEntity": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string", "description": "Home Assistant entity ID"},
                "name": {"type": "string", "description": "Entity display name"},
                "type": {"type": "string", "description": "Entity type"},
                "home_id": {"type": "string", "description": "Source home identifier"},
                "capabilities": {"type": "array", "items": {"type": "string"}},
                "metadata": {"type": "object"}
            },
            "required": ["entity_id", "name", "type", "home_id"]
        },
        "Error": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "message": {"type": "string"},
                "details": {"type": "object"}
            }
        }
    }
}

# =============================================================================
# Security Schemes
# =============================================================================

SECURITY_SCHEMES = {
    "apiKeyAuth": {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
        "description": "API Key authentication for most endpoints"
    },
    "bearerAuth": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Bearer token authentication for Notifications and Telegram APIs"
    }
}

# =============================================================================
# Spec Generator
# =============================================================================

def generate_openapi_spec() -> Dict[str, Any]:
    """Generate complete OpenAPI specification."""
    spec = {
        **OPENAPI_INFO,
        "tags": [],
        "paths": {},
        "components": COMPONENT_SCHEMAS,
        "security": OPENAPI_INFO["security"]
    }
    
    # Add components.securitySchemes
    spec["components"]["securitySchemes"] = SECURITY_SCHEMES
    
    # Process each module
    for module in API_MODULES:
        # Add tag
        spec["tags"].append({
            "name": module.name,
            "description": module.description
        })
        
        # Process endpoints
        for endpoint in module.endpoints:
            path = endpoint.path
            
            # Initialize path if not exists
            if path not in spec["paths"]:
                spec["paths"][path] = {}
            
            # Build operation object
            operation = {
                "summary": endpoint.summary,
                "description": endpoint.description,
                "operationId": endpoint.operation_id,
                "tags": endpoint.tags,
                "responses": endpoint.responses
            }
            
            # Add parameters
            if endpoint.parameters:
                operation["parameters"] = endpoint.parameters
            
            # Add request body
            if endpoint.request_body:
                operation["requestBody"] = endpoint.request_body
            
            # Add security override if specified
            if endpoint.security is not None:
                operation["security"] = endpoint.security
            elif module.auth_type == "bearer":
                operation["security"] = [{"bearerAuth": []}]
            elif module.auth_type == "apiKey":
                operation["security"] = [{"apiKeyAuth": []}]
            
            # Add deprecated flag
            if endpoint.deprecated:
                operation["deprecated"] = True
            
            # Add to paths
            method_key = endpoint.method.lower()
            spec["paths"][path][method_key] = operation
    
    return spec


def save_spec(spec: Dict[str, Any], output_path: Path, format: str = "yaml") -> None:
    """Save specification to file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if format == "json":
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=2)
    else:
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(spec, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    print(f"✓ OpenAPI spec saved to: {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate OpenAPI specification for PilotSuite Styx Core API"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="openapi.yaml",
        help="Output file path (default: openapi.yaml)"
    )
    parser.add_argument(
        "--format", "-f",
        type=str,
        choices=["yaml", "json"],
        default="yaml",
        help="Output format (default: yaml)"
    )
    parser.add_argument(
        "--output-dir", "-d",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR})"
    )
    
    args = parser.parse_args()
    
    # Generate spec
    print("Generating OpenAPI specification...")
    spec = generate_openapi_spec()
    
    # Determine output path
    output_path = args.output_dir / args.output
    if not output_path.suffix:
        output_path = output_path.with_suffix(f".{args.format}")
    
    # Save spec
    save_spec(spec, output_path, args.format)
    
    # Print summary
    print(f"\n📊 OpenAPI Specification Summary:")
    print(f"   - Tags: {len(spec['tags'])}")
    print(f"   - Paths: {len(spec['paths'])}")
    print(f"   - Schemas: {len(spec['components']['schemas'])}")
    print(f"   - Security Schemes: {len(spec['components']['securitySchemes'])}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
