"""
Tests for Connection Management Module.

Test coverage for connections.py:
- HAConnection and OllamaConnection classes
- Connection status tracking
- High-level API methods
- Metrics collection
- Graceful shutdown

Author: Clawdya
Version: 1.0.0
Date: 2026-03-02
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp

from copilot_core.connections import (
    ConnectionConfig,
    ConnectionStatus,
    HAConnection,
    OllamaConnection,
    get_ha_connection,
    get_ollama_connection,
    close_all_connections,
    get_connection_metrics,
    ha_connection,
    ollama_connection,
)


@pytest.fixture
def connection_config():
    """Create a ConnectionConfig instance."""
    return ConnectionConfig(
        ha_base_url="http://test-ha:8123",
        ha_access_token="test-token",
        ollama_base_url="http://test-ollama:11434",
        max_connections=5,
    )


@pytest.fixture
def mock_response():
    """Create a mock aiohttp response."""
    response = MagicMock(spec=aiohttp.ClientResponse)
    response.status = 200
    response.json = AsyncMock(return_value={"status": "ok"})
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    response.raise_for_status = MagicMock()
    return response


@pytest.fixture
def mock_session(mock_response):
    """Create a mock aiohttp session."""
    session = MagicMock(spec=aiohttp.ClientSession)
    session.closed = False
    session.get = MagicMock(return_value=mock_response)
    session.post = MagicMock(return_value=mock_response)
    return session


class TestConnectionConfig:
    """Tests for ConnectionConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ConnectionConfig()
        
        assert config.ha_base_url == "http://homeassistant:8123"
        assert config.ha_access_token == ""
        assert config.ha_timeout == 30.0
        assert config.ollama_base_url == "http://ollama:11434"
        assert config.ollama_timeout == 60.0
        assert config.max_connections == 10

    def test_custom_values(self, connection_config):
        """Test custom configuration values."""
        assert connection_config.ha_base_url == "http://test-ha:8123"
        assert connection_config.ha_access_token == "test-token"
        assert connection_config.max_connections == 5


class TestConnectionStatus:
    """Tests for ConnectionStatus dataclass."""

    def test_default_values(self):
        """Test default status values."""
        status = ConnectionStatus()
        
        assert status.connected is False
        assert status.base_url == ""
        assert status.last_error is None
        assert status.last_success is None
        assert status.response_time_ms is None


class TestHAConnection:
    """Tests for HAConnection class."""

    @pytest.mark.asyncio
    async def test_init(self, connection_config):
        """Test HAConnection initialization."""
        conn = HAConnection(connection_config)
        
        assert conn.config is connection_config
        assert conn._session is None
        assert conn._status.connected is False

    @pytest.mark.asyncio
    async def test_connect_success(self, connection_config, mock_session, mock_response):
        """Test successful HA connection."""
        conn = HAConnection(connection_config)
        
        with patch('copilot_core.connections.get_pool_manager') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_pool.get_ha_session = AsyncMock(return_value=mock_session)
            mock_get_pool.return_value = mock_pool
            
            await conn.connect()
            
            assert conn._status.connected is True
            assert conn._status.base_url == "http://test-ha:8123"
            assert conn._session is mock_session

    @pytest.mark.asyncio
    async def test_connect_failure(self, connection_config, mock_session):
        """Test failed HA connection."""
        conn = HAConnection(connection_config)
        
        # Mock session.get to raise exception
        mock_response = MagicMock(spec=aiohttp.ClientResponse)
        mock_response.__aenter__ = AsyncMock(side_effect=Exception("Connection refused"))
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = MagicMock(return_value=mock_response)
        
        with patch('copilot_core.connections.get_pool_manager') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_pool.get_ha_session = AsyncMock(return_value=mock_session)
            mock_get_pool.return_value = mock_pool
            
            await conn.connect()
            
            assert conn._status.connected is False
            assert conn._status.last_error is not None

    @pytest.mark.asyncio
    async def test_get_request(self, connection_config, mock_session, mock_response):
        """Test HA GET request."""
        conn = HAConnection(connection_config)
        conn._session = mock_session
        
        result = await conn.get("/api/states")
        
        assert result == {"status": "ok"}
        mock_session.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_request(self, connection_config, mock_session, mock_response):
        """Test HA POST request."""
        conn = HAConnection(connection_config)
        conn._session = mock_session
        
        data = {"service": "light.turn_on"}
        result = await conn.post("/api/services/homeassistant/turn_on", data=data)
        
        assert result == {"status": "ok"}
        mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_status_property(self, connection_config):
        """Test HA connection status property."""
        conn = HAConnection(connection_config)
        
        status = conn.status
        
        assert isinstance(status, ConnectionStatus)
        assert status.connected is False

    @pytest.mark.asyncio
    async def test_close(self, connection_config, mock_session):
        """Test HA connection close."""
        conn = HAConnection(connection_config)
        conn._session = mock_session
        conn._status.connected = True
        
        await conn.close()
        
        assert conn._status.connected is False


