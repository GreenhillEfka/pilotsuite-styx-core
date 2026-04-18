"""PilotSuite Core REST API Server — FastAPI with JWT Auth + Rate Limiting."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from enum import Enum
import time
import jwt
import hashlib
from pathlib import Path
from dataclasses import dataclass, field

from fastapi import FastAPI, HTTPException, Depends, status, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

# Legacy gap endpoints
from copilot_core.api.v1.legacy_gaps import router as legacy_gaps_router
from copilot_core.api.voice_discovery import voice_capabilities_module

logger = logging.getLogger(__name__)


def _get_runtime_persistence_summary() -> Dict[str, object]:
    persistence_paths = {
        "conversation_memory_db": os.environ.get("CONVERSATION_MEMORY_DB", "/data/conversation_memory.db"),
        "vector_store_db": os.environ.get("COPILOT_VECTOR_DB_PATH", "/data/vector_store.db"),
        "shopping_db": os.environ.get("SHOPPING_DB_PATH", "/data/shopping_reminders.db"),
    }
    summary: Dict[str, object] = {}
    for label, db_path in persistence_paths.items():
        summary[f"{label}_path"] = db_path
        summary[f"{label}_accessible"] = os.path.exists(db_path)
    return summary


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class APIConfig:
    """REST API configuration."""
    host: str = "0.0.0.0"
    port: int = 8080
    secret_key: str = field(default_factory=lambda: hashlib.sha256(str(time.time()).encode()).hexdigest())
    token_expiry_hours: int = 24
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    debug: bool = False


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class TokenRequest(BaseModel):
    """Token request model."""
    api_key: str = Field(..., description="API key for authentication")
    scope: str = Field(default="read", description="Token scope (read, write, admin)")


class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    scope: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    uptime_seconds: float
    timestamp: float
    persistence: Dict[str, object] | None = None


class StatusResponse(BaseModel):
    """System status response."""
    status: str
    version: str
    modules: Dict[str, bool]
    capabilities: List[str]
    timestamp: float
    persistence: Dict[str, object] | None = None


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    message: str
    code: str
    timestamp: float


# =============================================================================
# AUTHENTICATION
# =============================================================================

class JWTAuth:
    """JWT Authentication handler."""

    def __init__(self, secret_key: str, expiry_hours: int):
        self._secret_key = secret_key
        self._expiry_seconds = expiry_hours * 3600
        self._tokens: Dict[str, Dict] = {}  # Token metadata for revocation

    def create_token(self, api_key: str, scope: str = "read") -> str:
        """Create JWT token."""
        payload = {
            "sub": api_key,
            "scope": scope,
            "iat": time.time(),
            "exp": time.time() + self._expiry_seconds,
            "jti": hashlib.sha256(f"{api_key}{time.time()}".encode()).hexdigest()[:16],
        }
        token = jwt.encode(payload, self._secret_key, algorithm="HS256")
        self._tokens[token] = payload
        return token

    def verify_token(self, token: str) -> Optional[Dict]:
        """Verify JWT token."""
        try:
            payload = jwt.decode(token, self._secret_key, algorithms=["HS256"])
            if token in self._tokens:
                return payload
            raise HTTPException(status_code=401, detail="Token revoked")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

    def revoke_token(self, token: str):
        """Revoke token."""
        if token in self._tokens:
            del self._tokens[token]

    def check_scope(self, payload: Dict, required_scope: str) -> bool:
        """Check if token has required scope."""
        token_scope = payload.get("scope", "read")
        if token_scope == "admin":
            return True
        if required_scope == "read" and token_scope in ["read", "write"]:
            return True
        if required_scope == "write" and token_scope == "write":
            return True
        return False


# =============================================================================
# RATE LIMITING
# =============================================================================

class RateLimiter:
    """Rate limiter with LRU cache."""

    def __init__(self, max_requests: int, window_seconds: int):
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = {}

    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed."""
        now = time.time()
        window_start = now - self._window_seconds

        if client_id not in self._requests:
            self._requests[client_id] = []

        # Remove old requests
        self._requests[client_id] = [
            ts for ts in self._requests[client_id] if ts > window_start
        ]

        # Check limit
        if len(self._requests[client_id]) >= self._max_requests:
            return False

        # Record request
        self._requests[client_id].append(now)
        return True

    def get_retry_after(self, client_id: str) -> int:
        """Get retry-after seconds."""
        if client_id not in self._requests:
            return 0
        oldest = min(self._requests[client_id])
        return max(0, int(oldest + self._window_seconds - time.time()))


# =============================================================================
# AUDIT LOGGING
# =============================================================================

