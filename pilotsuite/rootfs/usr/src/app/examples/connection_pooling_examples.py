"""
Connection Pooling Usage Examples

This file demonstrates how to use the connection pool in various scenarios.
Copy these patterns into your code.
"""

# =============================================================================
# Example 1: Basic HA API Call
# =============================================================================

from copilot_core.connection_pool import get_ha_session


async def get_all_states():
    """Fetch all Home Assistant states using pooled connection."""
    async with get_ha_session() as session:
        async with session.get('http://homeassistant:8123/api/states') as resp:
            return await resp.json()


# =============================================================================
# Example 2: Ollama API Call
# =============================================================================

from copilot_core.connection_pool import get_ollama_session


async def generate_text(prompt: str, model: str = "llama2"):
    """Generate text using Ollama with pooled connection."""
    async with get_ollama_session() as session:
        async with session.post(
            'http://ollama:11434/api/generate',
            json={"model": model, "prompt": prompt, "stream": False}
        ) as resp:
            return await resp.json()


# =============================================================================
# Example 3: Multiple Sequential Calls (Session Reuse)
# =============================================================================

from copilot_core.connection_pool import get_ha_session


async def fetch_multiple_endpoints():
    """Fetch multiple endpoints reusing the same session."""
    async with get_ha_session() as session:
        # All these calls reuse the same session
        async with session.get('http://homeassistant:8123/api/states') as resp1:
            states = await resp1.json()
        
        async with session.get('http://homeassistant:8123/api/services') as resp2:
            services = await resp2.json()
        
        async with session.get('http://homeassistant:8123/api/config') as resp3:
            config = await resp3.json()
        
        return {"states": states, "services": services, "config": config}


# =============================================================================
# Example 4: Error Handling with Pooling
# =============================================================================

import logging
from copilot_core.connection_pool import get_ha_session

logger = logging.getLogger(__name__)


async def safe_ha_call(url: str):
    """Make HA call with proper error handling."""
    try:
        async with get_ha_session() as session:
            async with session.get(test_url) as resp:
                resp.raise_for_status()
                return await resp.json()
    except Exception as e:
        logger.error(f"HA call failed: {e}")
        raise


# =============================================================================
# Example 5: Health Checks
# =============================================================================

from copilot_core.connection_pool import get_pool_manager


async def check_all_services():
    """Check health of all pooled services."""
    pool = await get_pool_manager()
    
    ha_healthy = await pool.check_ha_health('http://homeassistant:8123')
    ollama_healthy = await pool.check_ollama_health('http://ollama:11434')
    
    return {
        "ha": ha_healthy,
        "ollama": ollama_healthy,
        "all_healthy": ha_healthy and ollama_healthy
    }


# =============================================================================
# Example 6: Metrics Collection
# =============================================================================

from copilot_core.connection_pool import get_pool_metrics


def log_pool_metrics():
    """Log current pool metrics."""
    metrics = get_pool_metrics()
    
    logger.info(f"HA Pool: {metrics['ha_pool']['requests_total']} requests, "
                f"{metrics['ha_pool']['reuse_rate_pct']}% reuse rate")
    logger.info(f"Ollama Pool: {metrics['ollama_pool']['requests_total']} requests, "
                f"{metrics['ollama_pool']['reuse_rate_pct']}% reuse rate")


# =============================================================================
# Example 7: Migration Pattern - Replace Direct Session Creation
# =============================================================================

# BEFORE (old code):
# async def old_way():
#     import aiohttp
#     async with aiohttp.ClientSession() as session:
#         async with session.get(test_url) as resp:
#             return await resp.json()

# AFTER (with pooling):
async def new_way():
    from copilot_core.connection_pool import get_ha_session
    async with get_ha_session() as session:
        async with session.get(test_url) as resp:
            return await resp.json()


# =============================================================================
# Example 8: Custom Session Configuration
# =============================================================================

from copilot_core.connection_pool import ConnectionPoolManager


async def custom_pool_example():
    """Example with custom pool configuration."""
    # Create custom pool manager
    custom_pool = ConnectionPoolManager(
        max_connections=50,  # Larger pool
        timeout=120,  # Longer timeout
        health_check_interval=30  # More frequent health checks
    )
    
    # Use custom pool
    session = await custom_pool.get_ha_session()
    async with session.get('http://homeassistant:8123/api/states') as resp:
        data = await resp.json()
    
    # Cleanup
    await custom_pool.close()


# =============================================================================
# Example 9: Integration with HomeAssistant Client
# =============================================================================

from copilot_core.homeassistant.client import HomeAssistantClient, HAConnectionConfig


async def ha_client_with_pooling():
    """Example: Use HA client (which has its own pooling)."""
    config = HAConnectionConfig(
        base_url="http://homeassistant:8123",
        access_token="your_token_here",
        timeout_seconds=10.0
    )
    
    client = HomeAssistantClient(config)
    
    # Test connection
    status = await client.test_connection()
    print(f"Connected: {status.connected}")
    
    # Make API call
    states = await client.get_states()
    
    # Cleanup
    await client.close()


# =============================================================================
# Example 10: Application Shutdown
# =============================================================================

from copilot_core.connection_pool import close_pool


async def shutdown_app():
    """Properly shutdown application with pool cleanup."""
    # ... other cleanup ...
    
    # Close connection pool
    await close_pool()
    
    # ... more cleanup ...
