# Rate Limiting API-Dokumentation

## Übersicht

Die Rate-Limiting-Implementierung in PilotSuite Styx Core v13.9.0 schützt die API vor Missbrauch und stellt faire Nutzung für alle Clients sicher.

**Standard-Limit:** 100 Requests pro Minute pro Client

## 🎯 Architektur

### Token-Bucket-Algorithmus

```
┌─────────────────────────────────────────┐
│           Token Bucket                  │
│  ┌─────────────────────────────────┐    │
│  │  Capacity: 100 Tokens           │    │
│  │  Refill Rate: 1.67 Tokens/sec   │    │
│  │                                 │    │
│  │  Current: 87 Tokens ████████░░  │    │
│  └─────────────────────────────────┘    │
│                                         │
│  Request → Consume Token → Success      │
│  Request → No Token → 429 Too Many      │
└─────────────────────────────────────────┘
```

### Client-Identifikation

```
┌──────────────────────────────────────────────────┐
│            Client Identification                 │
│                                                  │
│  Priority 1: Authenticated User ID               │
│  ┌────────────────────────────────────────┐     │
│  │ user:a1b2c3d4-e5f6-7890-abcd-ef123456  │     │
│  └────────────────────────────────────────┘     │
│                                                  │
│  Priority 2: API Key (hashed)                    │
│  ┌────────────────────────────────────────┐     │
│  │ apikey:8f3a2b1c9d4e5f6a                │     │
│  └────────────────────────────────────────┘     │
│                                                  │
│  Priority 3: IP Address (fallback)               │
│  ┌────────────────────────────────────────┐     │
│  │ ip:192.168.1.100                       │     │
│  └────────────────────────────────────────┘     │
└──────────────────────────────────────────────────┘
```

## 📊 Rate-Limit-Konfiguration

### Globale Standards

```python
# copilot_core/api/rate_limiter.py

RATE_LIMITS = {
    "default": "100/minute",      # Standard für alle Endpunkte
    "burst": "20/second",         # Burst-Toleranz
    "auth": "5/minute",           # Login-Versuche
    "search": "30/minute",        # Resource-intensive Searches
    "write": "50/minute",         # Write-Operations
    "read": "200/minute",         # Read-Operations
}
```

### Endpunkt-spezifische Limits

| Endpunkt | Limit | Begründung |
|----------|-------|------------|
| `POST /auth/login` | 5/min | Brute-Force-Schutz |
| `POST /auth/register` | 3/min | Spam-Schutz |
| `GET /search` | 30/min | RAG-Queries sind resource-intensiv |
| `POST /zones` | 50/min | Write-Operation |
| `PUT /zones/{id}` | 50/min | Write-Operation |
| `DELETE /zones/{id}` | 20/min | Kritische Operation |
| `GET /zones` | 100/min | Standard Read |
| `GET /rooms` | 100/min | Standard Read |
| `GET /devices` | 100/min | Standard Read |
| `WS /dashboard` | 60/min | WebSocket Messages |

## 🔧 Implementierung

### Middleware-Setup

```python
# copilot_core/main.py

from slowapi import SlowAPILimiter
from slowapi.util import get_remote_address
from copilot_core.api.rate_limiter import (
    limiter,
    get_client_identifier,
    rate_limit_exceeded_handler
)

# Initialisierung
limiter = SlowAPILimiter(key_func=get_client_identifier)

# App-Integration
app = FastAPI(
    title="PilotSuite Styx Core",
    version="12.7.0"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Middleware für alle Routes
app.add_middleware(SlowAPILimiterMiddleware)
```

### Client-Identifier-Funktion

```python
# copilot_core/api/rate_limiter.py

import hashlib
from fastapi import Request

def get_client_identifier(request: Request) -> str:
    """
    Identifiziert Client für Rate Limiting.
    
    Priorität:
    1. Authenticated User ID
    2. API Key (gehasht)
    3. IP-Adresse (Fallback)
    """
    # 1. Authenticated User (höchste Priorität)
    if hasattr(request.state, 'user_id') and request.state.user_id:
        return f"user:{request.state.user_id}"
    
    # 2. Auth Token (X-Auth-Token bevorzugt; X-API-Key deprecated seit v13.5.3)
    auth_token = request.headers.get("X-Auth-Token") or request.headers.get("X-API-Key")
    if auth_token:
        # Hash für Privacy (speichern nicht den Klartext-Key)
        key_hash = hashlib.sha256(auth_token.encode()).hexdigest()[:16]
        return f"apikey:{key_hash}"
    
    # 3. IP-Adresse (Fallback)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"
    
    return f"ip:{ip}"
```

