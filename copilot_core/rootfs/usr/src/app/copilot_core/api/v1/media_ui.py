"""Media UI API — Sonos, Musikwolke, Favorites, Camera.

Endpoints:
- GET /api/v1/media — Media Overview
- GET /api/v1/media/sonos — Sonos Players + Status
- GET /api/v1/media/sonos/favorites — Sonos Favorites
- POST /api/v1/media/sonos/play — Play Favorite
- GET /api/v1/media/musikwolke — Musikwolke (zonenabhängig)
- PUT /api/v1/media/musikwolke/zone/{zone_id} — Musikwolke pro Zone konfigurieren
- GET /api/v1/media/cameras — Camera Status
- GET /api/v1/media/cameras/{camera_id}/snapshot — Camera Snapshot
"""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List
from datetime import datetime, timezone

_LOGGER = logging.getLogger(__name__)

media_ui_bp = Blueprint("media_ui", __name__, url_prefix="/api/v1/media")


# =============================================================================
# API Endpoints
# =============================================================================

@media_ui_bp.route("", methods=["GET"])
def get_media_overview():
    """Media Overview — Sonos, Musikwolke, Cameras."""
    return jsonify({
        "sonos": {
            "players_count": 4,
            "zones_with_audio": 3,
            "now_playing": 2,
        },
        "musikwolke": {
            "enabled": True,
            "zones_configured": 3,
            "total_favorites": 15,
        },
        "cameras": {
            "count": 3,
            "recording": 1,
            "idle": 2,
        },
    })


@media_ui_bp.route("/sonos", methods=["GET"])
def get_sonos_players():
    """Sonos Players — Status + Controls."""
    # TODO: Echte Sonos-Player aus SonosHTTPClient laden
    players = [
        {
            "id": "sonos_wohnzimmer",
            "name": "Wohnzimmer",
            "zone": "living",
            "status": "playing",
            "volume": 40,
            "current_track": {
                "title": "Jazz Radio",
                "artist": "Various",
                "album": "Favorites",
            },
            "favorites": ["Jazz", "Chillout", "Classical"],
        },
        {
            "id": "sonos_kuche",
            "name": "Küche",
            "zone": "kitchen",
            "status": "idle",
            "volume": 30,
            "current_track": None,
            "favorites": ["Pop", "Rock"],
        },
        {
            "id": "sonos_bad",
            "name": "Bad",
            "zone": "bath",
            "status": "idle",
            "volume": 25,
            "current_track": None,
            "favorites": ["Relax", "Nature"],
        },
        {
            "id": "sonos_terrasse",
            "name": "Terrasse",
            "zone": "terrace",
            "status": "idle",
            "volume": 50,
            "current_track": None,
            "favorites": ["Summer", "Party"],
        },
    ]
    
    return jsonify({
        "players": players,
        "http_api": {
            "enabled": True,
            "url": "http://localhost:5005",
            "status": "healthy",
        },
    })


@media_ui_bp.route("/sonos/favorites", methods=["GET"])
def get_sonos_favorites():
    """Sonos Favorites — Alle Favorites."""
    # TODO: Echte Favorites aus Sonos laden
    favorites = [
        {"id": "fav_001", "name": "Jazz", "url": "x-rincon-mp3radio://stream.jazz.com", "zone": "living"},
        {"id": "fav_002", "name": "Chillout", "url": "x-rincon-mp3radio://stream.chill.com", "zone": "living"},
        {"id": "fav_003", "name": "Classical", "url": "x-rincon-mp3radio://stream.classical.com", "zone": "living"},
        {"id": "fav_004", "name": "Pop", "url": "x-rincon-mp3radio://stream.pop.com", "zone": "kitchen"},
        {"id": "fav_005", "name": "Rock", "url": "x-rincon-mp3radio://stream.rock.com", "zone": "kitchen"},
        {"id": "fav_006", "name": "Relax", "url": "x-rincon-mp3radio://stream.relax.com", "zone": "bath"},
        {"id": "fav_007", "name": "Nature", "url": "x-rincon-mp3radio://stream.nature.com", "zone": "bath"},
        {"id": "fav_008", "name": "Summer", "url": "x-rincon-mp3radio://stream.summer.com", "zone": "terrace"},
        {"id": "fav_009", "name": "Party", "url": "x-rincon-mp3radio://stream.party.com", "zone": "terrace"},
    ]
    
    return jsonify({
        "total": len(favorites),
        "favorites": favorites,
    })