class AuditLogger:
    """Audit logger for security trail."""

    def __init__(self, log_path: str = "/config/audit"):
        self._log_path = Path(log_path)
        self._log_path.mkdir(parents=True, exist_ok=True)
        self._log_file = self._log_path / "api_audit.log"

    def log(self, event_type: str, details: Dict):
        """Log audit event."""
        entry = {
            "timestamp": time.time(),
            "event_type": event_type,
            **details,
        }
        with open(self._log_file, "a") as f:
            f.write(f"{entry}\n")
        logger.info(f"Audit: {event_type} — {details}")

    def log_auth_failure(self, client_ip: str, reason: str):
        """Log authentication failure."""
        self.log("AUTH_FAILURE", {"client_ip": client_ip, "reason": reason})

    def log_auth_success(self, client_ip: str, api_key: str):
        """Log authentication success."""
        self.log("AUTH_SUCCESS", {"client_ip": client_ip, "api_key_hash": hashlib.sha256(api_key.encode()).hexdigest()[:8]})

    def log_rate_limit(self, client_ip: str):
        """Log rate limit hit."""
        self.log("RATE_LIMIT", {"client_ip": client_ip})


# =============================================================================
# DEPENDENCIES
# =============================================================================

security = HTTPBearer(auto_error=False)
_auth: Optional[JWTAuth] = None
_rate_limiter: Optional[RateLimiter] = None
_audit: Optional[AuditLogger] = None
_start_time: float = 0.0


def init_auth(config: APIConfig) -> JWTAuth:
    """Initialize authentication."""
    global _auth
    _auth = JWTAuth(config.secret_key, config.token_expiry_hours)
    return _auth


def init_rate_limiter(config: APIConfig) -> RateLimiter:
    """Initialize rate limiter."""
    global _rate_limiter
    _rate_limiter = RateLimiter(config.rate_limit_requests, config.rate_limit_window_seconds)
    return _rate_limiter