### Decorator-Verwendung

```python
# copilot_core/api/routes/zones.py

from copilot_core.api.rate_limiter import limiter
from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/zones")
@limiter.limit("100/minute")
async def get_zones(request: Request):
    """
    Alle Zones abrufen.
    Limit: 100 Requests/Minute
    """
    zones = await zone_service.list_zones()
    return {"zones": zones}

@router.post("/zones")
@limiter.limit("50/minute")
async def create_zone(request: Request, zone_data: ZoneCreateSchema):
    """
    Neue Zone erstellen.
    Limit: 50 Requests/Minute (Write-Operation)
    """
    zone = await zone_service.create(zone_data)
    return {"zone": zone}

@router.delete("/zones/{zone_id}")
@limiter.limit("20/minute")
async def delete_zone(request: Request, zone_id: str):
    """
    Zone löschen.
    Limit: 20 Requests/Minute (kritische Operation)
    """
    await zone_service.delete(zone_id)
    return {"status": "deleted"}
```

## 📡 Response Headers

### Erfolgreiche Request (200 OK)

```http
HTTP/1.1 200 OK
Content-Type: application/json
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1709305260

{
  "zones": [...]
}
```

**Header-Erklärung:**
- `X-RateLimit-Limit`: Maximale Requests im Zeitfenster (100)
- `X-RateLimit-Remaining`: Verbleibende Requests (87)
- `X-RateLimit-Reset`: Unix-Timestamp, wann das Limit resetted wird

### Rate-Limit-Überschreitung (429 Too Many Requests)

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
Retry-After: 45
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1709305260

{
  "error": "rate_limit_exceeded",
  "message": "Zu viele Anfragen. Bitte warten Sie.",
  "retry_after": 45,
  "limit": "100/minute",
  "reset_at": "2026-03-01T23:21:00Z"
}
```

**Response-Felder:**
- `error`: Error-Code (`rate_limit_exceeded`)
- `message`: Menschlesbare Nachricht
- `retry_after`: Sekunden bis zum nächsten Versuch
- `limit`: Das überschrittene Limit
- `reset_at`: ISO-8601 Timestamp für Reset

## 🛠️ Handler-Implementierung

### Exception Handler

```python
# copilot_core/api/rate_limiter.py

from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta

async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """
    Handler für Rate-Limit-Überschreitungen.
    
    Returns eine strukturierte 429 Response mit Retry-Informationen.
    """
    retry_after = exc.detail.retry_after
    reset_at = datetime.utcnow() + timedelta(seconds=retry_after)
    
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": "Zu viele Anfragen. Bitte warten Sie.",
            "retry_after": retry_after,
            "limit": str(exc.detail.limit),
            "reset_at": reset_at.isoformat() + "Z"
        },
        headers={
            "Retry-After": str(retry_after),
        }
    )
```

## 📈 Monitoring & Metriken

### Prometheus-Metriken

```python
# copilot_core/metrics.py

from prometheus_client import Counter, Histogram, Gauge

# Rate-Limit-Metriken
RATE_LIMIT_TOTAL = Counter(
    'rate_limit_requests_total',
    'Total number of requests',
    ['endpoint', 'client_type']
)

RATE_LIMIT_EXCEEDED = Counter(
    'rate_limit_exceeded_total',
    'Number of rate limit exceeded responses',
    ['endpoint', 'limit']
)

RATE_LIMIT_REMAINING = Gauge(
    'rate_limit_remaining',
    'Remaining requests in current window',
    ['client_id']
)

RATE_LIMIT_RESET_TIME = Gauge(
    'rate_limit_reset_seconds',
    'Seconds until rate limit reset',
    ['client_id']
)
```

### Logging

```python
# Structured Logging für Rate-Limit-Events

import logging
from datetime import datetime

audit_logger = logging.getLogger('audit')

async def log_rate_limit_event(
    client_id: str,
    endpoint: str,
    limit: str,
    remaining: int,
    exceeded: bool
):
    """Loggt Rate-Limit-Event"""
    audit_logger.info({
        "timestamp": datetime.utcnow().isoformat(),
        "event": "rate_limit",
        "client_id": client_id,
        "endpoint": endpoint,
        "limit": limit,
        "remaining": remaining,
        "exceeded": exceeded,
    })