@media_ui_bp.route("/sonos/play", methods=["POST"])
def sonos_play():
    """Sonos Favorite abspielen."""
    data = request.get_json()
    player_id = data.get("player_id")
    favorite_id = data.get("favorite_id")
    volume = data.get("volume", 40)
    
    if not player_id:
        return jsonify({"error": "player_id required"}), 400
    
    # TODO: SonosHTTPClient.play_favorite(player_id, favorite_id, volume)
    _LOGGER.info(f"Playing {favorite_id} on {player_id} at volume {volume}")
    
    return jsonify({
        "success": True,
        "player_id": player_id,
        "favorite_id": favorite_id,
        "volume": volume,
    })


@media_ui_bp.route("/musikwolke", methods=["GET"])
def get_musikwolke():
    """Musikwolke — Zonenabhängige Musik-Konfiguration."""
    # TODO: Echte Musikwolke-Konfiguration laden
    musikwolke = {
        "enabled": True,
        "zones": [
            {
                "zone_id": "living",
                "zone_name": "Wohnbereich",
                "player_id": "sonos_wohnzimmer",
                "favorites": ["Jazz", "Chillout"],
                "volume": 40,
                "auto_play_on_presence": True,
                "shuffle": True,
            },
            {
                "zone_id": "kitchen",
                "zone_name": "Kochbereich",
                "player_id": "sonos_kuche",
                "favorites": ["Pop", "Rock"],
                "volume": 30,
                "auto_play_on_presence": False,
                "shuffle": True,
            },
            {
                "zone_id": "terrace",
                "zone_name": "Terrassenbereich",
                "player_id": "sonos_terrasse",
                "favorites": ["Summer", "Party"],
                "volume": 50,
                "auto_play_on_presence": False,
                "shuffle": False,
            },
        ],
    }
    
    return jsonify(musikwolke)


@media_ui_bp.route("/musikwolke/zone/<zone_id>", methods=["PUT"])
def update_musikwolke_zone(zone_id: str):
    """Musikwolke pro Zone konfigurieren."""
    data = request.get_json()
    
    # Validierung
    valid_fields = {"player_id", "favorites", "volume", "auto_play_on_presence", "shuffle"}
    update_data = {k: v for k, v in data.items() if k in valid_fields}
    
    # TODO: In ZoneConfig speichern
    _LOGGER.info(f"Updating musikwolke for zone {zone_id}: {update_data}")
    
    return jsonify({
        "success": True,
        "zone_id": zone_id,
        "updated": update_data,
    })


@media_ui_bp.route("/cameras", methods=["GET"])
def get_cameras():
    """Camera Status — Alle Kameras."""
    # TODO: Echte Camera-Status laden
    cameras = [
        {
            "id": "cam_haustur",
            "name": "Haustür",
            "zone": "hallway",
            "status": "recording",
            "snapshot_url": "/api/v1/media/cameras/cam_haustur/snapshot",
            "last_motion": datetime.now(timezone.utc).isoformat(),
        },
        {
            "id": "cam_garten",
            "name": "Garten",
            "zone": "outside",
            "status": "idle",
            "snapshot_url": "/api/v1/media/cameras/cam_garten/snapshot",
            "last_motion": None,
        },
        {
            "id": "cam_terrasse",
            "name": "Terrasse",
            "zone": "terrace",
            "status": "idle",
            "snapshot_url": "/api/v1/media/cameras/cam_terrasse/snapshot",
            "last_motion": datetime.now(timezone.utc).isoformat(),
        },
    ]
    
    return jsonify({
        "total": len(cameras),
        "recording": sum(1 for c in cameras if c["status"] == "recording"),
        "cameras": cameras,
    })


@media_ui_bp.route("/cameras/<camera_id>/snapshot", methods=["GET"])
def get_camera_snapshot(camera_id: str):
    """Camera Snapshot — als Bild."""
    # TODO: Echten Snapshot von Camera laden
    # Return: image/jpeg
    return jsonify({
        "camera_id": camera_id,
        "snapshot_url": f"/api/v1/media/cameras/{camera_id}/snapshot.jpg",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
