# Config Hardening (P1-003)

Comprehensive configuration hardening for Copilot Core with validation, encryption, secrets management, versioning, and audit logging.

## Features

### 1. Pydantic Validation (`models.py`)

Strict type validation for all configuration objects:

```python
from copilot_core.config import ZoneConfig, SonosConfig

# Automatic validation on creation
zone = ZoneConfig(
    zone_id="area_wohnbereich",  # Validated: lowercase, numbers, underscores, hyphens
    zone_name="Wohnbereich",
    sonos=SonosConfig(
        room_name="Wohnzimmer",  # Validated: no special chars
        volume_default=30,       # Validated: 0-100
        volume_ramp_start=10,    # Validated: must be <= volume_ramp_end
        volume_ramp_end=40,
    ),
    light=LightConfig(
        entities=["light.wohnzimmer"],  # Validated: entity ID format
        brightness_default=80,          # Validated: 0-255
    ),
)

# Extra fields are rejected
zone = ZoneConfig(zone_id="test", invalid_field="rejected")  # Raises ValueError
```

**Validation Rules:**
- Zone IDs: lowercase alphanumeric + underscores/hyphens
- Entity IDs: `domain.entity_name` format
- Volume: 0-100 range
- Brightness: 0-255 range
- Time: HH:MM 24h format
- Repeat patterns: once, daily, weekdays, weekends, custom
- Custom days: 0-6 (Mon-Sun)
- Room names: alphanumeric + spaces, hyphens, underscores

### 2. Encryption for Sensitive Data (`encryption.py`)

Fernet symmetric encryption (AES-128-CBC + HMAC) for secrets:

```python
from copilot_core.config import ConfigEncryption, encrypt_value

# Option 1: Direct encryption
encrypted = encrypt_value("my-api-key", master_secret="your-master-secret")
decrypted = decrypt_value(encrypted, master_secret="your-master-secret")

# Option 2: Encryptor instance
encryptor = ConfigEncryption(master_secret="your-master-secret")
encrypted = encryptor.encrypt("secret-value")
decrypted = encryptor.decrypt(encrypted)
```

**Key Features:**
- PBKDF2 key derivation (100,000 iterations)
- Unique salt per installation
- Versioned ciphertext for key rotation
- Secure salt storage (`.config_master_key.salt`)

**Environment Variable:**
```bash
export CONFIG_MASTER_SECRET="your-secure-master-secret"
```

### 3. Secrets Management

High-level API for encrypted secret storage:

```python
from copilot_core.config import ConfigEncryption, SecretManager

encryptor = ConfigEncryption(master_secret="master-secret")
secrets = SecretManager(encryptor)

# Store (auto-encrypts)
secrets.store("openai_api_key", "sk-...")
secrets.store("spotify_token", "BQC...")

# Retrieve (auto-decrypts)
api_key = secrets.retrieve("openai_api_key")

# Rotate
secrets.rotate_secret("spotify_token", "new-token")

# Delete
secrets.delete("old_secret")
```

### 4. Config Versioning + Rollback (`manager.py`)

Automatic version snapshots and rollback capability:

```python
from copilot_core.config import async_get_config_manager

manager = await async_get_config_manager(hass, master_secret="secret")

# Create version snapshot before changes
version = await manager.create_version_snapshot(
    description="Before major refactor",
    user="admin",
)

# Make changes...
await manager.save_zone(zone, user="admin", reason="Updated config")

# Rollback if needed
await manager.rollback_to_version(
    version=5,
    user="admin",
    reason="Config caused issues",
)

# List available versions
versions = manager.list_versions(limit=10)
for v in versions:
    print(f"v{v.version}: {v.description} ({v.created_at})")

# Cleanup old versions
deleted = await manager.cleanup_old_versions(keep=10)
```

**Version Storage:**
- Location: `/config/clawd/config_versions/v{N}.json`
- Includes: metadata, config snapshot, checksum
- Permissions: 0600 (owner read/write only)

### 5. Audit Logging (`manager.py`)

Complete audit trail for all config changes:

```python
# Query audit log
entries = manager.get_audit_log(
    limit=100,
    action="update",      # Filter: create, update, delete, rollback, validate
    zone_id="wohnbereich", # Filter by zone
    user="admin",          # Filter by user
)

for entry in entries:
    print(f"{entry.timestamp}: {entry.action} by {entry.user}")
    print(f"  Reason: {entry.reason}")
    if entry.old_value:
        print(f"  Old: {entry.old_value}")
    if entry.new_value:
        print(f"  New: {entry.new_value}")

# Export audit log
await manager.export_audit_log("/config/clawd/reports/config_audit.json")
```