# Beispiel-Log-Eintrag:
# {
#   "timestamp": "2026-03-01T23:15:42.123Z",
#   "event": "rate_limit",
#   "client_id": "user:a1b2c3d4",
#   "endpoint": "GET /zones",
#   "limit": "100/minute",
#   "remaining": 0,
#   "exceeded": true
# }
```

## 🧪 Testing

### Unit Tests

```python
# tests/test_rate_limiting.py

import pytest
from fastapi.testclient import TestClient

client = TestClient(app)

def test_rate_limit_headers():
    """Testet Rate-Limit-Header in Response"""
    response = client.get("/zones")
    
    assert response.status_code == 200
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Reset" in response.headers
    
    limit = int(response.headers["X-RateLimit-Limit"])
    assert limit == 100

def test_rate_limit_exceeded():
    """Testet 429 Response bei Limit-Überschreitung"""
    # 105 Requests senden (Limit: 100/min)
    for i in range(105):
        response = client.get("/zones")
        
        if i < 100:
            assert response.status_code == 200
        else:
            assert response.status_code == 429
            
            # Response-Struktur prüfen
            data = response.json()
            assert data["error"] == "rate_limit_exceeded"
            assert "retry_after" in data
            assert "Retry-After" in response.headers

def test_rate_limit_by_client():
    """Testet, dass Limits pro Client gelten"""
    # Client A: 100 Requests (X-Auth-Token bevorzugt seit v13.5.3)
    for i in range(100):
        response = client.get("/zones", headers={"X-Auth-Token": "token-a"})
        assert response.status_code == 200

    # Client A: 101. Request → 429
    response = client.get("/zones", headers={"X-Auth-Token": "token-a"})
    assert response.status_code == 429

    # Client B: 1. Request → 200 (separates Limit)
    response = client.get("/zones", headers={"X-Auth-Token": "token-b"})
    assert response.status_code == 200

def test_auth_endpoint_stricter_limit():
    """Testet strikteres Limit für Auth-Endpoints"""
    # Login-Endpoint: nur 5/min
    for i in range(6):
        response = client.post("/auth/login", json={
            "username": "test",
            "password": "test"
        })
        
        if i < 5:
            assert response.status_code in [200, 401]  # OK oder Invalid Creds
        else:
            assert response.status_code == 429  # Rate Limited
```

### Integration Tests

```python
# tests/integration/test_rate_limiting_integration.py

@pytest.mark.asyncio
async def test_rate_limit_with_concurrent_requests():
    """Testet Rate Limiting unter paralleler Last"""
    import asyncio
    from aiohttp import ClientSession
    
    async def make_request(session, request_id):
        async with session.get("http://localhost:8000/zones") as response:
            return response.status
    
    async with ClientSession() as session:
        # 150 parallele Requests senden
        tasks = [make_request(session, i) for i in range(150)]
        results = await asyncio.gather(*tasks)
        
        # Zählen
        success_count = sum(1 for r in results if r == 200)
        limited_count = sum(1 for r in results if r == 429)
        
        # ~100 sollten erfolgreich sein, ~50 limited
        assert 95 <= success_count <= 105  # Toleranz für Race Conditions
        assert 45 <= limited_count <= 55
