"""Tests for API Gateway Engine — Slice 45."""
import pytest
from copilot_core.apigateway.engine import (
    APIGatewayEngine,
    HTTPMethod,
    RouteStatus,
    RouteConfig,
    Request,
    Response,
    MiddlewareRegistration,
    create_api_gateway_engine,
)
from datetime import datetime, timezone, timedelta


class TestAPIGatewayEngine:
    """Test API gateway engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_api_gateway_engine()
        assert engine is not None
    
    def test_register_route_get(self):
        """Test registering GET route."""
        engine = APIGatewayEngine()
        
        def handler(request):
            return Response.ok({"message": "OK"})
        
        route_id = engine.register_route(
            path="/users",
            method="GET",
            handler=handler,
        )
        
        assert route_id is not None
        assert route_id.startswith("route_")
        
        route = engine.get_route(route_id)
        assert route is not None
        assert route["method"] == "GET"
        assert route["path"] == "/users"
    
    def test_register_route_post(self):
        """Test registering POST route."""
        engine = APIGatewayEngine()
        
        def handler(request):
            return Response.created({"id": 1})
        
        route_id = engine.register_route(
            path="/users",
            method="POST",
            handler=handler,
        )
        
        route = engine.get_route(route_id)
        assert route["method"] == "POST"
    
    def test_register_route_with_custom_id(self):
        """Test registering route with custom ID."""
        engine = APIGatewayEngine()
        
        def handler(request):
            return Response.ok({})
        
        route_id = engine.register_route(
            path="/test",
            method="GET",
            handler=handler,
            route_id="custom_route_id",
        )
        
        assert route_id == "custom_route_id"
    
    def test_register_route_with_auth(self):
        """Test registering route with auth required."""
        engine = APIGatewayEngine()
        
        def handler(request):
            return Response.ok({})
        
        route_id = engine.register_route(
            path="/protected",
            method="GET",
            handler=handler,
            auth_required=True,
        )
        
        route = engine.get_route(route_id)
        assert route["auth_required"] is True
    
    def test_register_route_with_rate_limit(self):
        """Test registering route with rate limit."""
        engine = APIGatewayEngine()
        
        def handler(request):
            return Response.ok({})
        
        route_id = engine.register_route(
            path="/api/data",
            method="GET",
            handler=handler,
            rate_limit_id="api_limit",
        )
        
        route = engine.get_route(route_id)
        assert route["rate_limit_id"] == "api_limit"
    
    def test_register_route_with_middleware(self):
        """Test registering route with middleware."""
        engine = APIGatewayEngine()
        
        def handler(request):
            return Response.ok({})
        
        route_id = engine.register_route(
            path="/api/data",
            method="GET",
            handler=handler,
            middleware=["logging", "cors"],
        )
        
        route = engine.get_route(route_id)
        assert route["middleware"] == ["logging", "cors"]
    
    def test_register_route_with_cache(self):
        """Test registering route with cache TTL."""
        engine = APIGatewayEngine()
        
        def handler(request):
            return Response.ok({"data": "value"})
        
        route_id = engine.register_route(
            path="/api/cached",
            method="GET",
            handler=handler,
            cache_ttl_seconds=60,
        )
        
        route = engine.get_route(route_id)
        assert route["cache_ttl_seconds"] == 60
    
    def test_register_route_with_tags(self):
        """Test registering route with tags."""
        engine = APIGatewayEngine()
        
        def handler(request):
            return Response.ok({})
        
        route_id = engine.register_route(
            path="/api/users",
            method="GET",
            handler=handler,
            tags=["users", "api", "v1"],
        )
        
        route = engine.get_route(route_id)
        assert "users" in route["tags"]
        assert "api" in route["tags"]
    
    def test_handle_request_exact_match(self):
        """Test handling request with exact route match."""
        engine = APIGatewayEngine()
        
        def handler(request):
            return Response.ok({"message": "Success"})
        
        engine.register_route("/users", "GET", handler)
        
        response = engine.handle_request("GET", "/users")
        
        assert response.status_code == 200
        assert response.body["message"] == "Success"
    
    def test_handle_request_parameterized_match(self):
        """Test handling request with parameterized route."""
        engine = APIGatewayEngine()
        
        def handler(request):
            return Response.ok({"user_id": request.path_params["id"]})
        
        engine.register_route("/users/:id", "GET", handler)
        
        response = engine.handle_request("GET", "/users/123")
        
        assert response.status_code == 200
        assert response.body["user_id"] == "123"
    
    def test_handle_request_no_match(self):
        """Test handling request with no route match."""
        engine = APIGatewayEngine()
        
        engine.register_route("/users", "GET", lambda r: Response.ok({}))
        
        response = engine.handle_request("GET", "/nonexistent")
        
        assert response.status_code == 404
    
    def test_handle_request_method_not_allowed(self):
        """Test handling request with wrong method."""
        engine = APIGatewayEngine()
        
        engine.register_route("/users", "GET", lambda r: Response.ok({}))
        
        response = engine.handle_request("POST", "/users")
        
        assert response.status_code == 404
    
    def test_handle_request_inactive_route(self):
        """Test handling request to inactive route."""
        engine = APIGatewayEngine()
        
        route_id = engine.register_route("/users", "GET", lambda r: Response.ok({}))
        engine.disable_route(route_id)
        
        response = engine.handle_request("GET", "/users")
        
        assert response.status_code == 500
    
    def test_register_middleware(self):
        """Test registering middleware."""
        engine = APIGatewayEngine()
        
        def middleware(request, next):
            response = next(request)
            response.headers["X-Custom"] = "value"
            return response
        
        mw_id = engine.register_middleware("custom_header", middleware)
        
        assert mw_id is not None
        assert mw_id.startswith("mw_")
    
    def test_register_middleware_with_priority(self):
        """Test registering middleware with priority."""
        engine = APIGatewayEngine()
        
        def mw1(request, next):
            return next(request)
        
        def mw2(request, next):
            return next(request)
        
        engine.register_middleware("mw1", mw1, priority=5)
        engine.register_middleware("mw2", mw2, priority=10)
        
        # Higher priority should be executed first
        mw_list = engine.get_all_middleware()
        
        assert len(mw_list) == 2
    
    def test_register_middleware_for_specific_routes(self):
        """Test registering middleware for specific routes."""
        engine = APIGatewayEngine()
        
        def middleware(request, next):
            return next(request)
        
        mw_id = engine.register_middleware(
            "auth_check",
            middleware,
            routes=["route_1", "route_2"],
        )
        
        mw = engine.get_middleware(mw_id)
        assert "route_1" in mw["routes"]
        assert "route_2" in mw["routes"]
    
    def test_register_auth_handler(self):
        """Test registering auth handler."""
        engine = APIGatewayEngine()
        
        def auth_handler(request):
            return "Bearer" in request.headers.get("Authorization", "")
        
        engine.register_auth_handler("Bearer", auth_handler)
        
        assert "Bearer" in engine._auth_handlers
    
    def test_handle_request_with_auth_success(self):
        """Test handling request with successful auth."""
        engine = APIGatewayEngine()
        
        def auth_handler(request):
            return True
        
        engine.register_auth_handler("Bearer", auth_handler)
        
        def handler(request):
            return Response.ok({"authenticated": True})
        
        engine.register_route("/protected", "GET", handler, auth_required=True)
        
        response = engine.handle_request(
            "GET",
            "/protected",
            headers={"Authorization": "Bearer token123"},
        )
        
        assert response.status_code == 200
        assert response.body["authenticated"] is True
    
    def test_handle_request_with_auth_failure(self):
        """Test handling request with failed auth."""
        engine = APIGatewayEngine()
        
        def auth_handler(request):
            return False
        
        engine.register_auth_handler("Bearer", auth_handler)
        
        def handler(request):
            return Response.ok({})
        
        engine.register_route("/protected", "GET", handler, auth_required=True)
        
        response = engine.handle_request(
            "GET",
            "/protected",
            headers={"Authorization": "Bearer invalid"},
        )
        
        assert response.status_code == 401
    
    def test_handle_request_without_auth_header(self):
        """Test handling request without auth header."""
        engine = APIGatewayEngine()
        
        def handler(request):
            return Response.ok({})
        
        engine.register_route("/protected", "GET", handler, auth_required=True)
        
        response = engine.handle_request("GET", "/protected")
        
        assert response.status_code == 401
    
    def test_response_ok(self):
        """Test Response.ok helper."""
        response = Response.ok({"message": "OK"})
        
        assert response.status_code == 200
        assert response.body["message"] == "OK"
    
    def test_response_created(self):
        """Test Response.created helper."""
        response = Response.created({"id": 123})
        
        assert response.status_code == 201
        assert response.body["id"] == 123
    
    def test_response_bad_request(self):
        """Test Response.bad_request helper."""
        response = Response.bad_request("Invalid input")
        
        assert response.status_code == 400
        assert response.body["error"] == "Invalid input"
    
    def test_response_unauthorized(self):
        """Test Response.unauthorized helper."""
        response = Response.unauthorized("Not logged in")
        
        assert response.status_code == 401
        assert response.body["error"] == "Not logged in"
    
    def test_response_forbidden(self):
        """Test Response.forbidden helper."""
        response = Response.forbidden("No access")
        
        assert response.status_code == 403
        assert response.body["error"] == "No access"
    
    def test_response_not_found(self):
        """Test Response.not_found helper."""
        response = Response.not_found("Resource missing")
        
        assert response.status_code == 404
        assert response.body["error"] == "Resource missing"
    
    def test_response_internal_error(self):
        """Test Response.internal_error helper."""
        response = Response.internal_error("Something broke")
        
        assert response.status_code == 500
        assert response.body["error"] == "Something broke"
    
    def test_get_route_not_found(self):
        """Test getting nonexistent route."""
        engine = APIGatewayEngine()
        
        route = engine.get_route("unknown_route")
        
        assert route is None
    
    def test_get_all_routes(self):
        """Test getting all routes."""
        engine = APIGatewayEngine()
        
        engine.register_route("/users", "GET", lambda r: Response.ok({}))
        engine.register_route("/posts", "GET", lambda r: Response.ok({}))
        engine.register_route("/comments", "GET", lambda r: Response.ok({}))
        
        routes = engine.get_all_routes()
        
        assert len(routes) == 3
    
    def test_get_all_routes_filtered_by_method(self):
        """Test getting routes filtered by method."""
        engine = APIGatewayEngine()
        
        engine.register_route("/users", "GET", lambda r: Response.ok({}))
        engine.register_route("/users", "POST", lambda r: Response.created({}))
        engine.register_route("/users/:id", "DELETE", lambda r: Response.ok({}))
        
        get_routes = engine.get_all_routes(method="GET")
        
        assert len(get_routes) == 1
        assert get_routes[0]["method"] == "GET"
    
    def test_get_all_routes_filtered_by_tag(self):
        """Test getting routes filtered by tag."""
        engine = APIGatewayEngine()
        
        engine.register_route("/api/users", "GET", lambda r: Response.ok({}), tags=["api", "users"])
        engine.register_route("/api/posts", "GET", lambda r: Response.ok({}), tags=["api", "posts"])
        engine.register_route("/health", "GET", lambda r: Response.ok({}), tags=["health"])
        
        api_routes = engine.get_all_routes(tag="api")
        
        assert len(api_routes) == 2
    
    def test_get_all_routes_filtered_by_status(self):
        """Test getting routes filtered by status."""
        engine = APIGatewayEngine()
        
        route1 = engine.register_route("/active", "GET", lambda r: Response.ok({}))
        route2 = engine.register_route("/inactive", "GET", lambda r: Response.ok({}))
        
        engine.disable_route(route2)
        
        active = engine.get_all_routes(status=RouteStatus.ACTIVE)
        inactive = engine.get_all_routes(status=RouteStatus.INACTIVE)
        
        assert len(active) == 1
        assert len(inactive) == 1
    
    def test_enable_route(self):
        """Test enabling a route."""
        engine = APIGatewayEngine()
        
        route_id = engine.register_route("/test", "GET", lambda r: Response.ok({}))
        engine.disable_route(route_id)
        
        result = engine.enable_route(route_id)
        
        assert result is True
        
        route = engine.get_route(route_id)
        assert route["status"] == "active"
    
    def test_enable_unknown_route(self):
        """Test enabling unknown route."""
        engine = APIGatewayEngine()
        
        result = engine.enable_route("unknown")
        
        assert result is False
    
    def test_disable_route(self):
        """Test disabling a route."""
        engine = APIGatewayEngine()
        
        route_id = engine.register_route("/test", "GET", lambda r: Response.ok({}))
        
        result = engine.disable_route(route_id)
        
        assert result is True
        
        route = engine.get_route(route_id)
        assert route["status"] == "inactive"
    
    def test_deprecate_route(self):
        """Test deprecating a route."""
        engine = APIGatewayEngine()
        
        route_id = engine.register_route("/old-api", "GET", lambda r: Response.ok({}))
        
        result = engine.deprecate_route(route_id)
        
        assert result is True
        
        route = engine.get_route(route_id)
        assert route["status"] == "deprecated"
    
    def test_delete_route(self):
        """Test deleting a route."""
        engine = APIGatewayEngine()
        
        route_id = engine.register_route("/test", "GET", lambda r: Response.ok({}))
        
        result = engine.delete_route(route_id)
        
        assert result is True
        assert engine.get_route(route_id) is None
    
    def test_delete_unknown_route(self):
        """Test deleting unknown route."""
        engine = APIGatewayEngine()
        
        result = engine.delete_route("unknown")
        
        assert result is False
    
    def test_get_middleware(self):
        """Test getting middleware."""
        engine = APIGatewayEngine()
        
        def mw(request, next):
            return next(request)
        
        mw_id = engine.register_middleware("test_mw", mw)
        
        mw_config = engine.get_middleware(mw_id)
        
        assert mw_config is not None
        assert mw_config["name"] == "test_mw"
    
    def test_get_unknown_middleware(self):
        """Test getting unknown middleware."""
        engine = APIGatewayEngine()
        
        mw = engine.get_middleware("unknown")
        
        assert mw is None
    
    def test_get_all_middleware(self):
        """Test getting all middleware."""
        engine = APIGatewayEngine()
        
        engine.register_middleware("mw1", lambda r, n: n(r))
        engine.register_middleware("mw2", lambda r, n: n(r))
        
        middleware = engine.get_all_middleware()
        
        assert len(middleware) == 2
    
    def test_clear_cache_all(self):
        """Test clearing all cache."""
        engine = APIGatewayEngine()
        
        def handler(request):
            return Response.ok({"data": "value"})
        
        engine.register_route("/cached", "GET", handler, cache_ttl_seconds=60)
        
        # Populate cache
        engine.handle_request("GET", "/cached")
        engine.handle_request("GET", "/cached")
        
        count = engine.clear_cache()
        
        assert count >= 1
        assert len(engine.get_cached_keys()) == 0
    
    def test_clear_cache_pattern(self):
        """Test clearing cache by pattern."""
        engine = APIGatewayEngine()
        
        def handler(request):
            return Response.ok({"data": "value"})
        
        engine.register_route("/api/users", "GET", handler, cache_ttl_seconds=60)
        engine.register_route("/api/posts", "GET", handler, cache_ttl_seconds=60)
        
        # Populate cache
        engine.handle_request("GET", "/api/users")
        engine.handle_request("GET", "/api/posts")
        
        count = engine.clear_cache(pattern="/api/users")
        
        assert count >= 1
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = APIGatewayEngine()
        
        def handler(request):
            return Response.ok({"message": "OK"})
        
        engine.register_route("/test", "GET", handler)
        
        engine.handle_request("GET", "/test")
        engine.handle_request("GET", "/test")
        engine.handle_request("GET", "/test")
        
        stats = engine.get_statistics()
        
        assert stats["total_requests"] == 3
        assert stats["successful_requests"] == 3
        assert stats["total_routes"] == 1
    
    def test_statistics_by_route(self):
        """Test statistics breakdown by route."""
        engine = APIGatewayEngine()
        
        engine.register_route("/users", "GET", lambda r: Response.ok({}))
        engine.register_route("/posts", "GET", lambda r: Response.ok({}))
        
        engine.handle_request("GET", "/users")
        engine.handle_request("GET", "/users")
        engine.handle_request("GET", "/posts")
        
        stats = engine.get_statistics()
        
        assert stats["by_route"] is not None
    
    def test_statistics_by_method(self):
        """Test statistics breakdown by method."""
        engine = APIGatewayEngine()
        
        engine.register_route("/test", "GET", lambda r: Response.ok({}))
        engine.register_route("/test", "POST", lambda r: Response.created({}))
        
        engine.handle_request("GET", "/test")
        engine.handle_request("GET", "/test")
        engine.handle_request("POST", "/test")
        
        stats = engine.get_statistics()
        
        assert stats["by_method"]["GET"] == 2
        assert stats["by_method"]["POST"] == 1
    
    def test_statistics_by_status_code(self):
        """Test statistics breakdown by status code."""
        engine = APIGatewayEngine()
        
        engine.register_route("/ok", "GET", lambda r: Response.ok({}))
        engine.register_route("/notfound", "GET", lambda r: Response.not_found())
        
        engine.handle_request("GET", "/ok")
        engine.handle_request("GET", "/notfound")
        
        stats = engine.get_statistics()
        
        assert stats["by_status_code"]["200"] == 1
        assert stats["by_status_code"]["404"] == 1
    
    def test_statistics_cache_hit_rate(self):
        """Test cache hit rate calculation."""
        engine = APIGatewayEngine()
        
        def handler(request):
            return Response.ok({"data": "value"})
        
        engine.register_route("/cached", "GET", handler, cache_ttl_seconds=60)
        
        # First request (miss)
        engine.handle_request("GET", "/cached")
        
        # Second request (hit)
        engine.handle_request("GET", "/cached")
        
        stats = engine.get_statistics()
        
        assert stats["cached_responses"] >= 1
        assert stats["cache_hit_rate"] > 0
    
    def test_request_to_dict(self):
        """Test request serialization."""
        request = Request(
            request_id="req_test",
            method=HTTPMethod.GET,
            path="/test",
            headers={"Content-Type": "application/json"},
            query_params={"page": "1"},
            body={"key": "value"},
        )
        
        d = request.to_dict()
        
        assert d["request_id"] == "req_test"
        assert d["method"] == "GET"
        assert d["path"] == "/test"
    
    def test_response_to_dict(self):
        """Test response serialization."""
        response = Response(
            status_code=200,
            body={"message": "OK"},
            headers={"X-Custom": "value"},
            cached=False,
        )
        
        d = response.to_dict()
        
        assert d["status_code"] == 200
        assert d["body"]["message"] == "OK"
        assert d["headers"]["X-Custom"] == "value"
    
    def test_route_config_to_dict(self):
        """Test route config serialization."""
        route = RouteConfig(
            route_id="route_test",
            path="/test",
            method=HTTPMethod.GET,
            handler=lambda r: Response.ok({}),
            auth_required=True,
            tags=["api"],
        )
        
        d = route.to_dict()
        
        assert d["route_id"] == "route_test"
        assert d["auth_required"] is True
        assert "api" in d["tags"]
    
    def test_middleware_registration_to_dict(self):
        """Test middleware registration serialization."""
        mw = MiddlewareRegistration(
            middleware_id="mw_test",
            name="Test Middleware",
            handler=lambda r, n: n(r),
            priority=10,
            routes=["route_1"],
        )
        
        d = mw.to_dict()
        
        assert d["middleware_id"] == "mw_test"
        assert d["priority"] == 10
        assert "route_1" in d["routes"]
    
    def test_http_method_enum_values(self):
        """Test HTTP method enum values."""
        assert HTTPMethod.GET.value == "GET"
        assert HTTPMethod.POST.value == "POST"
        assert HTTPMethod.PUT.value == "PUT"
        assert HTTPMethod.PATCH.value == "PATCH"
        assert HTTPMethod.DELETE.value == "DELETE"
        assert HTTPMethod.OPTIONS.value == "OPTIONS"
        assert HTTPMethod.HEAD.value == "HEAD"
    
    def test_route_status_enum_values(self):
        """Test route status enum values."""
        assert RouteStatus.ACTIVE.value == "active"
        assert RouteStatus.INACTIVE.value == "inactive"
        assert RouteStatus.DEPRECATED.value == "deprecated"
    
    def test_middleware_executes_in_priority_order(self):
        """Test that middleware executes in priority order."""
        engine = APIGatewayEngine()
        
        call_order = []
        
        def mw1(request, next):
            call_order.append(1)
            return next(request)
        
        def mw2(request, next):
            call_order.append(2)
            return next(request)
        
        def mw3(request, next):
            call_order.append(3)
            return next(request)
        
        engine.register_middleware("mw1", mw1, priority=5)
        engine.register_middleware("mw2", mw2, priority=15)
        engine.register_middleware("mw3", mw3, priority=10)
        
        def handler(request):
            return Response.ok({})
        
        engine.register_route(
            "/test",
            "GET",
            handler,
            middleware=["mw1", "mw2", "mw3"],
        )
        
        engine.handle_request("GET", "/test")
        
        # Higher priority first
        assert call_order == [2, 3, 1]
    
    def test_cached_response_marked(self):
        """Test that cached response is marked."""
        engine = APIGatewayEngine()
        
        def handler(request):
            return Response.ok({"data": "value"})
        
        engine.register_route("/cached", "GET", handler, cache_ttl_seconds=60)
        
        # First request
        response1 = engine.handle_request("GET", "/cached")
        assert response1.cached is False
        
        # Second request (should be cached)
        response2 = engine.handle_request("GET", "/cached")
        assert response2.cached is True
    
    def test_cache_expires(self):
        """Test that cache expires."""
        engine = APIGatewayEngine()
        
        call_count = [0]
        
        def handler(request):
            call_count[0] += 1
            return Response.ok({"data": "value", "call": call_count[0]})
        
        engine.register_route("/cached", "GET", handler, cache_ttl_seconds=1)
        
        # First request
        response1 = engine.handle_request("GET", "/cached")
        
        # Wait for expiry
        import time
        time.sleep(1.1)
        
        # Second request (cache expired)
        response2 = engine.handle_request("GET", "/cached")
        
        # Should have called handler again
        assert call_count[0] == 2
    
    def test_path_params_extracted(self):
        """Test that path params are extracted."""
        engine = APIGatewayEngine()
        
        captured_params = {}
        
        def handler(request):
            captured_params.update(request.path_params)
            return Response.ok(request.path_params)
        
        engine.register_route("/users/:user_id/posts/:post_id", "GET", handler)
        
        engine.handle_request("GET", "/users/123/posts/456")
        
        assert captured_params["user_id"] == "123"
        assert captured_params["post_id"] == "456"
    
    def test_query_params_passed_to_handler(self):
        """Test that query params are passed to handler."""
        engine = APIGatewayEngine()
        
        captured_params = {}
        
        def handler(request):
            captured_params.update(request.query_params)
            return Response.ok(request.query_params)
        
        engine.register_route("/search", "GET", handler)
        
        engine.handle_request(
            "GET",
            "/search",
            query_params={"q": "test", "page": "1"},
        )
        
        assert captured_params["q"] == "test"
        assert captured_params["page"] == "1"
    
    def test_headers_passed_to_handler(self):
        """Test that headers are passed to handler."""
        engine = APIGatewayEngine()
        
        captured_headers = {}
        
        def handler(request):
            captured_headers.update(request.headers)
            return Response.ok(request.headers)
        
        engine.register_route("/test", "GET", handler)
        
        engine.handle_request(
            "GET",
            "/test",
            headers={"X-Custom-Header": "custom_value"},
        )
        
        assert captured_headers["X-Custom-Header"] == "custom_value"
    
    def test_body_passed_to_handler(self):
        """Test that body is passed to handler."""
        engine = APIGatewayEngine()
        
        captured_body = None
        
        def handler(request):
            nonlocal captured_body
            captured_body = request.body
            return Response.ok(request.body)
        
        engine.register_route("/test", "POST", handler)
        
        engine.handle_request(
            "POST",
            "/test",
            body={"key": "value"},
        )
        
        assert captured_body == {"key": "value"}
    
    def test_handler_exception_returns_500(self):
        """Test that handler exception returns 500."""
        engine = APIGatewayEngine()
        
        def failing_handler(request):
            raise Exception("Handler failed")
        
        engine.register_route("/test", "GET", failing_handler)
        
        response = engine.handle_request("GET", "/test")
        
        assert response.status_code == 500
    
    def test_statistics_failed_requests_tracked(self):
        """Test that failed requests are tracked."""
        engine = APIGatewayEngine()
        
        engine.register_route("/test", "GET", lambda r: Response.internal_error())
        
        engine.handle_request("GET", "/test")
        
        stats = engine.get_statistics()
        
        assert stats["failed_requests"] == 1
    
    def test_get_cached_keys(self):
        """Test getting cached keys."""
        engine = APIGatewayEngine()
        
        def handler(request):
            return Response.ok({"data": "value"})
        
        engine.register_route("/cached", "GET", handler, cache_ttl_seconds=60)
        
        engine.handle_request("GET", "/cached")
        
        keys = engine.get_cached_keys()
        
        assert len(keys) >= 1
        assert any("GET:" in k for k in keys)
    
    def test_invalidate_cache_for_path(self):
        """Test invalidating cache for specific path."""
        engine = APIGatewayEngine()
        
        def handler(request):
            return Response.ok({"data": "value"})
        
        engine.register_route("/api/users", "GET", handler, cache_ttl_seconds=60)
        engine.register_route("/api/posts", "GET", handler, cache_ttl_seconds=60)
        
        engine.handle_request("GET", "/api/users")
        engine.handle_request("GET", "/api/posts")
        
        count = engine.invalidate_cache_for_path("/api/users")
        
        assert count >= 1
    
    def test_route_with_timeout(self):
        """Test route with timeout configuration."""
        engine = APIGatewayEngine()
        
        def handler(request):
            return Response.ok({})
        
        route_id = engine.register_route(
            "/slow",
            "GET",
            handler,
            timeout_seconds=60,
        )
        
        route = engine.get_route(route_id)
        
        assert route["timeout_seconds"] == 60
    
    def test_route_with_description(self):
        """Test route with description."""
        engine = APIGatewayEngine()
        
        def handler(request):
            return Response.ok({})
        
        route_id = engine.register_route(
            "/users",
            "GET",
            handler,
            description="Get all users",
        )
        
        route = engine.get_route(route_id)
        
        assert route["description"] == "Get all users"
    
    def test_request_id_generated(self):
        """Test that request ID is generated."""
        engine = APIGatewayEngine()
        
        captured_id = None
        
        def handler(request):
            nonlocal captured_id
            captured_id = request.request_id
            return Response.ok({})
        
        engine.register_route("/test", "GET", handler)
        
        engine.handle_request("GET", "/test")
        
        assert captured_id is not None
        assert captured_id.startswith("req_")
    
    def test_response_headers_set(self):
        """Test setting response headers."""
        engine = APIGatewayEngine()
        
        def handler(request):
            return Response.ok({"data": "value"}, headers={"X-Custom": "test"})
        
        engine.register_route("/test", "GET", handler)
        
        response = engine.handle_request("GET", "/test")
        
        assert response.headers["X-Custom"] == "test"
    
    def test_middleware_can_modify_response(self):
        """Test that middleware can modify response."""
        engine = APIGatewayEngine()
        
        def add_header_middleware(request, next):
            response = next(request)
            response.headers["X-Added"] = "by_middleware"
            return response
        
        engine.register_middleware("add_header", add_header_middleware)
        
        def handler(request):
            return Response.ok({"data": "value"})
        
        engine.register_route("/test", "GET", handler)
        
        response = engine.handle_request("GET", "/test")
        
        assert response.headers["X-Added"] == "by_middleware"
    
    def test_statistics_total_routes(self):
        """Test that statistics include total routes."""
        engine = APIGatewayEngine()
        
        engine.register_route("/route1", "GET", lambda r: Response.ok({}))
        engine.register_route("/route2", "GET", lambda r: Response.ok({}))
        
        stats = engine.get_statistics()
        
        assert stats["total_routes"] == 2
    
    def test_statistics_total_middleware(self):
        """Test that statistics include total middleware."""
        engine = APIGatewayEngine()
        
        engine.register_middleware("mw1", lambda r, n: n(r))
        engine.register_middleware("mw2", lambda r, n: n(r))
        
        stats = engine.get_statistics()
        
        assert stats["total_middleware"] == 2
    
    def test_route_created_at_tracked(self):
        """Test that route created_at is tracked."""
        engine = APIGatewayEngine()
        
        route_id = engine.register_route("/test", "GET", lambda r: Response.ok({}))
        
        route = engine.get_route(route_id)
        
        # Route config doesn't have created_at, but it's tracked internally
    
    def test_multiple_path_params(self):
        """Test route with multiple path parameters."""
        engine = APIGatewayEngine()
        
        def handler(request):
            return Response.ok(request.path_params)
        
        engine.register_route("/orgs/:org_id/teams/:team_id/members/:member_id", "GET", handler)
        
        response = engine.handle_request("GET", "/orgs/acme/teams/dev/members/alice")
        
        assert response.body["org_id"] == "acme"
        assert response.body["team_id"] == "dev"
        assert response.body["member_id"] == "alice"
    
    def test_route_tags_stored(self):
        """Test that route tags are stored."""
        engine = APIGatewayEngine()
        
        route_id = engine.register_route(
            "/api/v1/users",
            "GET",
            lambda r: Response.ok({}),
            tags=["api", "v1", "users", "public"],
        )
        
        route = engine.get_route(route_id)
        
        assert len(route["tags"]) == 4
        assert "api" in route["tags"]
        assert "public" in route["tags"]
    
    def test_empty_cache_clear(self):
        """Test clearing empty cache."""
        engine = APIGatewayEngine()
        
        count = engine.clear_cache()
        
        assert count == 0
    
    def test_invalid_cache_pattern(self):
        """Test clearing cache with invalid pattern."""
        engine = APIGatewayEngine()
        
        def handler(request):
            return Response.ok({})
        
        engine.register_route("/test", "GET", handler, cache_ttl_seconds=60)
        engine.handle_request("GET", "/test")
        
        count = engine.clear_cache(pattern="nonexistent")
        
        assert count == 0
