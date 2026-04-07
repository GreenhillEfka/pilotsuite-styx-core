"""Tests for the TagRegistry implementation."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from copilot_core.tagging.registry import TagRegistry, TagRegistryError

DATA_PATH = ROOT / "copilot_core" / "data" / "tagging" / "tags.yaml"


def test_registry_loads_default_file():
    registry = TagRegistry.from_file(DATA_PATH)
    tag = registry.get("aicp.role.safety_critical")
    assert tag is not None
    assert tag.namespace == "aicp"
    assert tag.materializes_in_ha is True
    assert tag.ha.label_slug == "aicp_role_safety_critical"


def test_alias_lookup():
    registry = TagRegistry.from_file(DATA_PATH)
    alias_tag = registry.get("aicp.role.critical")
    assert alias_tag is not None
    assert alias_tag.id == "aicp.role.safety_critical"


def test_invalid_tag_payload():
    payload = {
        "schema_version": "0.1",
        "reserved_namespaces": ["sys"],
        "tags": [
            {"id": "invalid", "ha": {"materialize_as_label": True}},
        ],
    }

    try:
        TagRegistry.from_dict(payload)
    except TagRegistryError:
        return
    raise AssertionError("Expected TagRegistryError for invalid id")


if __name__ == "__main__":
    test_registry_loads_default_file()
    test_alias_lookup()
    test_invalid_tag_payload()
    print("All TagRegistry tests passed.")
