"""
Zone-Management API für PilotSuite Styx Core

Endpoints für Habituszone-Zuordnung, Matching und Review.
"""

from fastapi import APIRouter, Query, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Any, List, Dict, Optional
import logging

from copilot_core.api.error_models import ErrorResponse, error_response_payload
from copilot_core.homeassistant.habitus_zones import (
    HABITUS_ZONES, ZoneType, HabitusZone, get_all_zones
)
from copilot_core.homeassistant.zone_matcher import (
    ZoneMatcher, MatchResult, get_matcher, match_room, match_rooms
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/zones", tags=["zones"])


# === Request/Response Models ===

class ZoneResponse(BaseModel):
    """Response-Modell für eine Habituszone."""
    zone_type: str = Field(..., description="Zone-Typ (Enum-Value)")
    name_de: str = Field(..., description="Deutscher Name")
    name_en: str = Field(..., description="Englischer Name")
    description: str = Field(..., description="Beschreibung der Zone")
    keywords_de: List[str] = Field(..., description="Deutsche Keywords")
    keywords_en: List[str] = Field(..., description="Englische Keywords")
    priority: int = Field(..., description="Priorität bei Matching-Konflikten")


class MatchedRoomResponse(BaseModel):
    """Response-Modell für gematchte Räume."""
    room_name: str = Field(..., description="Name des Raums")
    zone_type: str = Field(..., description="Zugewiesener Zone-Typ")
    zone_name_de: str = Field(..., description="Deutscher Zonenname")
    zone_name_en: str = Field(..., description="Englischer Zonenname")
    confidence: float = Field(..., ge=0, le=100, description="Confidence-Score (0-100)")
    matched_keyword: Optional[str] = Field(None, description="Keyword das zum Match führte")
    needs_review: bool = Field(..., description="True wenn Review benötigt")


class AssignRequest(BaseModel):
    """Request für manuelle Zuordnung."""
    room_name: str = Field(..., description="Name des Raums")
    zone_type: str = Field(..., description="Zone-Typ (z.B. 'living', 'bath')")
    override_existing: bool = Field(default=False, description="Bestehende Zuordnung überschreiben")


class TagRequest(BaseModel):
    """Request für Tag-Korrektur."""
    room_name: str = Field(..., description="Name des Raums")
    tag: str = Field(..., description="Tag im Format 'zone:<type>' (z.B. 'zone:living')")


class ReviewQueueResponse(BaseModel):
    """Response für Review-Queue."""
    total_count: int = Field(..., description="Anzahl Räume in Review")
    rooms: List[MatchedRoomResponse] = Field(..., description="Räume die Review benötigen")


class SecondaryStateRequest(BaseModel):
    """Request für secondary zone state (dark/sleep/extended)."""
    zone_type: str = Field(..., description="Zone-Typ (z.B. 'living', 'bedroom')")
    state: str = Field(..., description="Secondary state: 'dark', 'sleep', 'extended'")
    timestamp_ms: int = Field(..., description="Unix timestamp in milliseconds")


class SecondaryStateResponse(BaseModel):
    """Response für secondary state operation."""
    zone_type: str = Field(..., description="Zone-Typ")
    state: str = Field(..., description="Current secondary state")
    state_since_ms: Optional[int] = Field(None, description="Timestamp when state was set")
    supports_dark: bool = Field(..., description="Zone supports dark state")
    supports_sleep: bool = Field(..., description="Zone supports sleep state")
    supports_extended: bool = Field(..., description="Zone supports extended state")


_VALID_ZONE_TYPES = [zt.value for zt in ZoneType]
_VALID_SECONDARY_STATES = ["dark", "sleep", "extended"]


def _zones_error_response(
    status_code: int,
    *,
    code: str,
    message: str,
    field: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_response_payload(code=code, message=message, field=field, context=context),
    )


# === Endpoints ===

@router.get("/habitus", response_model=List[ZoneResponse])
async def get_habitus_zones():
    """
    Alle Habituszonen zurückgeben.
    
    Gibt alle 10 vordefinierten Habituszonen mit Keywords und Metadaten zurück.
    """
    zones = get_all_zones()
    return [
        ZoneResponse(
            zone_type=zone.zone_type.value,
            name_de=zone.name_de,
            name_en=zone.name_en,
            description=zone.description,
            keywords_de=zone.keywords_de,
            keywords_en=zone.keywords_en,
            priority=zone.priority
        )
        for zone in zones
    ]


@router.get("/matched", response_model=List[MatchedRoomResponse])
async def get_matched_rooms(
    rooms: Optional[str] = Query(None, description="Kommagetrennte Liste von Raum-Namen")
):
    """
    Gematchte Räume mit Confidence-Scores zurückgeben.
    
    Wenn keine Räume angegeben, werden keine Matches berechnet.
    Für Massen-Matching: rooms="Wohnzimmer,Küche,Bad"
    """
    if not rooms:
        return []
    
    room_list = [r.strip() for r in rooms.split(",") if r.strip()]
    matcher = get_matcher()
    results = matcher.match_multiple_rooms(room_list)
    
    return [
        MatchedRoomResponse(
            room_name=r.room_name,
            zone_type=r.zone.zone_type.value,
            zone_name_de=r.zone.name_de,
            zone_name_en=r.zone.name_en,
            confidence=r.confidence,
            matched_keyword=r.matched_keyword,
            needs_review=r.needs_review
        )
        for r in results
    ]


@router.post(
    "/assign",
    response_model=MatchedRoomResponse,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Invalid zone assignment request",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_zone_type": {
                            "summary": "Unknown zone type",
                            "value": {
                                "code": "INVALID_ZONE_TYPE",
                                "message": "Ungültiger Zone-Typ: spa.",
                                "field": "zone_type",
                                "context": {
                                    "allowed_values": ["living", "bath", "kitchen"]
                                },
                            },
                        }
                    }
                }
            },
        },
        404: {
            "model": ErrorResponse,
            "description": "Zone not found",
            "content": {
                "application/json": {
                    "examples": {
                        "zone_not_found": {
                            "summary": "Zone missing",
                            "value": {
                                "code": "ZONE_NOT_FOUND",
                                "message": "Zone nicht gefunden: living",
                                "field": "zone_type",
                            },
                        }
                    }
                }
            },
        },
    },
)
async def assign_room_to_zone(request: AssignRequest):
    """
    Raum manuell einer Zone zuordnen.
    
    Überschreibt das automatische Matching. Nützlich für Korrekturen
    oder wenn das ML-Matching unsicher war.
    """
    # Validiere Zone-Type
    try:
        zone_type = ZoneType(request.zone_type)
    except ValueError:
        return _zones_error_response(
            400,
            code="INVALID_ZONE_TYPE",
            message=f"Ungültiger Zone-Typ: {request.zone_type}.",
            field="zone_type",
            context={"allowed_values": _VALID_ZONE_TYPES},
        )

    zone = HABITUS_ZONES.get(zone_type)
    if not zone:
        return _zones_error_response(
            404,
            code="ZONE_NOT_FOUND",
            message=f"Zone nicht gefunden: {zone_type.value}",
            field="zone_type",
        )
    
    # Erstelle MatchResult mit hoher Confidence (manuelle Zuordnung)
    result = MatchResult(
        room_name=request.room_name,
        zone=zone,
        confidence=100.0,  # Manuelle Zuordnung = 100% sicher
        matched_keyword="manual_assignment",
        needs_review=False
    )
    
    logger.info(
        f"Manuelle Zuordnung: {request.room_name} → {zone.name_de} "
        f"(vorher: {request.override_existing})"
    )
    
    return MatchedRoomResponse(
        room_name=result.room_name,
        zone_type=result.zone.zone_type.value,
        zone_name_de=result.zone.name_de,
        zone_name_en=result.zone.name_en,
        confidence=result.confidence,
        matched_keyword=result.matched_keyword,
        needs_review=result.needs_review
    )


