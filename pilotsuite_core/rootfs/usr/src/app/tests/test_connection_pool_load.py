"""
Load Test for Connection Pool Manager.

Tests connection pooling efficiency under load:
- 1000 requests to HA and Ollama endpoints
- Measures connection reuse rate
- Target: >90% connection pool efficiency

Author: Clawdya
Version: 1.0.0
Date: 2026-03-02
"""
import asyncio
import time
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import aiohttp

from copilot_core.connection_pool import (
    ConnectionPoolManager,
    get_pool_manager,
    get_ha_session,
    get_ollama_session,
    close_pool,
    get_pool_metrics,
)


class TestConnectionPoolLoadTest:
    """Load tests for connection pool efficiency."""

    @pytest.fixture
    async def pool_manager(self):
        """Create a ConnectionPoolManager instance for load testing."""
        manager = ConnectionPoolManager(
            max_connections=10,
            timeout=30,
            health_check_interval=60,
        )
        yield manager
        # Cleanup
        await manager.close()

    @pytest.fixture
    def mock_response(self):
        """Create a mock aiohttp response."""
        response = MagicMock(spec=aiohttp.ClientResponse)
        response.status = 200
        response.json = AsyncMock(return_value={"status": "ok"})
        response.__aenter__ = AsyncMock(return_value=response)
        response.__aexit__ = AsyncMock(return_value=None)
        return response

    @pytest.fixture
    def mock_session(self, mock_response):
        """Create a mock aiohttp session."""
        session = MagicMock(spec=aiohttp.ClientSession)
        session.closed = False
        session.get = MagicMock(return_value=mock_response)
        session.post = MagicMock(return_value=mock_response)
        return session

    @pytest.mark.asyncio
    async def test_ha_load_1000_requests(self, pool_manager, mock_session, mock_response):
        """
        Load test: 1000 HA requests with connection pooling.
        
        Target: >90% connection reuse rate.
        """
        # Mock session creation
        pool_manager._ha_session = mock_session
        
        # Track request timing
        start_time = time.monotonic()
        
        # Execute 1000 requests
        for i in range(1000):
            session = await pool_manager.get_ha_session()
            pool_manager.record_ha_request(reused=True)
            
            # Simulate request
            async with session.get("http://ha:8123/api/states") as resp:
                await resp.json()
        
        elapsed_time = time.monotonic() - start_time
        
        # Get metrics
        metrics = pool_manager.get_metrics()
        ha_metrics = metrics["ha_pool"]
        
        print(f"\n=== HA Load Test Results (1000 requests) ===")
        print(f"Total time: {elapsed_time:.2f}s")
        print(f"Requests/sec: {1000/elapsed_time:.1f}")
        print(f"Requests total: {ha_metrics['requests_total']}")
        print(f"Connections reused: {ha_metrics['connections_reused']}")
        print(f"Reuse rate: {ha_metrics['reuse_rate_pct']}%")
        print(f"Session active: {ha_metrics['session_active']}")
        
        # Assert >90% efficiency
        assert ha_metrics["requests_total"] == 1000
        assert ha_metrics["reuse_rate_pct"] >= 90.0, \
            f"Connection reuse rate {ha_metrics['reuse_rate_pct']}% < 90%"
        assert ha_metrics["session_active"] is True

    @pytest.mark.asyncio
    async def test_ollama_load_1000_requests(self, pool_manager, mock_session, mock_response):
        """
        Load test: 1000 Ollama requests with connection pooling.
        
        Target: >90% connection reuse rate.
        """
        # Mock session creation
        pool_manager._ollama_session = mock_session
        
        # Track request timing
        start_time = time.monotonic()
        
        # Execute 1000 requests
        for i in range(1000):
            session = await pool_manager.get_ollama_session()
            pool_manager.record_ollama_request(reused=True)
            
            # Simulate request
            async with session.post(
                "http://ollama:11434/api/generate",
                json={"model": "llama2", "prompt": "test"}
            ) as resp:
                await resp.json()
        
        elapsed_time = time.monotonic() - start_time
        
        # Get metrics
        metrics = pool_manager.get_metrics()
        ollama_metrics = metrics["ollama_pool"]
        
        print(f"\n=== Ollama Load Test Results (1000 requests) ===")
        print(f"Total time: {elapsed_time:.2f}s")
        print(f"Requests/sec: {1000/elapsed_time:.1f}")
        print(f"Requests total: {ollama_metrics['requests_total']}")
        print(f"Connections reused: {ollama_metrics['connections_reused']}")
        print(f"Reuse rate: {ollama_metrics['reuse_rate_pct']}%")
        print(f"Session active: {ollama_metrics['session_active']}")
        
        # Assert >90% efficiency
        assert ollama_metrics["requests_total"] == 1000
        assert ollama_metrics["reuse_rate_pct"] >= 90.0, \
            f"Connection reuse rate {ollama_metrics['reuse_rate_pct']}% < 90%"
        assert ollama_metrics["session_active"] is True

    @pytest.mark.asyncio
    async def test_concurrent_load_test(self, pool_manager, mock_session, mock_response):
        """
        Concurrent load test: 1000 requests with 10 concurrent workers.
        
        Tests thread-safety and connection pool stability under concurrent load.
        """
        # Mock session creation
        pool_manager._ha_session = mock_session
        
        async def make_requests(worker_id: int, count: int):
            """Worker that makes multiple requests."""
            for i in range(count):
                session = await pool_manager.get_ha_session()
                pool_manager.record_ha_request(reused=True)
                
                async with session.get("http://ha:8123/api/states") as resp:
                    await resp.json()
                
                # Small delay to simulate real work
                await asyncio.sleep(0.001)
        
        # Track request timing
        start_time = time.monotonic()
        
        # Create 10 workers, each making 100 requests = 1000 total
        num_workers = 10
        requests_per_worker = 100
        
        tasks = [
            make_requests(worker_id, requests_per_worker)
            for worker_id in range(num_workers)
        ]
        
        await asyncio.gather(*tasks)
        
        elapsed_time = time.monotonic() - start_time
        
        # Get metrics
        metrics = pool_manager.get_metrics()
        ha_metrics = metrics["ha_pool"]
        
        print(f"\n=== Concurrent Load Test Results (1000 requests, 10 workers) ===")
        print(f"Total time: {elapsed_time:.2f}s")
        print(f"Requests/sec: {1000/elapsed_time:.1f}")
        print(f"Requests total: {ha_metrics['requests_total']}")
        print(f"Connections reused: {ha_metrics['connections_reused']}")
        print(f"Reuse rate: {ha_metrics['reuse_rate_pct']}%")
        print(f"Session active: {ha_metrics['session_active']}")
        
        # Assert >90% efficiency
        assert ha_metrics["requests_total"] == 1000
        assert ha_metrics["reuse_rate_pct"] >= 90.0, \
            f"Connection reuse rate {ha_metrics['reuse_rate_pct']}% < 90%"
        assert ha_metrics["session_active"] is True

    @pytest.mark.asyncio
    async def test_global_pool_load_test(self, mock_session, mock_response):
        """
        Load test using global pool manager.
        
        Tests the singleton pool manager under load.
        """
        # Ensure clean state
        await close_pool()
        
        # Get global pool
        pool = await get_pool_manager()
        pool._ha_session = mock_session
        
        # Execute 1000 requests
        for i in range(1000):
            async with get_ha_session() as session:
                async with session.get("http://ha:8123/api/states") as resp:
                    await resp.json()
        
        # Get metrics
        metrics = get_pool_metrics()
        ha_metrics = metrics["ha_pool"]
        
        print(f"\n=== Global Pool Load Test Results (1000 requests) ===")
        print(f"Requests total: {ha_metrics['requests_total']}")
        print(f"Connections reused: {ha_metrics['connections_reused']}")
        print(f"Reuse rate: {ha_metrics['reuse_rate_pct']}%")
        
        # Assert >90% efficiency
        assert ha_metrics["requests_total"] == 1000
        assert ha_metrics["reuse_rate_pct"] >= 90.0
        
        # Cleanup
        await close_pool()

    @pytest.mark.asyncio
    async def test_mixed_ha_ollama_load(self, pool_manager, mock_session, mock_response):
        """
        Mixed load test: 500 HA + 500 Ollama requests.
        
        Tests isolation between HA and Ollama pools.
        """
        # Mock both sessions
        pool_manager._ha_session = mock_session
        pool_manager._ollama_session = mock_session
        
        # Execute 500 HA requests
        for i in range(500):
            session = await pool_manager.get_ha_session()
            pool_manager.record_ha_request(reused=True)
            async with session.get("http://ha:8123/api/states") as resp:
                await resp.json()
        
        # Execute 500 Ollama requests
        for i in range(500):
            session = await pool_manager.get_ollama_session()
            pool_manager.record_ollama_request(reused=True)
            async with session.post("http://ollama:11434/api/generate") as resp:
                await resp.json()
        
        # Get metrics
        metrics = pool_manager.get_metrics()
        ha_metrics = metrics["ha_pool"]
        ollama_metrics = metrics["ollama_pool"]
        
        print(f"\n=== Mixed Load Test Results ===")
        print(f"HA requests: {ha_metrics['requests_total']}, reuse: {ha_metrics['reuse_rate_pct']}%")
        print(f"Ollama requests: {ollama_metrics['requests_total']}, reuse: {ollama_metrics['reuse_rate_pct']}%")
        
        # Assert both pools >90% efficiency
        assert ha_metrics["requests_total"] == 500
        assert ollama_metrics["requests_total"] == 500
        assert ha_metrics["reuse_rate_pct"] >= 90.0
        assert ollama_metrics["reuse_rate_pct"] >= 90.0