def init_audit() -> AuditLogger:
    """Initialize audit logger."""
    global _audit
    _audit = AuditLogger()
    return _audit


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Dict:
    """Get current authenticated user."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing credentials")

    if not _auth:
        raise HTTPException(status_code=500, detail="Auth not initialized")

    payload = _auth.verify_token(credentials.credentials)
    return payload


async def check_rate_limit(request: Request) -> bool:
    """Check rate limit."""
    if not _rate_limiter:
        return True

    client_id = request.client.host if request.client else "unknown"

    if not _rate_limiter.is_allowed(client_id):
        if _audit:
            _audit.log_rate_limit(client_id)
        retry_after = _rate_limiter.get_retry_after(client_id)
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )

    return True


# =============================================================================
# EXCEPTION HANDLERS
# =============================================================================

async def http_exception_handler(request: Request, exc: HTTPException) -> Response:
    """Handle HTTP exceptions."""
    error = ErrorResponse(
        error=exc.detail,
        message=str(exc.detail),
        code=f"HTTP_{exc.status_code}",
        timestamp=time.time(),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=error.dict(),
        headers=getattr(exc, "headers", None),
    )


async def general_exception_handler(request: Request, exc: Exception) -> Response:
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}")
    error = ErrorResponse(
        error="Internal Server Error",
        message="An unexpected error occurred",
        code="INTERNAL_ERROR",
        timestamp=time.time(),
    )
    return JSONResponse(status_code=500, content=error.dict())


# =============================================================================
# LIFESPAN
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global _start_time
    _start_time = time.time()

    # Startup
    logger.info("PilotSuite Core REST API starting...")
    init_audit()

    yield

    # Shutdown
    logger.info("PilotSuite Core REST API shutting down...")


# =============================================================================
# APP CREATION
# =============================================================================

def create_app(config: Optional[APIConfig] = None) -> FastAPI:
    """Create FastAPI application."""
    if config is None:
        config = APIConfig()

    app = FastAPI(
        title="PilotSuite Core API",
        description="PilotSuite Core REST API Server",
        version="1.0.0-rc2",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    # Initialize components
    init_auth(config)
    init_rate_limiter(config)

    # Register routes
    register_routes(app, config)
    
    # Register legacy gap endpoints
    app.include_router(legacy_gaps_router)

    return app


# =============================================================================
# ROUTES
# =============================================================================

def register_routes(app: FastAPI, config: APIConfig):
    """Register API routes."""

    @app.get("/health", response_model=HealthResponse, tags=["System"])
    async def health_check():
        """Health check endpoint."""
        return HealthResponse(
            status="healthy",
            version="1.0.0-rc2",
            uptime_seconds=time.time() - _start_time,
            timestamp=time.time(),
            persistence=_get_runtime_persistence_summary(),
        )

    @app.get("/version", tags=["System"])
    async def version():
        """Version info endpoint."""
        return {
            "version": "1.0.0-rc2",
            "build": "takeover/main",
            "python": "3.10+",
            "fastapi": True,
        }

    @app.get("/api/v1/status", response_model=StatusResponse, tags=["System"])
    async def get_status():
        """System status endpoint."""
        return StatusResponse(
            status="operational",
            version="1.0.0-rc2",
            modules={
                "rag": True,
                "ml": True,
                "presence": True,
                "energy": True,
                "brain": True,
                "voice": True,
            },
            capabilities=[
                "vector_search",
                "embedding",
                "presence_detection",
                "energy_optimization",
                "knowledge_graph",
                "voice_pipeline",
            ],
            timestamp=time.time(),
            persistence=_get_runtime_persistence_summary(),
        )

    @app.get("/api/v1/capabilities", tags=["System"])
    async def get_capabilities(user: Dict = Depends(get_current_user)):
        """Module capabilities endpoint.

        Keep capability discovery auth-gated here as well, so the standalone
        FastAPI compatibility server does not advertise a weaker unauthenticated
        contract than the canonical Flask runtime surfaces. Reuse the shared
        voice discovery payload so the compatibility server does not drift back
        to the older reduced voice-module shape.
        """
        return {
            "modules": {
                "rag": ["embedding", "similarity_search", "retrieval"],
                "ml": ["pattern_detection", "habit_learning", "anomaly_detection"],
                "presence": ["multi_sensor_fusion", "wilson_score", "bayesian"],
                "energy": ["forecasting", "or_tools_scheduler", "optimization"],
                "brain": ["graph_store", "neo4j", "networkx", "temporal"],
                "voice": voice_capabilities_module(),
            },
        }

    @app.post("/api/v1/auth/token", response_model=TokenResponse, tags=["Auth"])
    async def create_token(request: TokenRequest):
        """Create JWT token."""
        if not _auth:
            raise HTTPException(status_code=500, detail="Auth not initialized")

        # Validate API key (in production, check against database)
        if not request.api_key or len(request.api_key) < 8:
            if _audit and request.client:
                _audit.log_auth_failure(request.client.host, "invalid_api_key")
            raise HTTPException(status_code=401, detail="Invalid API key")

        token = _auth.create_token(request.api_key, request.scope)

        if _audit and request.client:
            _audit.log_auth_success(request.client.host, request.api_key)

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=config.token_expiry_hours * 3600,
            scope=request.scope,
        )

    @app.post("/api/v1/auth/revoke", tags=["Auth"])
    async def revoke_token(
        token: str,
        user: Dict = Depends(get_current_user),
    ):
        """Revoke JWT token."""
        if not _auth:
            raise HTTPException(status_code=500, detail="Auth not initialized")
        _auth.revoke_token(token)
        return {"status": "revoked"}

    @app.get("/api/v1/events", tags=["Events"])
    async def get_events(
        limit: int = 100,
        user: Dict = Depends(get_current_user),
    ):
        """Get events."""
        # TODO: Implement event retrieval from event store
        return {"events": [], "limit": limit}

    @app.post("/api/v1/events", tags=["Events"])
    async def create_event(
        event: Dict[str, Any],
        user: Dict = Depends(get_current_user),
    ):
        """Create event (ingestion)."""
        # TODO: Implement event ingestion
        return {"status": "created", "event_id": "evt_" + str(time.time())[:10]}

    @app.post("/api/v1/events/batch", tags=["Events"])
    async def create_events_batch(
        events: List[Dict[str, Any]],
        user: Dict = Depends(get_current_user),
    ):
        """Batch event ingestion."""
        # TODO: Implement batch ingestion
        return {"status": "created", "count": len(events)}

    @app.get("/api/v1/vector/stats", tags=["Vector"])
    async def get_vector_stats(
        user: Dict = Depends(get_current_user),
    ):
        """Vector store statistics."""
        # TODO: Get from actual vector store
        return {
            "vector_count": 0,
            "dimension": 384,
            "memory_usage_mb": 0,
        }

    @app.get("/api/v1/vector/vectors", tags=["Vector"])
    async def list_vectors(
        limit: int = 100,
        user: Dict = Depends(get_current_user),
    ):
        """List vectors."""
        # TODO: Implement
        return {"vectors": [], "limit": limit}

    @app.post("/api/v1/vector/embeddings", tags=["Vector"])
    async def create_embeddings(
        texts: List[str],
        user: Dict = Depends(get_current_user),
    ):
        """Create embeddings for texts."""
        # TODO: Implement with embedding pipeline
        return {"embeddings": [], "count": len(texts)}

    @app.get("/api/v1/vector/similar/{entity_id}", tags=["Vector"])
    async def get_similar(
        entity_id: str,
        k: int = 10,
        user: Dict = Depends(get_current_user),
    ):
        """Get similar vectors."""
        # TODO: Implement similarity search
        return {"similar": [], "k": k}

    @app.post("/api/v1/vector/similarity", tags=["Vector"])
    async def similarity_search(
        query: Dict[str, Any],
        user: Dict = Depends(get_current_user),
    ):
        """Custom similarity query."""
        # TODO: Implement
        return {"results": []}

    @app.get("/api/v1/graph/stats", tags=["Graph"])
    async def get_graph_stats(
        user: Dict = Depends(get_current_user),
    ):
        """Graph statistics."""
        # TODO: Get from actual graph store
        return {
            "node_count": 0,
            "edge_count": 0,
            "entity_types": [],
        }

    @app.get("/api/v1/graph/state", tags=["Graph"])
    async def get_graph_state(
        entity_type: Optional[str] = None,
        user: Dict = Depends(get_current_user),
    ):
        """Graph state with filters."""
        # TODO: Implement
        return {"entities": [], "entity_type": entity_type}

    @app.get("/api/v1/graph/patterns", tags=["Graph"])
    async def get_graph_patterns(
        user: Dict = Depends(get_current_user),
    ):
        """Graph patterns."""
        # TODO: Implement
        return {"patterns": []}

    @app.get("/api/v1/graph/snapshot.svg", tags=["Graph"])
    async def get_graph_snapshot(
        user: Dict = Depends(get_current_user),
    ):
        """SVG snapshot of graph."""
        # TODO: Generate SVG
        return Response(content="<svg></svg>", media_type="image/svg+xml")

    @app.get("/api/v1/mood/state", tags=["Mood"])
    async def get_mood_state(
        user: Dict = Depends(get_current_user),
    ):
        """Current mood state."""
        # TODO: Implement
        return {"mood": "neutral", "score": 0.5}

    @app.get("/api/v1/mood/score", tags=["Mood"])
    async def get_mood_score(
        user: Dict = Depends(get_current_user),
    ):
        """Mood score."""
        # TODO: Implement
        return {"score": 0.5, "timestamp": time.time()}

    @app.get("/api/v1/neurons", tags=["Neural"])
    async def get_neurons(
        user: Dict = Depends(get_current_user),
    ):
        """Neural system state."""
        # TODO: Implement
        return {"neurons": [], "active_count": 0}

    @app.post("/api/v1/neurons/evaluate", tags=["Neural"])
    async def evaluate_neurons(
        input_data: Dict[str, Any],
        user: Dict = Depends(get_current_user),
    ):
        """Evaluate neurons."""
        # TODO: Implement
        return {"result": {}, "activation": []}

    @app.get("/api/v1/habitus/mine", tags=["Habitus"])
    async def get_habitus(
        user: Dict = Depends(get_current_user),
    ):
        """User habitus."""
        # TODO: Implement
        return {"habitus": {}, "suggestions": []}

    @app.get("/api/v1/habitus/dashboard-cards", tags=["Habitus"])
    async def get_dashboard_cards(
        user: Dict = Depends(get_current_user),
    ):
        """Dashboard cards."""
        # TODO: Implement
        return {"cards": []}

    @app.get("/api/v1/search", tags=["Search"])
    async def search(
        q: str,
        limit: int = 20,
        user: Dict = Depends(get_current_user),
    ):
        """Search API."""
        # TODO: Implement semantic search
        return {"results": [], "query": q}

    @app.get("/api/v1/tags", tags=["Tags"])
    async def list_tags(
        user: Dict = Depends(get_current_user),
    ):
        """List all tags."""
        # TODO: Implement
        return {"tags": []}

    @app.get("/api/v1/candidates", tags=["Candidates"])
    async def list_candidates(
        user: Dict = Depends(get_current_user),
    ):
        """List candidates."""
        # TODO: Implement
        return {"candidates": []}

    @app.get("/api/v1/dev/health", tags=["Dev"])
    async def dev_health(
        user: Dict = Depends(get_current_user),
    ):
        """Dev health check."""
        return {"status": "ok", "debug": config.debug}

    @app.get("/api/v1/dashboard/brain-summary", tags=["Dashboard"])
    async def get_brain_summary(
        user: Dict = Depends(get_current_user),
    ):
        """Dashboard brain summary."""
        # TODO: Implement
        return {"summary": {}}

    @app.get("/api/v1/dashboard/health", tags=["Dashboard"])
    async def get_dashboard_health(
        user: Dict = Depends(get_current_user),
    ):
        """Dashboard health."""
        # TODO: Implement
        return {"health": {}}

    # Rate limit check for all routes
    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        """Rate limit middleware."""
        await check_rate_limit(request)
        response = await call_next(request)
        return response


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run API server."""
    config = APIConfig(debug=True)
    app = create_app(config)

    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level="info" if config.debug else "warning",
    )


if __name__ == "__main__":
    main()
