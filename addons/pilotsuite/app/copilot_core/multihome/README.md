# Multi-Home Synchronization Module

## Overview

The Multi-Home Synchronization module enables secure synchronization between multiple PilotSuite instances across different locations (Hauptwohnung, Ferienhaus, Büro).

## Features

- **Secure Synchronization**: Encrypted communication between home instances
- **Unified Control**: Single interface to manage all locations
- **Location-Aware Automations**: Context-specific automations (e.g., "Ferienhaus vorheizen")
- **Conflict Resolution**: Multiple strategies for handling simultaneous changes
- **Configuration Sync**: Synchronize automations, zones, entities, and preferences
- **State Sync**: Real-time synchronization of entity states (climate, lighting, etc.)

## Architecture

```
┌─────────────────┐
│  Hauptwohnung   │ ← Primary Home
│  (Primary)      │
└────────┬────────┘
         │
    ┌────┴────┐
    │  Sync   │
    │ Engine  │
    └────┬────┘
         │
    ┌────┴────────────┐
    │                 │
┌───┴────┐      ┌────┴────┐
│Ferienhaus│    │  Büro   │
│Vacation │      │ Office  │
└─────────┘      └─────────┘
```

## Module Structure

```
copilot_core/multihome/
├── __init__.py          # Package exports
├── sync_engine.py       # Core synchronization engine
├── config_sync.py       # Configuration synchronization
└── state_sync.py        # State synchronization
```

## API Endpoints

All endpoints require authentication via `X-Auth-Token` or `Bearer` token.

### Home Management

- `GET /api/v1/multihome/homes` - List all configured homes
- `GET /api/v1/multihome/homes/<home_id>` - Get home details
- `POST /api/v1/multihome/homes` - Register a new home
- `DELETE /api/v1/multihome/homes/<home_id>` - Unregister a home

### Configuration Sync

- `GET /api/v1/multihome/config/diff/<source>/<target>` - Get config differences
- `POST /api/v1/multihome/config/sync` - Create config sync operation
- `POST /api/v1/multihome/config/sync/<id>/apply` - Apply config sync

### State Sync

- `GET /api/v1/multihome/state/diff/<home1>/<home2>` - Get state differences
- `POST /api/v1/multihome/state/sync` - Create state sync operation
- `POST /api/v1/multihome/state/sync/<id>/apply` - Apply state sync

### Location-Aware Automation

- `POST /api/v1/multihome/location/sync` - Sync location-aware automations
- `POST /api/v1/multihome/climate/preheat` - Preheat vacation home

### Conflict Management

- `GET /api/v1/multihome/conflicts` - List active conflicts
- `POST /api/v1/multihome/conflicts/<id>/resolve` - Resolve a conflict

### Status & Operations

- `GET /api/v1/multihome/status` - Get sync status
- `GET /api/v1/multihome/operations` - List operations
- `POST /api/v1/multihome/operations/<id>/execute` - Execute operation
- `DELETE /api/v1/multihome/operations/cleanup` - Cleanup old operations

### Settings

- `GET /api/v1/multihome/settings` - Get sync settings
- `PUT /api/v1/multihome/settings` - Update sync settings

## Usage Examples

### Register a New Home

```bash
curl -X POST http://localhost:8909/api/v1/multihome/homes \
  -H "X-Auth-Token: your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "ferienhaus",
    "name": "Ferienhaus Ostsee",
    "home_type": "vacation",
    "base_url": "http://192.168.2.100:8123",
    "auth_token": "remote-token",
    "is_primary": false,
    "sync_interval_seconds": 300
  }'
```

### Preheat Vacation Home

```bash
curl -X POST http://localhost:8909/api/v1/multihome/climate/preheat \
  -H "X-Auth-Token: your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "source_home_id": "hauptwohnung",
    "target_home_id": "ferienhaus",
    "climate_entity_id": "climate.living_room"
  }'
```

### Sync Location-Aware Automations

```bash
curl -X POST http://localhost:8909/api/v1/multihome/location/sync \
  -H "X-Auth-Token: your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "source_home_id": "hauptwohnung",
    "target_home_id": "ferienhaus",
    "location_context": "vacation_home"
  }'
```

### Resolve Conflict

```bash
curl -X POST http://localhost:8909/api/v1/multihome/conflicts/conflict-123/resolve \
  -H "X-Auth-Token: your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "resolution": "last_write_wins"
  }'
```

## Conflict Resolution Strategies

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `last_write_wins` | Most recent timestamp wins | Default, general purpose |
| `primary_wins` | Primary home value always wins | Centralized control |
| `merge` | Attempt to merge dict values | Compatible changes |
| `manual` | Require manual intervention | Critical configurations |

## Security

### Encryption

- All inter-home communication is encrypted using HMAC-SHA256 signatures
- Payload encryption uses AES-GCM (production) or base64+signature (development)
- Shared secret configured via `MULTIHOME_SHARED_SECRET` environment variable

### Authentication

- All API endpoints require valid authentication token
- Tokens are validated against configured `auth_token` in options.json
- Support for both `X-Auth-Token` header and `Bearer` token

## Configuration

### Environment Variables

```bash
# Shared secret for encryption (change in production!)
MULTIHOME_SHARED_SECRET=your-secure-secret

# Data directory for sync state
MULTIHOME_DATA_DIR=/data/multihome
```

### Options.json

```json
{
  "multihome": {
    "enabled": true,
    "conflict_resolution_strategy": "last_write_wins",
    "default_sync_interval": 300,
    "data_dir": "/data/multihome"
  }
}
```

## Testing

Run the test suite:

```bash
cd /config/.openclaw/workspace/pilotsuite-styx-core/copilot_core/rootfs/usr/src/app
pytest -v tests/test_multihome_sync.py
```

## Future Enhancements

- [ ] Real-time WebSocket synchronization
- [ ] Bidirectional sync with conflict detection
- [ ] Sync scheduling and automation
- [ ] Bandwidth optimization (delta sync)
- [ ] Multi-master replication support
- [ ] Sync audit logging
- [ ] Performance metrics and monitoring

## Troubleshooting

### Common Issues

1. **Sync fails with authentication error**
   - Verify `auth_token` is configured correctly on both instances
   - Check network connectivity between homes

2. **Conflicts not resolving**
   - Review conflict resolution strategy
   - Check timestamps are synchronized (NTP)

3. **Performance issues**
   - Reduce sync frequency for non-critical data
   - Use selective sync instead of full sync

### Logs

Check application logs for sync-related messages:

```bash
journalctl -u pilotsuite-styx-core -f | grep multihome
```

## License

Part of PilotSuite Styx Core. See main repository for license details.