@router.post(
    "/tag",
    response_model=MatchedRoomResponse,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Invalid zone tag request",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_zone_tag_format": {
                            "summary": "Tag prefix missing",
                            "value": {
                                "code": "INVALID_ZONE_TAG_FORMAT",
                                "message": "Tag muss im Format 'zone:<type>' sein (z.B. 'zone:living')",
                                "field": "tag",
                                "context": {"expected_prefix": "zone:"},
                            },
                        },
                        "invalid_zone_type": {
                            "summary": "Unknown zone type in tag",
                            "value": {
                                "code": "INVALID_ZONE_TYPE",
                                "message": "Ungültiger Zone-Typ in Tag: spa.",
                                "field": "tag",
                                "context": {
                                    "allowed_values": _VALID_ZONE_TYPES,
                                },
                            },
                        },
                    }
                }
            },
        },
        404: {
            "model": ErrorResponse,
            "description": "Zone not found",
            "content": {
                "application/json": {
                    "examples": {
                        "zone_not_found": {
                            "summary": "Zone missing in registry",
                            "value": {
                                "code": "ZONE_NOT_FOUND",
                                "message": "Zone nicht gefunden: living",
                                "field": "zone_type",
                            },
                        }
                    }
                }
            },
        },
    },
)
async def add_zone_tag(request: TagRequest):
    """
    Tag für Raum-Korrektur hinzufügen.
    
    Tags im Format 'zone:<type>' können verwendet werden um das
    automatische Matching zu verbessern. Beispiel: 'zone:living'
    """
    tag = request.tag.strip()
    
    # Validiere Tag-Format
    if not tag.startswith("zone:"):
        return _zones_error_response(
            400,
            code="INVALID_ZONE_TAG_FORMAT",
            message="Tag muss im Format 'zone:<type>' sein (z.B. 'zone:living')",
            field="tag",
            context={"expected_prefix": "zone:"},
        )
    
    zone_type_str = tag[5:]  # "zone:" entfernen
    
    try:
        zone_type = ZoneType(zone_type_str)
    except ValueError:
        return _zones_error_response(
            400,
            code="INVALID_ZONE_TYPE",
            message=f"Ungültiger Zone-Typ in Tag: {zone_type_str}.",
            field="tag",
            context={"allowed_values": _VALID_ZONE_TYPES},
        )
    
    zone = HABITUS_ZONES.get(zone_type)
    if not zone:
        return _zones_error_response(
            404,
            code="ZONE_NOT_FOUND",
            message=f"Zone nicht gefunden: {zone_type.value}",
            field="zone_type",
        )
    
    # Match mit Tag-Korrektur (simuliert)
    result = MatchResult(
        room_name=request.room_name,
        zone=zone,
        confidence=95.0,  # Tag-basiert = hohe Confidence
        matched_keyword=f"tag:{tag}",
        needs_review=False
    )
    
    logger.info(f"Tag hinzugefügt: {request.room_name} → {tag}")
    
    return MatchedRoomResponse(
        room_name=result.room_name,
        zone_type=result.zone.zone_type.value,
        zone_name_de=result.zone.name_de,
        zone_name_en=result.zone.name_en,
        confidence=result.confidence,
        matched_keyword=result.matched_keyword,
        needs_review=result.needs_review
    )