```

## 🔐 Security-Aspekte

### Brute-Force-Schutz

```python
# Auth-Endpoints haben strikte Limits
@router.post("/auth/login")
@limiter.limit("5/minute")  # Nur 5 Login-Versuche pro Minute
async def login(request: Request, credentials: LoginSchema):
    """
    Login-Endpoint mit Brute-Force-Schutz.
    
    Limit: 5 Requests/Minute verhindert Passwort-Raten.
    Bei 5 Fehlversuchen muss der Client 1 Minute warten.
    """
    user = await auth_service.authenticate(credentials)
    if not user:
        # Logging für Security-Monitoring
        await log_security_event(
            event_type="auth",
            action="login_failed",
            ip_address=request.client.host,
            details={"username": credentials.username}
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    return {"token": user.token}
```

### DDoS-Mitigation

```python
# Burst-Limit für plötzliche Traffic-Spitzen
@limiter.limit("20/second")  # Max 20 Requests pro Sekunde
@limiter.limit("100/minute")  # Max 100 Requests pro Minute
async def protected_endpoint(request: Request):
    """
    Doppelschicht-Schutz:
    - Burst: 20/sec verhindert kurze Spitzen
    - Minute: 100/min verhindert anhaltende Last
    """
    pass
```

## 📝 Best Practices

### Client-Seite

**Empfohlenes Client-Verhalten:**

```python
# Beispiel: Respektvoller Client mit Retry-Logic

import time
from requests import Session

class RespectfulClient:
    def __init__(self, base_url: str):
        self.session = Session()
        self.base_url = base_url
    
    def request(self, method: str, endpoint: str, max_retries: int = 3):
        """
        Macht Request mit automatischem Retry bei Rate-Limiting.
        """
        for attempt in range(max_retries):
            response = self.session.request(
                method,
                f"{self.base_url}{endpoint}"
            )
            
            if response.status_code == 429:
                # Rate-Limited: Warte und retry
                retry_after = int(response.headers.get("Retry-After", 60))
                print(f"Rate-limited. Warte {retry_after}s...")
                time.sleep(retry_after)
                continue
            
            # Success oder anderer Error
            response.raise_for_status()
            return response
        
        raise Exception("Max retries exceeded due to rate limiting")

# Verwendung
client = RespectfulClient("http://localhost:8000")
zones = client.request("GET", "/zones")
```

### Server-Seite

**Empfehlungen:**

1. **Logging aktivieren:** Alle Rate-Limit-Events loggen für Security-Monitoring
2. **Alerting:** Alerts bei ungewöhnlich hohen Rate-Limit-Überschreitungen
3. **Dokumentation:** Rate-Limits in API-Dokumentation klar kommunizieren
4. **Graceful Degradation:** 429 mit hilfreichen Retry-Informationen
5. **Monitoring:** Dashboards für Rate-Limit-Metriken

## 🔧 Konfiguration

### Environment Variables

```bash
# Rate-Limiting Konfiguration
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT=100/minute
RATE_LIMIT_BURST=20/second
RATE_LIMIT_AUTH=5/minute
RATE_LIMIT_SEARCH=30/minute
RATE_LIMIT_WRITE=50/minute
RATE_LIMIT_READ=200/minute

# Storage-Backend (für verteilte Systeme)
RATE_LIMIT_STORAGE=memory  # memory, redis, memcached
RATE_LIMIT_REDIS_URL=redis://localhost:6379

# Monitoring
RATE_LIMIT_METRICS_ENABLED=true
RATE_LIMIT_LOGGING_ENABLED=true
```

### Custom Limits pro Endpunkt

```python
# copilot_core/api/rate_limiter.py

from functools import wraps

def custom_rate_limit(limit_string: str):
    """
    Decorator für benutzerdefinierte Rate-Limits.
    
    Args:
        limit_string: Format "X/second", "Y/minute", "Z/hour", "W/day"
    
    Example:
        @custom_rate_limit("10/hour")
        async def expensive_operation():
            pass
    """
    def decorator(func):
        @wraps(func)
        @limiter.limit(limit_string)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Verwendung
@router.post("/expensive-export")
@custom_rate_limit("10/hour")  # Nur 10 Export-Stunden
async def export_data(request: Request):
    """Resource-intensive Operation mit striktem Limit"""
    pass
```

## 📊 Metriken & Monitoring

### Dashboard-Metriken

**Wichtige KPIs:**

| Metrik | Beschreibung | Zielwert |
|--------|--------------|----------|
| Rate-Limit-Hit-Rate | % der Requests innerhalb Limits | >95% |
| Rate-Limit-Exceeded-Rate | % der 429 Responses | <5% |
| Avg Retry-After-Time | Durchschnittliche Wartezeit | <60s |
| Clients-Hit-Limit | Unique Clients, die Limit erreichen | Monitoring |

### Alerting-Regeln

```yaml
# alerting.yaml

alerts:
  - name: HighRateLimitExceededRate
    condition: rate_limit_exceeded_rate > 10%
    duration: 5m
    severity: warning
    message: "More than 10% of requests are rate-limited"
  
  - name: SingleClientAbuse
    condition: single_client_exceeded_count > 100
    duration: 1m
    severity: critical
    message: "Single client exceeded rate limit 100+ times"
  
  - name: AuthBruteForceAttempt
    condition: auth_endpoint_exceeded_rate > 50%
    duration: 1m
    severity: critical
    message: "Possible brute-force attack on auth endpoint"
```

---

*Dokumentation erstellt für PilotSuite Styx Core v13.9.0*
*Rate-Limiting: 100 Req/Min pro Client ✅*
*Letzte Aktualisierung: 2026-03-01*
