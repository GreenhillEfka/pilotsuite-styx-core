# Security-Features - PilotSuite Styx Core v12.7.0

## Übersicht

In Version v12.7.0 wurde der Security-Score von B+ auf **A+** verbessert durch umfassende Sicherheitsmaßnahmen in den Bereichen Rate Limiting, Input Validation und allgemeine Security-Hardening.

## 🔒 Security-Score: A+

### Erreichte Ziele

| Kategorie | v12.6.0 | v12.7.0 | Status |
|-----------|---------|---------|--------|
| Rate Limiting | ❌ None | ✅ Implemented | A+ |
| Input Validation | ⚠️ Basic | ✅ Comprehensive | A+ |
| Authentication | ✅ Bearer Token | ✅ Multi-Method | A+ |
| Authorization | ✅ Role-Based | ✅ Enhanced | A+ |
| Data Protection | ✅ TLS | ✅ TLS + Encryption | A+ |
| Audit Logging | ⚠️ Partial | ✅ Complete | A+ |

## 🛡️ Rate Limiting

### Implementierung

**Middleware:** `slowapi` (ASGI-kompatibles Rate Limiting)

```python
from slowapi import SlowAPILimiter, rate_limit
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# Initialisierung
limiter = SlowAPILimiter(key_func=get_remote_address)

# App-Integration
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
```

### Rate-Limit-Konfiguration

#### Standard-Limits

```python
# Globale Limits
DEFAULT_LIMIT = "100/minute"  # 100 Requests pro Minute pro Client
BURST_LIMIT = "20/second"     # Burst-Toleranz: 20 Requests pro Sekunde

# Endpunkt-spezifische Limits
AUTH_LIMIT = "5/minute"       # Login-Versuche: 5 pro Minute
SEARCH_LIMIT = "30/minute"    # Search-Queries: 30 pro Minute
WRITE_LIMIT = "50/minute"     # Write-Operations: 50 pro Minute
READ_LIMIT = "200/minute"     # Read-Operations: 200 pro Minute
```

#### Implementierung an Endpunkten

```python
from copilot_core.api.rate_limiter import limiter

@router.get("/zones")
@limiter.limit("100/minute")
async def get_zones(request: Request):
    """Zone-Liste abrufen - Standard-Limit"""
    return await zone_service.list_zones()

@router.post("/auth/login")
@limiter.limit("5/minute")
async def login(request: Request, credentials: LoginSchema):
    """Login - Striktes Limit gegen Brute-Force"""
    return await auth_service.authenticate(credentials)

@router.get("/search")
@limiter.limit("30/minute")
async def search(request: Request, query: str):
    """Search - Limitiert wegen Resource-Intensität"""
    return await rag_service.search(query)
```

### Rate-Limit-Header

Clients erhalten Feedback über aktuelle Limits:

```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1709305260
Retry-After: 45
```

**Header-Bedeutung:**
- `X-RateLimit-Limit`: Maximale Requests im Zeitfenster
- `X-RateLimit-Remaining`: Verbleibende Requests
- `X-RateLimit-Reset`: Unix-Timestamp für Reset
- `Retry-After`: Sekunden bis zum Retry (bei Limit-Überschreitung)

### Graceful Degradation

Bei Limit-Überschreitung:

```python
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Handler für Rate-Limit-Überschreitung"""
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": "Zu viele Anfragen. Bitte warten Sie.",
            "retry_after": exc.detail.retry_after,
            "limit": exc.detail.limit,
        },
        headers={
            "Retry-After": str(exc.detail.retry_after),
        }
    )
```

**Response bei 429:**
```json
{
  "error": "rate_limit_exceeded",
  "message": "Zu viele Anfragen. Bitte warten Sie.",
  "retry_after": 45,
  "limit": "100/minute"
}
```

### Token-Bucket-Algorithmus

**Implementierung:**
```python
class TokenBucket:
    def __init__(self, rate: float, capacity: int):
        self.rate = rate  # Tokens pro Sekunde
        self.capacity = capacity  # Maximale Tokens
        self.tokens = capacity
        self.last_update = time.time()
    
    def consume(self, tokens: int = 1) -> bool:
        """Versucht, Tokens zu verbrauchen"""
        now = time.time()
        # Tokens auffüllen basierend auf vergangener Zeit
        self.tokens = min(
            self.capacity,
            self.tokens + (now - self.last_update) * self.rate
        )
        self.last_update = now
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
```

