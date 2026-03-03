"""
HA Add-on Configuration Conformance Tests

Tests for validating config.yaml and manifest.json against
Home Assistant Add-on requirements.

Reference: https://developers.home-assistant.io/docs/add-ons/configuration/
"""

import json
import os
import re
import pytest
from pathlib import Path


# Get the root path of the copilot_core addon
# Path from test file: tests/ -> ../ -> copilot_core/rootfs/usr/src/app
# But config.yaml and manifest.json are in copilot_core/ (parent of rootfs)
ADDON_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent  # Go up to copilot_core/
CONFIG_YAML_PATH = ADDON_ROOT / "config.yaml"
MANIFEST_JSON_PATH = ADDON_ROOT / "manifest.json"


class TestHAAddonConfig:
    """Test HA Add-on configuration conformance."""

    @pytest.fixture
    def manifest(self):
        """Load manifest.json."""
        with open(MANIFEST_JSON_PATH, 'r') as f:
            return json.load(f)

    @pytest.fixture
    def config(self):
        """Load config.yaml (parsed as dict)."""
        import yaml
        with open(CONFIG_YAML_PATH, 'r') as f:
            return yaml.safe_load(f)

    def test_manifest_exists(self):
        """Test manifest.json exists."""
        assert MANIFEST_JSON_PATH.exists(), f"manifest.json not found at {MANIFEST_JSON_PATH}"

    def test_config_exists(self):
        """Test config.yaml exists."""
        assert CONFIG_YAML_PATH.exists(), f"config.yaml not found at {CONFIG_YAML_PATH}"

    def test_manifest_valid_json(self, manifest):
        """Test manifest.json is valid JSON."""
        assert isinstance(manifest, dict)
        assert len(manifest) > 0

    def test_required_fields(self, manifest):
        """Test all required HA Add-on fields are present."""
        required_fields = ['name', 'version', 'slug', 'description', 'arch', 'startup']
        missing = [f for f in required_fields if f not in manifest]
        assert not missing, f"Missing required fields: {missing}"

    def test_version_format(self, manifest):
        """Test version follows semantic versioning (X.Y.Z)."""
        version = manifest.get('version', '')
        assert re.match(r'^\d+\.\d+\.\d+$', version), f"Invalid version format: {version}"

    def test_architecture_valid(self, manifest):
        """Test architecture values are valid."""
        valid_arch = ['amd64', 'aarch64', 'armhf', 'armv7', 'i386']
        arch = manifest.get('arch', [])
        assert len(arch) > 0, "No architectures specified"
        assert all(a in valid_arch for a in arch), f"Invalid architecture: {arch}"

    def test_startup_value(self, manifest):
        """Test startup value is valid."""
        valid_startup = ['application', 'services', 'system', 'once']
        startup = manifest.get('startup')
        assert startup in valid_startup, f"Invalid startup value: {startup}"

    def test_slug_format(self, manifest):
        """Test slug follows HA naming conventions."""
        slug = manifest.get('slug', '')
        assert re.match(r'^[a-z0-9_]+$', slug), f"Invalid slug format: {slug}"

    def test_ingress_consistency(self, manifest):
        """Test ingress configuration is consistent."""
        if manifest.get('ingress'):
            assert 'ingress_port' in manifest, "Ingress enabled but no ingress_port defined"
            assert isinstance(manifest['ingress_port'], int), "ingress_port must be integer"
            assert 1 <= manifest['ingress_port'] <= 65535, "ingress_port out of range"

    def test_options_schema_match(self, manifest):
        """Test options and schema keys match."""
        opts = set(manifest.get('options', {}).keys())
        schema = set(manifest.get('schema', {}).keys())
        assert opts == schema, f"Options/Schema mismatch: opts={opts}, schema={schema}"

    def test_schema_types_valid(self, manifest):
        """Test schema type definitions are valid."""
        valid_types = [
            'str', 'string', 'int', 'integer', 'float', 'bool', 'boolean',
            'password', 'email', 'url', 'port', 'device', 'folder', 'list',
            'select', 'multi', 'timespan', 'icon', 'color', 'date', 'datetime'
        ]
        schema = manifest.get('schema', {})
        for key, type_def in schema.items():
            # Extract base type (ignore modifiers like ?, !, list(), etc.)
            base_type = re.match(r'^([a-z_]+)', type_def.lower())
            if base_type:
                assert base_type.group(1) in valid_types, f"Invalid schema type for {key}: {type_def}"

    def test_version_sync(self, manifest):
        """Test version is synced between manifest and VERSION file."""
        version_file = ADDON_ROOT / "VERSION"
        if version_file.exists():
            with open(version_file, 'r') as f:
                file_version = f.read().strip()
            assert manifest.get('version') == file_version, \
                f"Version mismatch: manifest={manifest.get('version')}, file={file_version}"

    def test_config_yaml_sync(self, config, manifest):
        """Test config.yaml and manifest.json are in sync."""
        # Check version
        assert config.get('version') == manifest.get('version'), \
            f"Version mismatch between config.yaml and manifest.json"
        
        # Check slug
        assert config.get('slug') == manifest.get('slug'), \
            f"Slug mismatch between config.yaml and manifest.json"
        
        # Check options keys
        config_opts = set(config.get('options', {}).keys())
        manifest_opts = set(manifest.get('options', {}).keys())
        assert config_opts == manifest_opts, \
            f"Options mismatch: config={config_opts}, manifest={manifest_opts}"

    def test_ports_format(self, manifest):
        """Test ports definition format."""
        ports = manifest.get('ports', {})
        if ports:
            for port_key, port_value in ports.items():
                # Key should be like "8909/tcp"
                assert '/' in port_key, f"Invalid port key format: {port_key}"
                # Value should be integer or null
                assert port_value is None or isinstance(port_value, int), \
                    f"Port value must be integer or null: {port_value}"

    def test_map_format(self, manifest):
        """Test map (volume mounts) format."""
        map_volumes = manifest.get('map', [])
        valid_mounts = ['config', 'ssl', 'addons', 'backup', 'share', 'media', 'data']
        for mount in map_volumes:
            # Format: "name:access" where access is optional (rw/ro)
            parts = mount.split(':')
            assert len(parts) <= 2, f"Invalid map format: {mount}"
            mount_name = parts[0]
            assert mount_name in valid_mounts, f"Invalid mount name: {mount_name}"
            if len(parts) == 2:
                assert parts[1] in ['rw', 'ro'], f"Invalid access mode: {parts[1]}"


class TestConfigOptions:
    """Test configuration options validity."""

    @pytest.fixture
    def manifest(self):
        """Load manifest.json."""
        with open(MANIFEST_JSON_PATH, 'r') as f:
            return json.load(f)

    def test_auth_token_optional(self, manifest):
        """Test auth_token is optional (has ? modifier)."""
        schema = manifest.get('schema', {})
        auth_schema = schema.get('auth_token', '')
        assert '?' in auth_schema, "auth_token should be optional (?)"

    def test_log_level_options(self, manifest):
        """Test log_level has valid options."""
        schema = manifest.get('schema', {})
        log_schema = schema.get('log_level', '')
        # Should be a list type with valid levels
        assert 'list' in log_schema.lower() or 'select' in log_schema.lower(), \
            f"log_level should be list/select: {log_schema}"

    def test_conversation_options_present(self, manifest):
        """Test conversation-related options are present."""
        options = manifest.get('options', {})
        required_conv_opts = [
            'conversation_ollama_url',
            'conversation_ollama_model',
            'conversation_enabled'
        ]
        missing = [opt for opt in required_conv_opts if opt not in options]
        assert not missing, f"Missing conversation options: {missing}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