**Audited Actions:**
- Zone create/update/delete
- Secret store/rotate/delete
- Version creation
- Rollback operations
- Validation failures

### 6. Git Integration

Automatic git commit hash capture in version metadata:

```python
version = manager.list_versions(limit=1)[0]
print(f"Config version {version.version}")
print(f"Git commit: {version.commit_hash}")
print(f"Checksum: {version.checksum}")
```

## Usage Examples

### Basic Setup

```python
from copilot_core.config import async_get_config_manager, ZoneConfig, SonosConfig

# Initialize
manager = await async_get_config_manager(
    hass,
    workspace="/config/clawd",
    master_secret=os.environ.get("CONFIG_MASTER_SECRET"),
)

# Create version snapshot
await manager.create_version_snapshot(
    description="Initial hardened config setup",
    user="system",
)

# Save zone with validation
zone = ZoneConfig(
    zone_id="area_wohnbereich",
    zone_name="Wohnbereich",
    sonos=SonosConfig(room_name="Wohnzimmer"),
)
await manager.save_zone(zone, user="admin", reason="Initial setup")

# Store encrypted secret
manager.store_secret(
    "spotify_api_key",
    "your-api-key-here",
    user="admin",
    reason="Spotify integration setup",
)
```

### Migration from Cross-Module Config

```python
from copilot_core.config import CrossModuleConfig, ConfigManager

# Old way (still works)
old_config = await async_get_cross_module_config(hass)
zone = old_config.get_zone("wohnbereich")

# New way (with hardening)
manager = await async_get_config_manager(hass, master_secret="...")
zone = manager.get_zone("wohnbereich")

# ZoneConfig is compatible - can migrate gradually
```

### Error Handling

```python
from copilot_core.config import ConfigValidationError, ConfigRollbackError

try:
    zone = ZoneConfig(zone_id="Invalid@ID!")
except ValueError as e:
    print(f"Validation error: {e}")

try:
    await manager.save_zone(invalid_zone)
except ConfigValidationError as e:
    print(f"Save failed: {e.errors}")

try:
    await manager.rollback_to_version(999)
except ConfigRollbackError as e:
    print(f"Rollback failed: {e}")
```

## Architecture

```
copilot_core/config/
├── __init__.py           # Exports
├── models.py             # Pydantic models (validation)
├── encryption.py         # Encryption utilities
├── manager.py            # Config manager (orchestration)
├── cross_module.py       # Legacy cross-module config
├── test_config_hardening.py  # Tests
└── README_HARDENING.md   # This file
```

## Security Considerations

### Master Secret Management

**Recommended:**
```bash
# Environment variable (preferred)
export CONFIG_MASTER_SECRET=$(openssl rand -base64 32)

# Or use secrets manager
CONFIG_MASTER_SECRET=$(op read "op://vault/master-secret")
```

**DO NOT:**
- Commit master secret to git
- Store in plaintext config files
- Share via insecure channels

### Key Rotation

```python
# Rotate encryption key
old_encryptor = ConfigEncryption(master_secret="old-secret", key_version=1)
new_encryptor = ConfigEncryption(master_secret="new-secret", key_version=2)

# Re-encrypt all secrets
for name in secrets.list_secrets():
    plaintext = old_encryptor.decrypt(secrets.retrieve(name, decrypt=False))
    new_encrypted = new_encryptor.encrypt(plaintext)
    secrets.store(name, new_encrypted, encrypt=False)
```

### File Permissions

All sensitive files are created with `0600` permissions:
- `.config_master_key.salt` - Encryption salt
- `config_versions/v{N}.json` - Version snapshots
- Audit log exports

## Testing

```bash
# Run tests
cd /config/clawd
/config/clawd/.venv_smoke_gate/bin/python -m pytest copilot_core/config/test_config_hardening.py -v

# Expected output:
# test_valid_config ... PASSED
# test_invalid_room_name ... PASSED
# test_encrypt_decrypt_roundtrip ... PASSED
# ...
```

## Migration Checklist

- [ ] Set `CONFIG_MASTER_SECRET` environment variable
- [ ] Initialize ConfigManager in main setup
- [ ] Create initial version snapshot
- [ ] Migrate existing secrets to encrypted storage
- [ ] Enable audit logging
- [ ] Test rollback procedure
- [ ] Document master secret recovery process

## Related

- [Cross-Module Config README](README.md) - Original cross-module config documentation
- [P1-003 Task](../../TASKBOARD.md) - Config hardening task tracking