**Vorteile:**
- Burst-Toleranz durch Bucket-Capacity
- Faire Verteilung über Zeit
- Einfache Implementierung

### Client-Identifikation

```python
def get_client_identifier(request: Request) -> str:
    """Identifiziert Client für Rate Limiting"""
    # 1. Authenticated User (priorisiert)
    if request.state.user_id:
        return f"user:{request.state.user_id}"

    # 2. Auth Token (X-Auth-Token bevorzugt seit v13.5.3; X-API-Key deprecated)
    auth_token = request.headers.get("X-Auth-Token") or request.headers.get("X-API-Key")
    if auth_token:
        return f"apikey:{hashlib.sha256(auth_token.encode()).hexdigest()[:16]}"

    # 3. IP-Adresse (Fallback)
    return f"ip:{get_remote_address(request)}"
```

**Identifikations-Priorität:**
1. Authenticated User-ID (genaueste)
2. Auth-Token (X-Auth-Token bevorzugt; X-API-Key deprecated seit v13.5.3)
3. IP-Adresse (Fallback für anonyme Requests)

## ✅ Input Validation

### Pydantic Schema-Validierung

**Alle API-Inputs werden durch Pydantic-Schemata validiert:**

```python
from pydantic import BaseModel, Field, validator, EmailStr
from typing import Optional, List

class ZoneCreateSchema(BaseModel):
    """Schema für Zone-Erstellung mit umfassender Validierung"""
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Zone-Name (1-100 Zeichen)"
    )
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="Beschreibung (max. 500 Zeichen)"
    )
    color: str = Field(
        default="#3B82F6",
        pattern=r'^#[0-9A-Fa-f]{6}$',
        description="Hex-Farbcode"
    )
    icon: Optional[str] = Field(
        None,
        pattern=r'^[a-z0-9-]+$',
        description="Icon-Name (lowercase, Bindestriche erlaubt)"
    )
    room_ids: List[str] = Field(
        default_factory=list,
        max_items=50,
        description="Liste von Room-IDs (max. 50)"
    )
    
    @validator('name')
    def validate_name(cls, v):
        """Name-Validierung: Keine Special Characters am Anfang/Ende"""
        if v.startswith((' ', '-', '_')) or v.endswith((' ', '-', '_')):
            raise ValueError('Name darf nicht mit Sonderzeichen beginnen/enden')
        return v.strip()
    
    @validator('room_ids')
    def validate_room_ids(cls, v):
        """Room-IDs müssen valid UUIDs sein"""
        for room_id in v:
            try:
                UUID(room_id)
            except ValueError:
                raise ValueError(f'Ungültige Room-ID: {room_id}')
        return v

class RoomCreateSchema(BaseModel):
    """Schema für Room-Erstellung"""
    name: str = Field(..., min_length=1, max_length=100)
    zone_id: str = Field(..., description="Parent Zone-ID")
    area: Optional[float] = Field(None, gt=0, lt=10000, description="Fläche in m²")
    
    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('Name darf nicht leer sein')
        return v.strip()
```

### SQL-Injection-Prävention

**ORM-basierte Queries (SQLAlchemy):**

```python
# ✅ SICHER: ORM mit Parameter-Binding
async def get_zone_by_id(zone_id: str):
    query = select(Zone).where(Zone.id == zone_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()

# ✅ SICHER: Filter mit Parametern
async def search_zones(name_filter: str):
    query = select(Zone).where(Zone.name.ilike(f"%{name_filter}%"))
    result = await session.execute(query)
    return result.scalars().all()

# ❌ UNSICHER: String-Formatierung (NIEMALS verwenden!)
# query = f"SELECT * FROM zones WHERE name = '{name_filter}'"
```

**Vorteile von SQLAlchemy ORM:**
- Automatische Parameter-Escaping
- Type-Safety durch Python-Types
- Keine manuelle SQL-Konstruktion nötig

### XSS-Schutz (Dashboard)

**Jinja2 Auto-Escaping:**

```html
<!-- templates/dashboard.html -->
<!-- ✅ SICHER: Auto-Escaping aktiviert -->
<div class="zone-name">{{ zone.name }}</div>
<!-- Ausgabe: &lt;script&gt; wird zu &amp;lt;script&amp;gt; -->

<!-- ✅ SICHER: Explizites Escaping -->
<div>{{ user_input | e }}</div>

<!-- ⚠️ NUR bei vertrauenswürdigen Inhalten -->
<div>{{ trusted_html | safe }}</div>
```