class TestOllamaConnection:
    """Tests for OllamaConnection class."""

    @pytest.mark.asyncio
    async def test_init(self, connection_config):
        """Test OllamaConnection initialization."""
        conn = OllamaConnection(connection_config)
        
        assert conn.config is connection_config
        assert conn._session is None
        assert conn._status.connected is False

    @pytest.mark.asyncio
    async def test_connect_success(self, connection_config, mock_session, mock_response):
        """Test successful Ollama connection."""
        conn = OllamaConnection(connection_config)
        
        with patch('copilot_core.connections.get_pool_manager') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_pool.get_ollama_session = AsyncMock(return_value=mock_session)
            mock_get_pool.return_value = mock_pool
            
            await conn.connect()
            
            assert conn._status.connected is True
            assert conn._status.base_url == "http://test-ollama:11434"

    @pytest.mark.asyncio
    async def test_generate(self, connection_config, mock_session, mock_response):
        """Test Ollama generate request."""
        conn = OllamaConnection(connection_config)
        conn._session = mock_session
        
        result = await conn.generate(model="llama2", prompt="Hello")
        
        assert result == {"status": "ok"}
        mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat(self, connection_config, mock_session, mock_response):
        """Test Ollama chat request."""
        conn = OllamaConnection(connection_config)
        conn._session = mock_session
        
        messages = [{"role": "user", "content": "Hello"}]
        result = await conn.chat(model="llama2", messages=messages)
        
        assert result == {"status": "ok"}
        mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_models(self, connection_config, mock_session):
        """Test Ollama list models."""
        conn = OllamaConnection(connection_config)
        conn._session = mock_session
        
        # Mock response with models
        mock_response = MagicMock(spec=aiohttp.ClientResponse)
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"models": [{"name": "llama2"}]})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = MagicMock(return_value=mock_response)
        
        models = await conn.list_models()
        
        assert len(models) == 1
        assert models[0]["name"] == "llama2"


class TestGlobalConnections:
    """Tests for global connection functions."""

    @pytest.mark.asyncio
    async def test_get_ha_connection_singleton(self):
        """Test get_ha_connection returns singleton."""
        # Clean up first
        await close_all_connections()
        
        conn1 = await get_ha_connection()
        conn2 = await get_ha_connection()
        
        assert conn1 is conn2
        
        await close_all_connections()

    @pytest.mark.asyncio
    async def test_get_ollama_connection_singleton(self):
        """Test get_ollama_connection returns singleton."""
        await close_all_connections()
        
        conn1 = await get_ollama_connection()
        conn2 = await get_ollama_connection()
        
        assert conn1 is conn2
        
        await close_all_connections()

    @pytest.mark.asyncio
    async def test_close_all_connections(self):
        """Test closing all connections."""
        await get_ha_connection()
        await get_ollama_connection()
        
        await close_all_connections()
        
        metrics = get_connection_metrics()
        assert metrics["ha_connection"]["connected"] is False
        assert metrics["ollama_connection"]["connected"] is False


class TestConnectionContextManagers:
    """Tests for connection context managers."""

    @pytest.mark.asyncio
    async def test_ha_connection_context_manager(self):
        """Test HA connection context manager."""
        await close_all_connections()
        
        async with ha_connection() as conn:
            assert isinstance(conn, HAConnection)
        
        await close_all_connections()

    @pytest.mark.asyncio
    async def test_ollama_connection_context_manager(self):
        """Test Ollama connection context manager."""
        await close_all_connections()
        
        async with ollama_connection() as conn:
            assert isinstance(conn, OllamaConnection)
        
        await close_all_connections()


class TestConnectionMetrics:
    """Tests for connection metrics."""

    @pytest.mark.asyncio
    async def test_get_connection_metrics(self):
        """Test getting connection metrics."""
        await close_all_connections()
        
        metrics = get_connection_metrics()
        
        assert "ha_connection" in metrics
        assert "ollama_connection" in metrics
        assert "pool" in metrics
        assert metrics["ha_connection"]["connected"] is False
        assert metrics["ollama_connection"]["connected"] is False

    @pytest.mark.asyncio
    async def test_metrics_with_active_connections(self):
        """Test metrics with active connections."""
        await close_all_connections()
        
        # Get connections (they may fail to connect without real servers)
        ha_conn = await get_ha_connection()
        ollama_conn = await get_ollama_connection()
        
        metrics = get_connection_metrics()
        
        # Check that metrics structure is correct
        assert "ha_connection" in metrics
        assert "ollama_connection" in metrics
        assert "pool" in metrics
        
        # Connections may not be actually connected without real servers
        # Just verify the structure is correct
        assert isinstance(metrics["ha_connection"], dict)
        assert isinstance(metrics["ollama_connection"], dict)
        
        await close_all_connections()