@router.post("/state", response_model=SecondaryStateResponse)
async def set_zone_secondary_state(request: SecondaryStateRequest):
    """
    Secondary zone state setzen (dark/sleep/extended).
    
    Secondary states sind orthogonal zum Zone-Typ und ermöglichen:
    - dark: Low light / night mode (Lichtsensor/Sonne)
    - sleep: User override sleep mode
    - extended: Exceeded time limit
    """
    zone_type_str = request.state.lower()
    
    # Validiere state
    if zone_type_str not in _VALID_SECONDARY_STATES:
        return _zones_error_response(
            400,
            code="INVALID_SECONDARY_STATE",
            message=f"Ungültiger secondary state: {request.state}.",
            field="state",
            context={"allowed_values": _VALID_SECONDARY_STATES},
        )
    
    # Validiere Zone-Type
    try:
        zone_type = ZoneType(request.zone_type)
    except ValueError:
        return _zones_error_response(
            400,
            code="INVALID_ZONE_TYPE",
            message=f"Ungültiger Zone-Typ: {request.zone_type}.",
            field="zone_type",
            context={"allowed_values": _VALID_ZONE_TYPES},
        )
    
    zone = HABITUS_ZONES.get(zone_type)
    if not zone:
        return _zones_error_response(
            404,
            code="ZONE_NOT_FOUND",
            message=f"Zone nicht gefunden: {zone_type.value}",
            field="zone_type",
        )
    
    # Set state
    zone.set_secondary_state(ZoneState(request.state), request.timestamp_ms)
    
    logger.info(f"Secondary state gesetzt: {zone_type.value} → {request.state}")
    
    return SecondaryStateResponse(
        zone_type=zone_type.value,
        state=zone.current_state.value,
        state_since_ms=zone.state_since_ms,
        supports_dark=zone.supports_dark,
        supports_sleep=zone.supports_sleep,
        supports_extended=zone.supports_extended,
    )