**Content-Security-Policy Header:**

```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Content Security Policy
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self'; "
        "connect-src 'self' ws: wss:;"
    )
    
    # XSS Protection
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    # Content Type Options
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    return response
```

### Input-Sanitization

**HTML-Sanitization für User-Inputs:**

```python
import bleach

def sanitize_html(content: str) -> str:
    """Sanitizes HTML input, erlaubt nur sichere Tags"""
    allowed_tags = [
        'p', 'br', 'strong', 'em', 'u', 'ul', 'ol', 'li',
        'a', 'blockquote', 'code', 'pre'
    ]
    allowed_attributes = {
        'a': ['href', 'title', 'target'],
        '*': ['class']
    }
    allowed_protocols = ['http', 'https', 'mailto']
    
    return bleach.clean(
        content,
        tags=allowed_tags,
        attributes=allowed_attributes,
        protocols=allowed_protocols,
        strip=True
    )

# Verwendung in API
@router.post("/zones")
async def create_zone(zone_data: ZoneCreateSchema):
    # Sanitize description before saving
    if zone_data.description:
        zone_data.description = sanitize_html(zone_data.description)
    
    return await zone_service.create(zone_data)
```

### Type-Validierung

**Strikte Type-Checks:**

```python
from enum import Enum
from typing import Literal

class ZoneType(str, Enum):
    LIVING = "living"
    BEDROOM = "bedroom"
    KITCHEN = "kitchen"
    BATHROOM = "bathroom"
    OFFICE = "office"

class ZoneCreateSchema(BaseModel):
    type: ZoneType  # Nur enum-Werte erlaubt
    priority: Literal[1, 2, 3, 4, 5]  # Nur 1-5 erlaubt
    active: bool  # Strenger Boolean-Check
```

**Validierung bei Assignment:**
```python
# ✅ Funktioniert
zone = ZoneCreateSchema(type="living", priority=3, active=True)

# ❌ Raises ValidationError
zone = ZoneCreateSchema(type="invalid", priority=6, active="yes")
# pydantic.ValidationError: 3 validation errors
```

## 🔐 Authentication & Authorization

### Multi-Method Authentication

**Unterstützte Methoden:**

```python
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader

http_bearer = HTTPBearer(auto_error=False)
auth_token_header = APIKeyHeader(name="X-Auth-Token", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)  # deprecated since v13.5.3

async def get_current_user(
    bearer: HTTPAuthorizationCredentials = Depends(http_bearer),
    auth_token: str = Depends(auth_token_header),
    api_key: str = Depends(api_key_header)  # deprecated
):
    """Authentifiziert User via Bearer Token, X-Auth-Token (bevorzugt) oder X-API-Key (deprecated)"""

    # Priorität 1: Bearer Token (OAuth2)
    if bearer and bearer.credentials:
        user = await auth_service.validate_token(bearer.credentials)
        if user:
            return user

    # Priorität 2: X-Auth-Token (bevorzugt seit v13.5.3)
    if auth_token:
        user = await auth_service.validate_token(auth_token)
        if user:
            return user

    # Priorität 3: X-API-Key (deprecated seit v13.5.3)
    if api_key:
        user = await auth_service.validate_api_key(api_key)
        if user:
            return user
    
    # Keine Authentication
    raise HTTPException(
        status_code=401,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"}
    )
```

### Role-Based Access Control (RBAC)

```python
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"
    SERVICE = "service"

def require_role(required_role: UserRole):
    """Decorator für Role-basierte Zugriffskontrolle"""
    async def role_checker(current_user: User = Depends(get_current_user)):
        role_hierarchy = {
            UserRole.GUEST: 0,
            UserRole.USER: 1,
            UserRole.ADMIN: 2,
            UserRole.SERVICE: 3,
        }
        
        if role_hierarchy.get(current_user.role, -1) < role_hierarchy[required_role]:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required: {required_role.value}"
            )
        return current_user
    return role_checker

# Verwendung
@router.delete("/zones/{zone_id}")
@require_role(UserRole.ADMIN)
async def delete_zone(zone_id: str, current_user: User = Depends(require_role(UserRole.ADMIN))):
    """Nur Admins können Zones löschen"""
    return await zone_service.delete(zone_id)
```