class TestConnectionPoolPerformance:
    """Performance benchmarks for connection pooling."""

    @pytest.fixture
    async def pool_manager(self):
        """Create pool manager for performance tests."""
        manager = ConnectionPoolManager(
            max_connections=20,
            timeout=30,
            health_check_interval=60,
        )
        yield manager
        await manager.close()

    @pytest.mark.asyncio
    async def test_session_creation_overhead(self, pool_manager):
        """
        Benchmark: Session creation vs reuse.
        
        Measures the overhead of creating new sessions vs reusing pooled sessions.
        """
        # Measure session creation time
        start = time.monotonic()
        for i in range(100):
            connector = await pool_manager._create_connector()
            session = await pool_manager._create_session(connector)
            await session.close()
            await connector.close()
        creation_time = time.monotonic() - start
        
        # Measure session reuse time
        session = await pool_manager.get_ha_session()
        start = time.monotonic()
        for i in range(100):
            reused_session = await pool_manager.get_ha_session()
            assert reused_session is session  # Same session
        reuse_time = time.monotonic() - start
        
        print(f"\n=== Session Performance Benchmark ===")
        print(f"100x Session creation: {creation_time:.3f}s ({creation_time*10:.1f}ms per session)")
        print(f"100x Session reuse: {reuse_time:.3f}s ({reuse_time*10:.1f}ms per request)")
        print(f"Speedup: {creation_time/max(reuse_time, 0.0001):.1f}x faster with pooling")
        
        # Reuse should be significantly faster
        assert reuse_time < creation_time, "Session reuse should be faster than creation"
