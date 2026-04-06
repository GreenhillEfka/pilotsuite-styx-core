import pytest
import asyncio
from copilot_core.module_registry import ModuleRegistry

@pytest.mark.asyncio
async def test_module_registry_async_bridge(monkeypatch):
    """Verify async bridge for ModuleRegistry (Slice 140)."""
    registry = ModuleRegistry.get_instance(":memory:")
    
    # Test async set
    success = await registry.set_state_async("presence", "learning")
    assert success is True
    
    # Test async get
    state = await registry.get_state_async("presence")
    assert state == "learning"

if __name__ == "__main__":
    pytest.main([__file__])