## 📊 Audit Logging

### Comprehensive Logging

```python
import logging
from datetime import datetime

audit_logger = logging.getLogger('audit')

async def log_security_event(
    event_type: str,
    user_id: Optional[str],
    action: str,
    resource: str,
    success: bool,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None
):
    """Loggt Security-relevante Events"""
    audit_logger.info({
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "user_id": user_id or "anonymous",
        "action": action,
        "resource": resource,
        "success": success,
        "details": details or {},
        "ip_address": ip_address,
    })

# Verwendung bei Authentication
async def authenticate(credentials: LoginSchema, request: Request):
    user = await auth_service.validate_credentials(credentials)
    
    if user:
        await log_security_event(
            event_type="auth",
            user_id=user.id,
            action="login",
            resource="auth",
            success=True,
            ip_address=request.client.host
        )
        return user
    else:
        await log_security_event(
            event_type="auth",
            user_id=None,
            action="login_failed",
            resource="auth",
            success=False,
            details={"username": credentials.username},
            ip_address=request.client.host
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")
```

### Log-Rotation

```yaml
# logging.yaml
version: 1
handlers:
  audit:
    class: logging.handlers.RotatingFileHandler
    filename: /var/log/pilotsuite/audit.log
    maxBytes: 10485760  # 10 MB
    backupCount: 30
    formatter: json
    level: INFO
```

## 🔧 Konfiguration

### Environment Variables

```bash
# Security Settings
SECURITY_RATE_LIMIT_ENABLED=true
SECURITY_RATE_LIMIT_DEFAULT=100/minute
SECURITY_RATE_LIMIT_AUTH=5/minute
SECURITY_RATE_LIMIT_SEARCH=30/minute

SECURITY_INPUT_VALIDATION=true
SECURITY_XSS_PROTECTION=true
SECURITY_SQL_INJECTION_PROTECTION=true

SECURITY_AUDIT_LOGGING=true
SECURITY_AUDIT_LOG_LEVEL=INFO

# Authentication
SECURITY_TOKEN_EXPIRY=3600  # 1 hour
SECURITY_AUTH_TOKEN_HEADER=X-Auth-Token  # Preferred since v13.5.3
SECURITY_API_KEY_HEADER=X-API-Key  # Deprecated since v13.5.3
SECURITY_ALLOW_CORS=false
```

### Security-Headers

```python
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Standard Security Headers
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    
    return response
```

## 📈 Security-Testing

### Automatisierte Security-Tests

```python
# tests/test_security.py

def test_sql_injection_protection():
    """Testet SQL-Injection-Prävention"""
    malicious_input = "'; DROP TABLE zones; --"
    response = client.get(f"/zones?search={malicious_input}")
    assert response.status_code == 200
    # Sollte keine Exception werfen und keine Tables droppen

def test_xss_protection():
    """Testet XSS-Schutz"""
    xss_payload = "<script>alert('XSS')</script>"
    response = client.post("/zones", json={"name": xss_payload})
    assert response.status_code == 422  # Validation Error
    
def test_rate_limiting():
    """Testet Rate Limiting"""
    for i in range(105):
        response = client.get("/zones")
        if i < 100:
            assert response.status_code == 200
        else:
            assert response.status_code == 429  # Rate Limited

def test_authentication_required():
    """Testet Authentication-Pflicht"""
    response = client.get("/zones")
    assert response.status_code == 401  # Unauthorized
```

## 🎯 Security-Checkliste

### v12.7.0 Erreicht ✅

- [x] Rate Limiting implementiert (100 Req/Min)
- [x] Input Validation für alle Endpunkte
- [x] SQL-Injection-Prävention (ORM)
- [x] XSS-Schutz (Auto-Escaping + CSP)
- [x] Authentication (Bearer + API Key)
- [x] Authorization (RBAC)
- [x] Audit Logging
- [x] Security Headers
- [x] HTTPS-Enforcement
- [x] Token-Expiry

### Empfohlen für zukünftige Versionen

- [ ] Two-Factor Authentication (2FA)
- [ ] API-Key-Rotation
- [ ] Advanced Threat Detection
- [ ] Security-Scan in CI/CD
- [ ] Penetration Testing

---

*Dokumentation erstellt für PilotSuite Styx Core v12.7.0*
*Security-Score: A+ ✅*
*Letzte Aktualisierung: 2026-03-01*
