# Zone Editor API Documentation

**Core v15.0 Zone Automation** | **Version:** 15.0 | **Last Updated:** 2026-03-22

Comprehensive API documentation for the Zone Editor system enabling bidirectional synchronization of habitus zones between Home Assistant and PilotSuite Core.

---

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [Data Types](#data-types)
- [Endpoints](#endpoints)
  - [POST /api/v1/habitus/zones/sync](#post-apiv1habituszonessync)
  - [GET /api/v1/habitus/zones](#get-apiv1habituszones)
  - [GET /api/v1/habitus/zones/:zone_id](#get-apiv1habituszoneszone_id)
  - [PUT /api/v1/habitus/zones/:zone_id](#put-apiv1habituszoneszone_id)
  - [DELETE /api/v1/habitus/zones/:zone_id](#delete-apiv1habituszoneszone_id)
  - [GET /api/v1/habitus/zones/summary](#get-apiv1habituszonessummary)
- [Error Codes](#error-codes)
- [Python SDK Examples](#python-sdk-examples)

---

## Overview

The Zone Editor API provides bidirectional synchronization of habitus zones between Home Assistant and the PilotSuite Core. Zones define logical groupings of entities with specific roles for mood-based automation.

### What are Zones?

Zones represent logical areas in your home with assigned entities and roles:

```json
{
  "zone_id": "zone:wohnzimmer",
  "name": "Wohnzimmer",
  "zone_type": "living",
  "entity_ids": [
    "light.wohnzimmer_hauptlicht",
    "light.wohnzimmer_stehlampe",
    "sensor.wohnzimmer_temperatur",
    "binary_sensor.wohnzimmer_bewegung"
  ],
  "entities": {
    "primary_light": "light.wohnzimmer_hauptlicht",
    "ambient_light": "light.wohnzimmer_stehlampe",
    "temperature_sensor": "sensor.wohnzimmer_temperatur",
    "motion_sensor": "binary_sensor.wohnzimmer_bewegung"
  },
  "mood_settings": {
    "relax": {"brightness": 40, "color_temp": 3000},
    "focus": {"brightness": 80, "color_temp": 4000},
    "active": {"brightness": 100, "color_temp": 5000}
  }
}
```

### Key Features

- 🔄 **Bidirectional Sync:** HA ↔ Core synchronization
- 📍 **Zone Management:** Create, update, delete zones
- 🎭 **Mood Integration:** Per-zone mood settings
- 🏷️ **Entity Roles:** Structured entity assignment
- 💾 **Persistent Storage:** JSON-based state persistence
- 📡 **EventBus Integration:** Real-time zone events

### Zone Types

| Type | Description | Example Entities |
|------|-------------|------------------|
| `living` | Living areas | Lights, media, climate |
| `bedroom` | Sleeping areas | Lights, blinds, climate |
| `kitchen` | Kitchen | Lights, appliances |
| `bathroom` | Bathroom | Lights, ventilation |
| `office` | Workspace | Lights, desk equipment |
| `hallway` | Transit areas | Lights, motion sensors |
| `outdoor` | Outdoor areas | Garden lights, sensors |

### Entity Roles

| Role | Description | Example |
|------|-------------|---------|
| `primary_light` | Main lighting | `light.wohnzimmer_hauptlicht` |
| `ambient_light` | Ambient/accent lighting | `light.wohnzimmer_stehlampe` |
| `temperature_sensor` | Temperature monitoring | `sensor.wohnzimmer_temperatur` |
| `motion_sensor` | Motion detection | `binary_sensor.wohnzimmer_bewegung` |
| `humidity_sensor` | Humidity monitoring | `sensor.wohnzimmer_feuchtigkeit` |
| `climate` | Climate control | `climate.wohnzimmer` |
| `media_player` | Media devices | `media_player.wohnzimmer_tv` |
| `cover` | Window covers | `cover.wohnzimmer_rollo` |

---

## Authentication

All endpoints require authentication:

```http
X-Auth-Token: your-api-token-here
```

or

```http
Authorization: Bearer your-api-token-here
```

**Authentication Failure:**

```json
{
  "ok": false,
  "error": "Valid X-Auth-Token or Bearer token required"
}
```

**HTTP Status:** `401 Unauthorized`

---

## Data Types

### Zone Object

```json
{
  "zone_id": "zone:wohnzimmer",
  "name": "Wohnzimmer",
  "zone_type": "living",
  "entity_ids": [
    "light.wohnzimmer_hauptlicht",
    "light.wohnzimmer_stehlampe"
  ],
  "entities": {
    "primary_light": "light.wohnzimmer_hauptlicht",
    "ambient_light": "light.wohnzimmer_stehlampe"
  },
  "mood_settings": {
    "relax": {"brightness": 40, "color_temp": 3000},
    "focus": {"brightness": 80, "color_temp": 4000}
  },
  "synced_at": "2026-03-01T14:30:00Z",
  "source": "ha",
  "updated_at": "2026-03-01T14:30:00Z"
}
```

### Zone Summary Object

```json
{
  "zone_id": "zone:wohnzimmer",
  "name": "Wohnzimmer",
  "entity_count": 4,
  "roles": ["primary_light", "ambient_light", "temperature_sensor", "motion_sensor"],
  "synced_at": "2026-03-01T14:30:00Z",
  "source": "ha"
}
```

### Sync Request Object

```json
{
  "zones": [
    {
      "zone_id": "zone:wohnzimmer",
      "name": "Wohnzimmer",
      "zone_type": "living",
      "entity_ids": [...],
      "entities": {...}
    }
  ],
  "full_sync": true
}
```

---

## Endpoints

### POST /api/v1/habitus/zones/sync

Synchronize all zones from Home Assistant to Core.

#### Description

Bidirectional sync endpoint that merges zones from HA with existing Core data. Supports full sync (removes deleted zones) or incremental sync.

#### Request Format

**Endpoint:** `POST /api/v1/habitus/zones/sync`

**Headers:**
```http
Content-Type: application/json
X-Auth-Token: your-api-token
```

**Body:**
```json
{
  "zones": [
    {
      "zone_id": "zone:wohnzimmer",
      "name": "Wohnzimmer",
      "zone_type": "living",
      "entity_ids": [
        "light.wohnzimmer_hauptlicht",
        "light.wohnzimmer_stehlampe",
        "sensor.wohnzimmer_temperatur"
      ],
      "entities": {
        "primary_light": "light.wohnzimmer_hauptlicht",
        "ambient_light": "light.wohnzimmer_stehlampe",
        "temperature_sensor": "sensor.wohnzimmer_temperatur"
      },
      "mood_settings": {
        "relax": {"brightness": 40, "color_temp": 3000},
        "focus": {"brightness": 80, "color_temp": 4000},
        "active": {"brightness": 100, "color_temp": 5000}
      }
    },
    {
      "zone_id": "zone:schlafzimmer",
      "name": "Schlafzimmer",
      "zone_type": "bedroom",
      "entity_ids": [
        "light.schlafzimmer_deckenlicht",
        "cover.schlafzimmer_rollo"
      ],
      "entities": {
        "primary_light": "light.schlafzimmer_deckenlicht",
        "cover": "cover.schlafzimmer_rollo"
      }
    }
  ],
  "full_sync": true
}
```

**Request Parameters:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `zones` | array | ✅ Yes | - | List of zone objects to sync |
| `full_sync` | boolean | ❌ No | false | If true, removes zones not in the list |

#### Response Format

**Success Response (200 OK):**

```json
{
  "ok": true,
  "synced": 2,
  "zone_ids": [
    "zone:wohnzimmer",
    "zone:schlafzimmer"
  ]
}
```

#### EventBus Events

The sync operation publishes the following events:

- `zone.synced` - After successful sync
- `zone.deleted` - For each removed zone (full_sync only)

#### Python Code Example

```python
import requests
from typing import List, Dict, Any, Optional


class ZoneEditorClient:
    """Client for Zone Editor API."""
    
    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.session = requests.Session()
        self.session.headers.update({
            'X-Auth-Token': api_token,
            'Content-Type': 'application/json'
        })
    
    def sync_zones(
        self,
        zones: List[Dict[str, Any]],
        full_sync: bool = True
    ) -> Dict[str, Any]:
        """
        Synchronize zones from HA to Core.
        
        Args:
            zones: List of zone objects
            full_sync: If true, removes zones not in the list
            
        Returns:
            Sync result with synced zone IDs
        """
        payload = {
            'zones': zones,
            'full_sync': full_sync
        }
        
        response = self.session.post(
            f'{self.base_url}/api/v1/habitus/zones/sync',
            json=payload
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 400:
            raise ValueError(f"Bad request: {response.json().get('error')}")
        elif response.status_code == 401:
            raise PermissionError("Invalid API token")
        else:
            response.raise_for_status()


# Usage Example
if __name__ == '__main__':
    client = ZoneEditorClient(
        base_url='http://localhost:8123',
        api_token='your-api-token-here'
    )
    
    # Define zones to sync
    zones = [
        {
            'zone_id': 'zone:wohnzimmer',
            'name': 'Wohnzimmer',
            'zone_type': 'living',
            'entity_ids': [
                'light.wohnzimmer_hauptlicht',
                'light.wohnzimmer_stehlampe'
            ],
            'entities': {
                'primary_light': 'light.wohnzimmer_hauptlicht',
                'ambient_light': 'light.wohnzimmer_stehlampe'
            },
            'mood_settings': {
                'relax': {'brightness': 40, 'color_temp': 3000},
                'focus': {'brightness': 80, 'color_temp': 4000}
            }
        }
    ]
    
    # Perform sync
    result = client.sync_zones(zones, full_sync=True)
    
    print(f"✅ Synced {result['synced']} zones")
    print(f"   Zone IDs: {result['zone_ids']}")
```

---

### GET /api/v1/habitus/zones

Get all habitus zones.

#### Description

Retrieves all zones with optional filtering by zone type.

#### Request Format

**Endpoint:** `GET /api/v1/habitus/zones`

**Headers:**
```http
X-Auth-Token: your-api-token
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `type` | string | ❌ No | Filter by zone type (e.g., "living", "bedroom") |

#### Response Format

```json
{
  "ok": true,
  "zones": [
    {
      "zone_id": "zone:wohnzimmer",
      "name": "Wohnzimmer",
      "zone_type": "living",
      "entity_ids": [...],
      "entities": {...},
      "mood_settings": {...},
      "synced_at": "2026-03-01T14:30:00Z",
      "source": "ha"
    }
  ],
  "count": 1
}
```

#### Python Code Example

```python
def list_zones_example(client: ZoneEditorClient):
    """Example: List all zones."""
    
    # Get all zones
    response = client.session.get(
        f'{client.base_url}/api/v1/habitus/zones'
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"📍 Found {data['count']} zones:")
        for zone in data['zones']:
            print(f"  • {zone['name']} ({zone['zone_type']})")
            print(f"    Entities: {len(zone.get('entity_ids', []))}")
    
    # Get only living zones
    response = client.session.get(
        f'{client.base_url}/api/v1/habitus/zones',
        params={'type': 'living'}
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n🏠 Living zones: {data['count']}")
```

---

### GET /api/v1/habitus/zones/:zone_id

Get a single zone by ID.

#### Description

Retrieves detailed information for a specific zone.

#### Request Format

**Endpoint:** `GET /api/v1/habitus/zones/:zone_id`

**Headers:**
```http
X-Auth-Token: your-api-token
```

**URL Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `zone_id` | string | Zone identifier (e.g., "zone:wohnzimmer") |

#### Response Format

**Success Response (200 OK):**

```json
{
  "ok": true,
  "zone": {
    "zone_id": "zone:wohnzimmer",
    "name": "Wohnzimmer",
    "zone_type": "living",
    "entity_ids": [
      "light.wohnzimmer_hauptlicht",
      "light.wohnzimmer_stehlampe"
    ],
    "entities": {
      "primary_light": "light.wohnzimmer_hauptlicht",
      "ambient_light": "light.wohnzimmer_stehlampe"
    },
    "mood_settings": {
      "relax": {"brightness": 40, "color_temp": 3000},
      "focus": {"brightness": 80, "color_temp": 4000}
    },
    "synced_at": "2026-03-01T14:30:00Z",
    "source": "ha"
  }
}
```

**Not Found Response (404):**

```json
{
  "ok": false,
  "error": "Zone not found"
}
```

#### Python Code Example

```python
def get_zone_example(client: ZoneEditorClient, zone_id: str):
    """Example: Get a specific zone."""
    
    response = client.session.get(
        f'{client.base_url}/api/v1/habitus/zones/{zone_id}'
    )
    
    if response.status_code == 200:
        zone = response.json()['zone']
        print(f"📍 {zone['name']}")
        print(f"   Type: {zone['zone_type']}")
        print(f"   Entities: {len(zone.get('entity_ids', []))}")
        print(f"   Roles: {list(zone.get('entities', {}).keys())}")
    elif response.status_code == 404:
        print(f"⚠️  Zone not found: {zone_id}")
```

---

### PUT /api/v1/habitus/zones/:zone_id

Update a zone.

#### Description

Updates an existing zone with new data. Merges provided fields with existing data.

#### Request Format

**Endpoint:** `PUT /api/v1/habitus/zones/:zone_id`

**Headers:**
```http
Content-Type: application/json
X-Auth-Token: your-api-token
```

**Body:**
```json
{
  "name": "Wohnzimmer Neu",
  "mood_settings": {
    "relax": {"brightness": 50, "color_temp": 2700},
    "social": {"brightness": 70, "color_temp": 3500}
  },
  "entities": {
    "primary_light": "light.wohnzimmer_neu",
    "ambient_light": "light.wohnzimmer_stehlampe"
  }
}
```

**Request Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ❌ No | Zone name |
| `zone_type` | string | ❌ No | Zone type |
| `entity_ids` | array | ❌ No | List of entity IDs |
| `entities` | object | ❌ No | Entity role mappings |
| `mood_settings` | object | ❌ No | Per-mood settings |

#### Response Format

```json
{
  "ok": true,
  "zone": {
    "zone_id": "zone:wohnzimmer",
    "name": "Wohnzimmer Neu",
    ...
  }
}
```

#### EventBus Events

- `zone.updated` - After successful update

#### Python Code Example

```python
def update_zone_example(client: ZoneEditorClient, zone_id: str):
    """Example: Update a zone."""
    
    update_data = {
        'name': 'Wohnzimmer Erweitert',
        'mood_settings': {
            'relax': {'brightness': 45, 'color_temp': 2800},
            'focus': {'brightness': 85, 'color_temp': 4200},
            'social': {'brightness': 70, 'color_temp': 3500}
        }
    }
    
    response = client.session.put(
        f'{client.base_url}/api/v1/habitus/zones/{zone_id}',
        json=update_data
    )
    
    if response.status_code == 200:
        zone = response.json()['zone']
        print(f"✅ Zone updated: {zone['name']}")
        print(f"   Mood settings: {list(zone['mood_settings'].keys())}")
    elif response.status_code == 404:
        print(f"⚠️  Zone not found: {zone_id}")
```

---

### DELETE /api/v1/habitus/zones/:zone_id

Delete a zone.

#### Description

Permanently removes a zone from the system.

#### Request Format

**Endpoint:** `DELETE /api/v1/habitus/zones/:zone_id`

**Headers:**
```http
X-Auth-Token: your-api-token
```

#### Response Format

```json
{
  "ok": true,
  "deleted": "zone:wohnzimmer"
}
```

#### EventBus Events

- `zone.deleted` - After successful deletion

#### Python Code Example

```python
def delete_zone_example(client: ZoneEditorClient, zone_id: str):
    """Example: Delete a zone."""
    
    response = client.session.delete(
        f'{client.base_url}/api/v1/habitus/zones/{zone_id}'
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Zone deleted: {result['deleted']}")
    elif response.status_code == 404:
        print(f"⚠️  Zone not found: {zone_id}")
```

---

### GET /api/v1/habitus/zones/summary

Get a summary of all zones.

#### Description

Returns a condensed summary of all zones including mood and activity data.

#### Request Format

**Endpoint:** `GET /api/v1/habitus/zones/summary`

**Headers:**
```http
X-Auth-Token: your-api-token
```

#### Response Format

```json
{
  "ok": true,
  "zones": [
    {
      "zone_id": "zone:wohnzimmer",
      "name": "Wohnzimmer",
      "entity_count": 4,
      "roles": ["primary_light", "ambient_light", "temperature_sensor", "motion_sensor"],
      "synced_at": "2026-03-01T14:30:00Z",
      "source": "ha"
    },
    {
      "zone_id": "zone:schlafzimmer",
      "name": "Schlafzimmer",
      "entity_count": 3,
      "roles": ["primary_light", "cover", "climate"],
      "synced_at": "2026-03-01T14:30:00Z",
      "source": "ha"
    }
  ],
  "count": 2
}
```

#### Python Code Example

```python
def zones_summary_example(client: ZoneEditorClient):
    """Example: Get zones summary."""
    
    response = client.session.get(
        f'{client.base_url}/api/v1/habitus/zones/summary'
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"📍 Zones Summary ({data['count']} zones)")
        print("-" * 50)
        
        for zone in data['zones']:
            print(f"\n{zone['name']} ({zone['zone_id']})")
            print(f"  Entities: {zone['entity_count']}")
            print(f"  Roles: {', '.join(zone['roles'])}")
            print(f"  Last synced: {zone['synced_at']}")
```

---

## Error Codes

### Standard HTTP Status Codes

| Code | Status | Description |
|------|--------|-------------|
| `200` | OK | Request successful |
| `400` | Bad Request | Invalid request format |
| `401` | Unauthorized | Invalid authentication |
| `403` | Forbidden | Insufficient permissions |
| `404` | Not Found | Zone not found |
| `500` | Internal Server Error | Server error |

### Error Response Format

```json
{
  "ok": false,
  "error": "Error message description"
}
```

---

## Python SDK Examples

### Complete Usage Example

```python
#!/usr/bin/env python3
"""
Zone Editor API - Complete Usage Examples
"""

import requests
from typing import List, Dict, Any, Optional


class ZoneEditorClient:
    """Complete client for Zone Editor API."""
    
    def __init__(self, base_url: str, api_token: str, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.timeout = timeout
        
        self.session = requests.Session()
        self.session.headers.update({
            'X-Auth-Token': api_token,
            'Content-Type': 'application/json'
        })
    
    # ==================== Sync Operations ====================
    
    def sync_zones(
        self,
        zones: List[Dict[str, Any]],
        full_sync: bool = True
    ) -> Dict[str, Any]:
        """Synchronize zones from HA to Core."""
        payload = {
            'zones': zones,
            'full_sync': full_sync
        }
        
        response = self.session.post(
            f'{self.base_url}/api/v1/habitus/zones/sync',
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()
    
    # ==================== List Operations ====================
    
    def list_zones(self, zone_type: str = None) -> Dict[str, Any]:
        """Get all zones with optional type filter."""
        params = {'type': zone_type} if zone_type else {}
        
        response = self.session.get(
            f'{self.base_url}/api/v1/habitus/zones',
            params=params,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()
    
    def get_zone(self, zone_id: str) -> Dict[str, Any]:
        """Get a single zone by ID."""
        # Ensure zone_id has "zone:" prefix
        if not zone_id.startswith('zone:'):
            zone_id = f'zone:{zone_id}'
        
        response = self.session.get(
            f'{self.base_url}/api/v1/habitus/zones/{zone_id}',
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get zones summary."""
        response = self.session.get(
            f'{self.base_url}/api/v1/habitus/zones/summary',
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()
    
    # ==================== CRUD Operations ====================
    
    def update_zone(
        self,
        zone_id: str,
        name: str = None,
        zone_type: str = None,
        entity_ids: List[str] = None,
        entities: Dict[str, str] = None,
        mood_settings: Dict[str, Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Update a zone."""
        if not zone_id.startswith('zone:'):
            zone_id = f'zone:{zone_id}'
        
        payload = {}
        if name:
            payload['name'] = name
        if zone_type:
            payload['zone_type'] = zone_type
        if entity_ids:
            payload['entity_ids'] = entity_ids
        if entities:
            payload['entities'] = entities
        if mood_settings:
            payload['mood_settings'] = mood_settings
        
        response = self.session.put(
            f'{self.base_url}/api/v1/habitus/zones/{zone_id}',
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()
    
    def delete_zone(self, zone_id: str) -> Dict[str, Any]:
        """Delete a zone."""
        if not zone_id.startswith('zone:'):
            zone_id = f'zone:{zone_id}'
        
        response = self.session.delete(
            f'{self.base_url}/api/v1/habitus/zones/{zone_id}',
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()


# ==================== Example Usage ====================

if __name__ == '__main__':
    BASE_URL = 'http://localhost:8123'
    API_TOKEN = 'your-api-token-here'
    
    client = ZoneEditorClient(BASE_URL, API_TOKEN)
    
    print("=" * 60)
    print("Zone Editor API - Usage Examples")
    print("=" * 60)
    
    # 1. Sync zones from HA
    print("\n1. 🔄 Sync Zones from HA")
    print("-" * 40)
    
    zones_to_sync = [
        {
            'zone_id': 'zone:wohnzimmer',
            'name': 'Wohnzimmer',
            'zone_type': 'living',
            'entity_ids': [
                'light.wohnzimmer_hauptlicht',
                'light.wohnzimmer_stehlampe',
                'sensor.wohnzimmer_temperatur',
                'binary_sensor.wohnzimmer_bewegung'
            ],
            'entities': {
                'primary_light': 'light.wohnzimmer_hauptlicht',
                'ambient_light': 'light.wohnzimmer_stehlampe',
                'temperature_sensor': 'sensor.wohnzimmer_temperatur',
                'motion_sensor': 'binary_sensor.wohnzimmer_bewegung'
            },
            'mood_settings': {
                'relax': {'brightness': 40, 'color_temp': 3000},
                'focus': {'brightness': 80, 'color_temp': 4000},
                'active': {'brightness': 100, 'color_temp': 5000}
            }
        },
        {
            'zone_id': 'zone:schlafzimmer',
            'name': 'Schlafzimmer',
            'zone_type': 'bedroom',
            'entity_ids': [
                'light.schlafzimmer_deckenlicht',
                'cover.schlafzimmer_rollo',
                'climate.schlafzimmer'
            ],
            'entities': {
                'primary_light': 'light.schlafzimmer_deckenlicht',
                'cover': 'cover.schlafzimmer_rollo',
                'climate': 'climate.schlafzimmer'
            },
            'mood_settings': {
                'sleep': {'brightness': 10, 'color_temp': 2200},
                'relax': {'brightness': 30, 'color_temp': 2700}
            }
        }
    ]
    
    result = client.sync_zones(zones_to_sync, full_sync=True)
    print(f"✅ Synced {result['synced']} zones")
    
    # 2. List all zones
    print("\n2. 📍 List All Zones")
    print("-" * 40)
    
    zones = client.list_zones()
    print(f"Total zones: {zones['count']}")
    for zone in zones['zones']:
        print(f"  • {zone['name']} ({zone['zone_type']})")
    
    # 3. Get specific zone
    print("\n3. 🔍 Get Specific Zone")
    print("-" * 40)
    
    zone_data = client.get_zone('zone:wohnzimmer')
    zone = zone_data['zone']
    print(f"Zone: {zone['name']}")
    print(f"  Type: {zone['zone_type']}")
    print(f"  Entity count: {len(zone['entity_ids'])}")
    print(f"  Roles: {list(zone['entities'].keys())}")
    
    # 4. Update zone
    print("\n4. ✏️  Update Zone")
    print("-" * 40)
    
    updated = client.update_zone(
        'zone:wohnzimmer',
        mood_settings={
            'relax': {'brightness': 45, 'color_temp': 2800},
            'focus': {'brightness': 85, 'color_temp': 4200},
            'social': {'brightness': 70, 'color_temp': 3500},
            'active': {'brightness': 100, 'color_temp': 5000}
        }
    )
    print(f"✅ Zone updated: {updated['zone']['name']}")
    
    # 5. Get summary
    print("\n5. 📊 Zones Summary")
    print("-" * 40)
    
    summary = client.get_summary()
    for zone in summary['zones']:
        print(f"{zone['name']}: {zone['entity_count']} entities, {len(zone['roles'])} roles")
    
    # 6. Delete zone (example - commented out)
    # print("\n6. 🗑️  Delete Zone")
    # print("-" * 40)
    # result = client.delete_zone('zone:guest')
    # print(f"✅ Deleted: {result['deleted']}")
    
    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)
```

---

## EventBus Integration

The Zone Editor API publishes events to the EventBus for real-time updates:

### Published Events

| Event | Payload | Description |
|-------|---------|-------------|
| `zone.synced` | `{"zone_ids": [...], "count": N}` | After successful sync |
| `zone.updated` | `{"zone_id": "...", "zone": {...}}` | After zone update |
| `zone.deleted` | `{"zone_id": "..."}` | After zone deletion |

### Subscribing to Events

```python
# Example: Subscribe to zone events
def on_zone_event(event):
    print(f"Zone event: {event['topic']}")
    print(f"Data: {event['data']}")

event_bus.subscribe('zone.*', on_zone_event)
```

---

## Storage

Zones are persisted to:

```
/data/habitus_zones.json
```

### Storage Format

```json
{
  "zones": [
    {
      "zone_id": "zone:wohnzimmer",
      "name": "Wohnzimmer",
      ...
    }
  ],
  "updated_at": "2026-03-01T14:30:00Z",
  "count": 2
}
```

---

**Documentation Version:** 1.0.0  
**Last Updated:** 2026-03-01  
**Maintained By:** PilotSuite Core Team

---

## ⚠️ Deprecation Notice (2026-03-22)

This document describes the legacy `/api/v1/habitus/zones/` endpoints which are **deprecated**.

**Current Zone Automation endpoints are at `/api/v1/zone-automation/`:**

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/zone-automation/zones` | GET | List all zone configs |
| `/api/v1/zone-automation/ensure-zones` | POST | Bulk-create zone configs (IDs only) |
| `/api/v1/zone-automation/sync-definitions` | POST | Sync full zone definitions from HA |
| `/api/v1/zone-automation/zones/<zone_id>/entities/read-model` | GET | Deterministic entity read-model for one zone (`?since=<revision>`, `compact=true` for reduced payload) |
| `/api/v1/zone-automation/entities/read-model` | GET | Deterministic read-model for all assignments (`?since=<revision>&deltas=true`, `compact=true`) |
| `/api/v1/zone-automation/module-schemas` | GET | Get schemas for zone modules |
| `/api/v1/zone-automation/zones/<zone_id>/modules/<module_id>` | GET/POST | Per-zone module config |
| `/api/v1/zone-automation/zones/<zone_id>/mode` | PUT | Set automation mode |

See **API_REFERENCE.md** for the complete current endpoint documentation.