@router.get("/state/{zone_type}", response_model=SecondaryStateResponse)
async def get_zone_secondary_state(zone_type: str):
    """
    Current secondary state einer Zone abrufen.
    """
    try:
        zone_type_enum = ZoneType(zone_type)
    except ValueError:
        return _zones_error_response(
            400,
            code="INVALID_ZONE_TYPE",
            message=f"Ungültiger Zone-Typ: {zone_type}.",
            field="zone_type",
            context={"allowed_values": _VALID_ZONE_TYPES},
        )
    
    zone = HABITUS_ZONES.get(zone_type_enum)
    if not zone:
        return _zones_error_response(
            404,
            code="ZONE_NOT_FOUND",
            message=f"Zone nicht gefunden: {zone_type}",
            field="zone_type",
        )
    
    return SecondaryStateResponse(
        zone_type=zone_type_enum.value,
        state=zone.current_state.value,
        state_since_ms=zone.state_since_ms,
        supports_dark=zone.supports_dark,
        supports_sleep=zone.supports_sleep,
        supports_extended=zone.supports_extended,
    )


@router.get("/review", response_model=ReviewQueueResponse)
async def get_review_queue(
    rooms: Optional[str] = Query(None, description="Kommagetrennte Liste von Raum-Namen"),
    threshold: float = Query(default=70.0, ge=0, le=100, description="Confidence-Threshold")
):
    """
    Unsichere Zuordnungen für Review zurückgeben.
    
    Gibt alle Räume zurück deren Confidence-Score unter dem Threshold liegt.
    Standard: 70% Confidence.
    """
    if not rooms:
        return ReviewQueueResponse(total_count=0, rooms=[])
    
    room_list = [r.strip() for r in rooms.split(",") if r.strip()]
    matcher = get_matcher()
    results = matcher.match_multiple_rooms(room_list)
    
    # Filtere unsichere Matches
    review_items = [r for r in results if r.confidence < threshold]
    
    return ReviewQueueResponse(
        total_count=len(review_items),
        rooms=[
            MatchedRoomResponse(
                room_name=r.room_name,
                zone_type=r.zone.zone_type.value,
                zone_name_de=r.zone.name_de,
                zone_name_en=r.zone.name_en,
                confidence=r.confidence,
                matched_keyword=r.matched_keyword,
                needs_review=r.needs_review
            )
            for r in review_items
        ]
    )


@router.get("/match/{room_name}", response_model=MatchedRoomResponse)
async def match_single_room(room_name: str):
    """
    Einzelnen Raum matchen.
    
    Matcht einen einzelnen Raum-Namen und gibt das Ergebnis mit Confidence zurück.
    """
    result = match_room(room_name)
    
    return MatchedRoomResponse(
        room_name=result.room_name,
        zone_type=result.zone.zone_type.value,
        zone_name_de=result.zone.name_de,
        zone_name_en=result.zone.name_en,
        confidence=result.confidence,
        matched_keyword=result.matched_keyword,
        needs_review=result.needs_review
    )


@router.post("/match/batch", response_model=List[MatchedRoomResponse])
async def match_batch_rooms(
    rooms: List[str] = Body(..., description="Liste von Raum-Namen")
):
    """
    Mehrere Räume auf einmal matchen.
    
    Batch-Endpoint für effizientes Matching mehrerer Räume.
    """
    if not rooms:
        return []
    
    results = match_rooms(rooms)
    
    return [
        MatchedRoomResponse(
            room_name=r.room_name,
            zone_type=r.zone.zone_type.value,
            zone_name_de=r.zone.name_de,
            zone_name_en=r.zone.name_en,
            confidence=r.confidence,
            matched_keyword=r.matched_keyword,
            needs_review=r.needs_review
        )
        for r in results
    ]
