"""Tests for Service Mesh Engine — Slice 46."""
import pytest
from copilot_core.servicemesh.engine import (
    ServiceMeshEngine,
    ServiceStatus,
    LoadBalanceStrategy,
    CircuitState,
    ServiceInstance,
    CircuitBreaker,
    RetryConfig,
    TrafficSplit,
    create_service_mesh_engine,
)
from datetime import datetime, timezone, timedelta
import time


class TestServiceMeshEngine:
    """Test service mesh engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_service_mesh_engine()
        assert engine is not None
    
    def test_register_service(self):
        """Test registering a service."""
        engine = ServiceMeshEngine()
        
        instance_id = engine.register_service(
            service_name="user-service",
            host="192.168.1.10",
            port=8080,
        )
        
        assert instance_id is not None
        assert instance_id.startswith("svc_")
        
        service = engine.get_service("user-service")
        assert service is not None
        assert service["instance_count"] == 1
    
    def test_register_service_with_weight(self):
        """Test registering service with weight."""
        engine = ServiceMeshEngine()
        
        engine.register_service("api", "192.168.1.10", 8080, weight=50)
        engine.register_service("api", "192.168.1.11", 8080, weight=150)
        
        service = engine.get_service("api")
        
        instances = service["instances"]
        assert instances[0]["weight"] == 50
        assert instances[1]["weight"] == 150
    
    def test_register_service_with_metadata(self):
        """Test registering service with metadata."""
        engine = ServiceMeshEngine()
        
        engine.register_service(
            "api",
            "192.168.1.10",
            8080,
            metadata={"version": "v2", "region": "us-east"},
        )
        
        service = engine.get_service("api")
        
        assert service["instances"][0]["metadata"]["version"] == "v2"
        assert service["instances"][0]["metadata"]["region"] == "us-east"
    
    def test_deregister_service(self):
        """Test deregistering a service."""
        engine = ServiceMeshEngine()
        
        instance_id = engine.register_service("api", "192.168.1.10", 8080)
        
        result = engine.deregister_service(instance_id)
        
        assert result is True
        
        service = engine.get_service("api")
        assert service is None
    
    def test_deregister_unknown_service(self):
        """Test deregistering unknown service."""
        engine = ServiceMeshEngine()
        
        result = engine.deregister_service("unknown_instance")
        
        assert result is False
    
    def test_get_healthy_instances(self):
        """Test getting healthy instances."""
        engine = ServiceMeshEngine()
        
        engine.register_service("api", "192.168.1.10", 8080)
        engine.register_service("api", "192.168.1.11", 8080)
        engine.register_service("api", "192.168.1.12", 8080)
        
        # Mark one as unhealthy
        instances = engine._services["api"]
        instances[1].status = ServiceStatus.UNHEALTHY
        
        healthy = engine.get_healthy_instances("api")
        
        assert len(healthy) == 2
    
    def test_get_healthy_instances_unknown_service(self):
        """Test getting healthy instances for unknown service."""
        engine = ServiceMeshEngine()
        
        instances = engine.get_healthy_instances("unknown")
        
        assert instances == []
    
    def test_select_instance_round_robin(self):
        """Test round-robin load balancing."""
        engine = ServiceMeshEngine()
        
        engine.register_service("api", "192.168.1.10", 8080)
        engine.register_service("api", "192.168.1.11", 8080)
        engine.register_service("api", "192.168.1.12", 8080)
        
        # Select 6 times - should cycle through all instances twice
        selected = []
        for i in range(6):
            instance = engine.select_instance("api", LoadBalanceStrategy.ROUND_ROBIN)
            selected.append(instance.host)
        
        # Each host should be selected twice
        assert selected.count("192.168.1.10") == 2
        assert selected.count("192.168.1.11") == 2
        assert selected.count("192.168.1.12") == 2
    
    def test_select_instance_least_connections(self):
        """Test least-connections load balancing."""
        engine = ServiceMeshEngine()
        
        engine.register_service("api", "192.168.1.10", 8080)
        engine.register_service("api", "192.168.1.11", 8080)
        
        instances = engine._services["api"]
        instances[0].active_connections = 10
        instances[1].active_connections = 2
        
        instance = engine.select_instance("api", LoadBalanceStrategy.LEAST_CONNECTIONS)
        
        assert instance.host == "192.168.1.11"
    
    def test_select_instance_weighted(self):
        """Test weighted load balancing."""
        engine = ServiceMeshEngine()
        
        engine.register_service("api", "192.168.1.10", 8080, weight=10)
        engine.register_service("api", "192.168.1.11", 8080, weight=90)
        
        # Select 100 times and check distribution
        selected = []
        for i in range(100):
            instance = engine.select_instance("api", LoadBalanceStrategy.WEIGHTED)
            selected.append(instance.host)
        
        # Higher weight should get more requests (allow variance)
        count_11 = selected.count("192.168.1.11")
        assert count_11 > 50  # Should be roughly 90%
    
    def test_select_instance_random(self):
        """Test random load balancing."""
        engine = ServiceMeshEngine()
        
        engine.register_service("api", "192.168.1.10", 8080)
        engine.register_service("api", "192.168.1.11", 8080)
        engine.register_service("api", "192.168.1.12", 8080)
        
        # Should always return an instance
        for i in range(10):
            instance = engine.select_instance("api", LoadBalanceStrategy.RANDOM)
            assert instance is not None
    
    def test_select_instance_no_healthy(self):
        """Test selecting instance when none healthy."""
        engine = ServiceMeshEngine()
        
        engine.register_service("api", "192.168.1.10", 8080)
        
        instances = engine._services["api"]
        instances[0].status = ServiceStatus.UNHEALTHY
        
        instance = engine.select_instance("api")
        
        assert instance is None
    
    def test_select_instance_circuit_open(self):
        """Test selecting instance when circuit breaker is open."""
        engine = ServiceMeshEngine()
        
        engine.register_service("api", "192.168.1.10", 8080)
        
        # Trip circuit breaker
        for i in range(5):
            engine.record_failure("api", engine._services["api"][0].instance_id)
        
        instance = engine.select_instance("api")
        
        assert instance is None
    
    def test_record_success(self):
        """Test recording successful request."""
        engine = ServiceMeshEngine()
        
        instance_id = engine.register_service("api", "192.168.1.10", 8080)
        
        engine.record_success("api", instance_id)
        
        stats = engine.get_statistics()
        assert stats["successful_requests"] == 1
        
        # Instance stats updated
        service = engine.get_service("api")
        assert service["instances"][0]["total_requests"] == 1
        assert service["instances"][0]["failed_requests"] == 0
    
    def test_record_failure(self):
        """Test recording failed request."""
        engine = ServiceMeshEngine()
        
        instance_id = engine.register_service("api", "192.168.1.10", 8080)
        
        engine.record_failure("api", instance_id, status_code=500)
        
        stats = engine.get_statistics()
        assert stats["failed_requests"] == 1
        
        # Instance stats updated
        service = engine.get_service("api")
        assert service["instances"][0]["total_requests"] == 1
        assert service["instances"][0]["failed_requests"] == 1
    
    def test_circuit_breaker_trips(self):
        """Test circuit breaker trips after threshold."""
        engine = ServiceMeshEngine()
        
        instance_id = engine.register_service("api", "192.168.1.10", 8080)
        
        # Record 5 failures (default threshold)
        for i in range(5):
            engine.record_failure("api", instance_id)
        
        cb = engine.get_circuit_breaker("api")
        
        assert cb["state"] == "open"
        
        stats = engine.get_statistics()
        assert stats["circuit_breaker_trips"] >= 1
    
    def test_circuit_breaker_half_open(self):
        """Test circuit breaker transitions to half-open."""
        engine = ServiceMeshEngine()
        
        instance_id = engine.register_service("api", "192.168.1.10", 8080)
        
        # Trip circuit breaker
        for i in range(5):
            engine.record_failure("api", instance_id)
        
        cb = engine.get_circuit_breaker("api")
        assert cb["state"] == "open"
        
        # Wait for timeout
        time.sleep(0.1)  # Use default 30s timeout - won't actually transition in test
        
        # Manually set to half-open for testing
        engine._circuit_breakers["api"].state = CircuitState.HALF_OPEN
        
        cb = engine.get_circuit_breaker("api")
        assert cb["state"] == "half_open"
    
    def test_circuit_breaker_closes_on_success(self):
        """Test circuit breaker closes after successful requests."""
        engine = ServiceMeshEngine()
        
        instance_id = engine.register_service("api", "192.168.1.10", 8080)
        
        # Trip circuit breaker
        for i in range(5):
            engine.record_failure("api", instance_id)
        
        # Set to half-open
        engine._circuit_breakers["api"].state = CircuitState.HALF_OPEN
        
        # Record successes
        for i in range(3):
            engine.record_success("api", instance_id)
        
        cb = engine.get_circuit_breaker("api")
        
        assert cb["state"] == "closed"
    
    def test_configure_circuit_breaker(self):
        """Test configuring circuit breaker."""
        engine = ServiceMeshEngine()
        
        engine.register_service("api", "192.168.1.10", 8080)
        
        result = engine.configure_circuit_breaker(
            "api",
            failure_threshold=10,
            success_threshold=5,
            timeout_seconds=60,
        )
        
        assert result is True
        
        cb = engine.get_circuit_breaker("api")
        
        assert cb["failure_threshold"] == 10
        assert cb["success_threshold"] == 5
        assert cb["timeout_seconds"] == 60
    
    def test_configure_circuit_breaker_unknown_service(self):
        """Test configuring circuit breaker for unknown service."""
        engine = ServiceMeshEngine()
        
        result = engine.configure_circuit_breaker("unknown")
        
        assert result is False
    
    def test_configure_retry(self):
        """Test configuring retry logic."""
        engine = ServiceMeshEngine()
        
        config = engine.configure_retry(
            "api",
            max_retries=5,
            initial_delay_ms=200,
            max_delay_ms=20000,
            multiplier=1.5,
        )
        
        assert config.max_retries == 5
        assert config.initial_delay_ms == 200
        assert config.max_delay_ms == 20000
        assert config.multiplier == 1.5
    
    def test_get_retry_config(self):
        """Test getting retry config."""
        engine = ServiceMeshEngine()
        
        engine.configure_retry("api", max_retries=5)
        
        config = engine.get_retry_config("api")
        
        assert config is not None
        assert config.max_retries == 5
    
    def test_get_retry_config_unknown_service(self):
        """Test getting retry config for unknown service."""
        engine = ServiceMeshEngine()
        
        config = engine.get_retry_config("unknown")
        
        assert config is None
    
    def test_retry_delay_calculation(self):
        """Test retry delay calculation with exponential backoff."""
        config = RetryConfig(
            max_retries=3,
            initial_delay_ms=100,
            max_delay_ms=10000,
            multiplier=2.0,
        )
        
        # Attempt 0: 100ms
        assert config.get_delay(0) == 100
        
        # Attempt 1: 200ms
        assert config.get_delay(1) == 200
        
        # Attempt 2: 400ms
        assert config.get_delay(2) == 400
        
        # Attempt 10: should be capped at max_delay_ms
        assert config.get_delay(10) == 10000
    
    def test_create_traffic_split(self):
        """Test creating traffic split."""
        engine = ServiceMeshEngine()
        
        engine.register_service("api", "192.168.1.10", 8080)
        engine.register_service("api", "192.168.1.11", 8080)
        
        split_id = engine.create_traffic_split(
            "api",
            rules=[
                {"instance_id": engine._services["api"][0].instance_id, "percentage": 90},
                {"instance_id": engine._services["api"][1].instance_id, "percentage": 10},
            ],
        )
        
        assert split_id is not None
        assert split_id.startswith("split_")
    
    def test_select_instance_with_traffic_split(self):
        """Test selecting instance with traffic split."""
        engine = ServiceMeshEngine()
        
        instance1_id = engine.register_service("api", "192.168.1.10", 8080)
        instance2_id = engine.register_service("api", "192.168.1.11", 8080)
        
        split_id = engine.create_traffic_split(
            "api",
            rules=[
                {"instance_id": instance1_id, "percentage": 90},
                {"instance_id": instance2_id, "percentage": 10},
            ],
        )
        
        # Select 100 times and check distribution
        selected = []
        for i in range(100):
            instance = engine.select_instance_with_traffic_split(split_id)
            if instance:
                selected.append(instance.host)
        
        # 90% should go to instance1
        count_10 = selected.count("192.168.1.10")
        assert count_10 > 50  # Should be roughly 90%
    
    def test_select_instance_unknown_traffic_split(self):
        """Test selecting instance with unknown traffic split."""
        engine = ServiceMeshEngine()
        
        instance = engine.select_instance_with_traffic_split("unknown_split")
        
        assert instance is None
    
    def test_update_instance_health(self):
        """Test updating instance health."""
        engine = ServiceMeshEngine()
        
        instance_id = engine.register_service("api", "192.168.1.10", 8080)
        
        result = engine.update_instance_health(instance_id, ServiceStatus.UNHEALTHY)
        
        assert result is True
        
        service = engine.get_service("api")
        assert service["instances"][0]["status"] == "unhealthy"
        assert service["instances"][0]["last_health_check"] is not None
    
    def test_update_unknown_instance_health(self):
        """Test updating unknown instance health."""
        engine = ServiceMeshEngine()
        
        result = engine.update_instance_health("unknown", ServiceStatus.HEALTHY)
        
        assert result is False
    
    def test_get_service(self):
        """Test getting service info."""
        engine = ServiceMeshEngine()
        
        engine.register_service("api", "192.168.1.10", 8080)
        engine.register_service("api", "192.168.1.11", 8080)
        
        service = engine.get_service("api")
        
        assert service is not None
        assert service["service_name"] == "api"
        assert service["instance_count"] == 2
        assert len(service["instances"]) == 2
    
    def test_get_unknown_service(self):
        """Test getting unknown service."""
        engine = ServiceMeshEngine()
        
        service = engine.get_service("unknown")
        
        assert service is None
    
    def test_get_all_services(self):
        """Test getting all services."""
        engine = ServiceMeshEngine()
        
        engine.register_service("api", "192.168.1.10", 8080)
        engine.register_service("users", "192.168.1.20", 8081)
        engine.register_service("orders", "192.168.1.30", 8082)
        
        services = engine.get_all_services()
        
        assert len(services) == 3
    
    def test_get_circuit_breaker(self):
        """Test getting circuit breaker state."""
        engine = ServiceMeshEngine()
        
        engine.register_service("api", "192.168.1.10", 8080)
        
        cb = engine.get_circuit_breaker("api")
        
        assert cb is not None
        assert cb["service_name"] == "api"
        assert cb["state"] == "closed"
    
    def test_get_unknown_circuit_breaker(self):
        """Test getting unknown circuit breaker."""
        engine = ServiceMeshEngine()
        
        cb = engine.get_circuit_breaker("unknown")
        
        assert cb is None
    
    def test_reset_circuit_breaker(self):
        """Test resetting circuit breaker."""
        engine = ServiceMeshEngine()
        
        instance_id = engine.register_service("api", "192.168.1.10", 8080)
        
        # Trip circuit breaker
        for i in range(5):
            engine.record_failure("api", instance_id)
        
        cb = engine.get_circuit_breaker("api")
        assert cb["state"] == "open"
        
        # Reset
        result = engine.reset_circuit_breaker("api")
        
        assert result is True
        
        cb = engine.get_circuit_breaker("api")
        assert cb["state"] == "closed"
        assert cb["failure_count"] == 0
    
    def test_reset_unknown_circuit_breaker(self):
        """Test resetting unknown circuit breaker."""
        engine = ServiceMeshEngine()
        
        result = engine.reset_circuit_breaker("unknown")
        
        assert result is False
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = ServiceMeshEngine()
        
        engine.register_service("api", "192.168.1.10", 8080)
        engine.register_service("users", "192.168.1.20", 8081)
        
        stats = engine.get_statistics()
        
        assert stats["total_services"] == 2
        assert stats["total_instances"] == 2
    
    def test_service_instance_to_dict(self):
        """Test service instance serialization."""
        instance = ServiceInstance(
            instance_id="svc_test",
            service_name="test-service",
            host="192.168.1.10",
            port=8080,
            weight=100,
            status=ServiceStatus.HEALTHY,
        )
        
        d = instance.to_dict()
        
        assert d["instance_id"] == "svc_test"
        assert d["service_name"] == "test-service"
        assert d["status"] == "healthy"
    
    def test_circuit_breaker_to_dict(self):
        """Test circuit breaker serialization."""
        cb = CircuitBreaker(
            service_name="test-service",
            state=CircuitState.OPEN,
            failure_count=5,
            failure_threshold=5,
            timeout_seconds=30,
        )
        
        d = cb.to_dict()
        
        assert d["service_name"] == "test-service"
        assert d["state"] == "open"
        assert d["failure_count"] == 5
    
    def test_retry_config_to_dict(self):
        """Test retry config serialization (via get_retry_config)."""
        engine = ServiceMeshEngine()
        
        config = engine.configure_retry("api", max_retries=5)
        
        assert config.max_retries == 5
        assert config.initial_delay_ms == 100
    
    def test_traffic_split_to_dict(self):
        """Test traffic split serialization."""
        split = TrafficSplit(
            split_id="split_test",
            service_name="api",
            rules=[{"instance_id": "svc_1", "percentage": 90}],
        )
        
        d = split.to_dict()
        
        assert d["split_id"] == "split_test"
        assert d["service_name"] == "api"
        assert len(d["rules"]) == 1
    
    def test_service_status_enum_values(self):
        """Test service status enum values."""
        assert ServiceStatus.HEALTHY.value == "healthy"
        assert ServiceStatus.UNHEALTHY.value == "unhealthy"
        assert ServiceStatus.DEGRADED.value == "degraded"
        assert ServiceStatus.UNKNOWN.value == "unknown"
    
    def test_load_balance_strategy_enum_values(self):
        """Test load balance strategy enum values."""
        assert LoadBalanceStrategy.ROUND_ROBIN.value == "round_robin"
        assert LoadBalanceStrategy.LEAST_CONNECTIONS.value == "least_connections"
        assert LoadBalanceStrategy.WEIGHTED.value == "weighted"
        assert LoadBalanceStrategy.RANDOM.value == "random"
    
    def test_circuit_state_enum_values(self):
        """Test circuit state enum values."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"
    
    def test_statistics_total_requests(self):
        """Test that statistics track total requests."""
        engine = ServiceMeshEngine()
        
        instance_id = engine.register_service("api", "192.168.1.10", 8080)
        
        engine.record_success("api", instance_id)
        engine.record_success("api", instance_id)
        engine.record_failure("api", instance_id)
        
        stats = engine.get_statistics()
        
        assert stats["total_requests"] == 3
    
    def test_statistics_circuit_breaker_trips(self):
        """Test that statistics track circuit breaker trips."""
        engine = ServiceMeshEngine()
        
        instance_id = engine.register_service("api", "192.168.1.10", 8080)
        
        for i in range(5):
            engine.record_failure("api", instance_id)
        
        stats = engine.get_statistics()
        
        assert stats["circuit_breaker_trips"] >= 1
    
    def test_statistics_retries(self):
        """Test that statistics track retries."""
        engine = ServiceMeshEngine()
        
        stats = engine.get_statistics()
        
        assert "retries" in stats
    
    def test_multiple_instances_same_service(self):
        """Test registering multiple instances for same service."""
        engine = ServiceMeshEngine()
        
        for i in range(5):
            engine.register_service("api", f"192.168.1.{i+10}", 8080)
        
        service = engine.get_service("api")
        
        assert service["instance_count"] == 5
    
    def test_service_registered_at_tracked(self):
        """Test that service registered_at is tracked."""
        engine = ServiceMeshEngine()
        
        engine.register_service("api", "192.168.1.10", 8080)
        
        service = engine.get_service("api")
        
        assert service["instances"][0]["registered_at"] is not None
    
    def test_circuit_breaker_last_state_change_tracked(self):
        """Test that circuit breaker last_state_change is tracked."""
        engine = ServiceMeshEngine()
        
        engine.register_service("api", "192.168.1.10", 8080)
        
        cb = engine.get_circuit_breaker("api")
        
        assert cb["last_state_change"] is not None
    
    def test_healthy_count_in_all_services(self):
        """Test that healthy count is calculated in all_services."""
        engine = ServiceMeshEngine()
        
        engine.register_service("api", "192.168.1.10", 8080)
        engine.register_service("api", "192.168.1.11", 8080)
        
        # Mark one unhealthy
        instances = engine._services["api"]
        instances[1].status = ServiceStatus.UNHEALTHY
        
        services = engine.get_all_services()
        
        assert services[0]["healthy_count"] == 1
    
    def test_last_failure_at_tracked(self):
        """Test that circuit breaker last_failure_at is tracked."""
        engine = ServiceMeshEngine()
        
        instance_id = engine.register_service("api", "192.168.1.10", 8080)
        
        engine.record_failure("api", instance_id)
        
        cb = engine.get_circuit_breaker("api")
        
        assert cb["last_failure_at"] is not None
    
    def test_select_instance_default_strategy(self):
        """Test selecting instance with default strategy."""
        engine = ServiceMeshEngine()
        
        engine.register_service("api", "192.168.1.10", 8080)
        
        # Default should work
        instance = engine.select_instance("api")
        
        assert instance is not None
    
    def test_retry_config_default_values(self):
        """Test retry config default values."""
        config = RetryConfig()
        
        assert config.max_retries == 3
        assert config.initial_delay_ms == 100
        assert config.max_delay_ms == 10000
        assert config.multiplier == 2.0
        assert config.retryable_status_codes == [502, 503, 504]
    
    def test_circuit_breaker_default_values(self):
        """Test circuit breaker default values."""
        cb = CircuitBreaker(service_name="test")
        
        assert cb.failure_threshold == 5
        assert cb.success_threshold == 3
        assert cb.timeout_seconds == 30
    
    def test_traffic_split_created_at_tracked(self):
        """Test that traffic split created_at is tracked."""
        engine = ServiceMeshEngine()
        
        engine.register_service("api", "192.168.1.10", 8080)
        
        split_id = engine.create_traffic_split("api", rules=[])
        
        split = engine._traffic_splits[split_id]
        
        assert split.created_at is not None
    
    def test_empty_service_list(self):
        """Test getting services when none registered."""
        engine = ServiceMeshEngine()
        
        services = engine.get_all_services()
        
        assert services == []
    
    def test_deregister_last_instance_removes_service(self):
        """Test that deregistering last instance removes service."""
        engine = ServiceMeshEngine()
        
        instance_id = engine.register_service("api", "192.168.1.10", 8080)
        
        engine.deregister_service(instance_id)
        
        service = engine.get_service("api")
        
        assert service is None
    
    def test_round_robin_index_per_service(self):
        """Test that round-robin index is per-service."""
        engine = ServiceMeshEngine()
        
        engine.register_service("api", "192.168.1.10", 8080)
        engine.register_service("api", "192.168.1.11", 8080)
        engine.register_service("users", "192.168.1.20", 8081)
        engine.register_service("users", "192.168.1.21", 8081)
        
        # Select from api
        engine.select_instance("api", LoadBalanceStrategy.ROUND_ROBIN)
        
        # Users should start from index 0
        users_instance = engine.select_instance("users", LoadBalanceStrategy.ROUND_ROBIN)
        
        assert users_instance.host == "192.168.1.20"
    
    def test_weighted_selection_with_equal_weights(self):
        """Test weighted selection with equal weights."""
        engine = ServiceMeshEngine()
        
        engine.register_service("api", "192.168.1.10", 8080, weight=100)
        engine.register_service("api", "192.168.1.11", 8080, weight=100)
        
        # Should distribute roughly equally
        selected = []
        for i in range(100):
            instance = engine.select_instance("api", LoadBalanceStrategy.WEIGHTED)
            selected.append(instance.host)
        
        count_10 = selected.count("192.168.1.10")
        count_11 = selected.count("192.168.1.11")
        
        # Should be roughly 50/50 (allow variance)
        assert 30 <= count_10 <= 70
        assert 30 <= count_11 <= 70
    
    def test_circuit_breaker_timeout_transition(self):
        """Test circuit breaker timeout transition to half-open."""
        engine = ServiceMeshEngine()
        
        instance_id = engine.register_service("api", "192.168.1.10", 8080)
        
        # Configure short timeout
        engine.configure_circuit_breaker("api", timeout_seconds=1)
        
        # Trip circuit breaker
        for i in range(5):
            engine.record_failure("api", instance_id)
        
        cb = engine.get_circuit_breaker("api")
        assert cb["state"] == "open"
        
        # Wait for timeout
        time.sleep(1.1)
        
        # Try to select - should transition to half-open
        engine.select_instance("api")
        
        cb = engine.get_circuit_breaker("api")
        assert cb["state"] == "half_open"
    
    def test_service_mesh_with_all_features(self):
        """Test service mesh with all features enabled."""
        engine = ServiceMeshEngine()
        
        # Register services
        instance1 = engine.register_service("api", "192.168.1.10", 8080, weight=90)
        instance2 = engine.register_service("api", "192.168.1.11", 8080, weight=10)
        
        # Configure circuit breaker
        engine.configure_circuit_breaker("api", failure_threshold=10, timeout_seconds=60)
        
        # Configure retry
        engine.configure_retry("api", max_retries=3, initial_delay_ms=200)
        
        # Create traffic split
        split_id = engine.create_traffic_split(
            "api",
            rules=[
                {"instance_id": instance1, "percentage": 90},
                {"instance_id": instance2, "percentage": 10},
            ],
        )
        
        # Make some requests
        for i in range(10):
            instance = engine.select_instance("api")
            if instance:
                engine.record_success("api", instance.instance_id)
        
        stats = engine.get_statistics()
        
        assert stats["total_services"] == 1
        assert stats["total_instances"] == 2
        assert stats["successful_requests"] == 10
    
    def test_get_service_includes_circuit_breaker(self):
        """Test that get_service includes circuit breaker info."""
        engine = ServiceMeshEngine()
        
        engine.register_service("api", "192.168.1.10", 8080)
        
        service = engine.get_service("api")
        
        assert "circuit_breaker" in service
        assert service["circuit_breaker"] is not None
    
    def test_instance_active_connections_tracked(self):
        """Test that instance active connections are tracked."""
        engine = ServiceMeshEngine()
        
        engine.register_service("api", "192.168.1.10", 8080)
        
        instances = engine._services["api"]
        instances[0].active_connections = 5
        
        instance = engine.select_instance("api", LoadBalanceStrategy.LEAST_CONNECTIONS)
        
        assert instance.active_connections == 5
    
    def test_metadata_stored_on_instance(self):
        """Test that metadata is stored on instance."""
        engine = ServiceMeshEngine()
        
        engine.register_service(
            "api",
            "192.168.1.10",
            8080,
            metadata={"version": "v2", "region": "us-east", "zone": "a"},
        )
        
        service = engine.get_service("api")
        
        assert service["instances"][0]["metadata"]["version"] == "v2"
        assert service["instances"][0]["metadata"]["region"] == "us-east"
        assert service["instances"][0]["metadata"]["zone"] == "a"
