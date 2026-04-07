"""Wi-Fi/BLE Fingerprinting API — P3-008.

REST API endpoints for device presence detection using Wi-Fi and BLE fingerprints.

Endpoints:
- POST /api/v1/presence/fingerprint/detect — Submit fingerprint data for presence detection
- GET /api/v1/presence/fingerprint/devices — List known devices
- POST /api/v1/presence/fingerprint/devices/register — Register a new device
- GET /api/v1/presence/fingerprint/history — Recent detection history
- POST /api/v1/presence/fingerprint/zones/map — Map AP/beacon to zone

Blueprint prefix: /api/v1/presence/fingerprint
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token
from copilot_core.presence.wifi_ble_fingerprint import (
    BLEFingerprint,
    DeviceFingerprintProfile,
    FingerprintHistoryEntry,
    PresenceDetection,
    WiFiFingerprint,
    get_fingerprint_engine,
    reset_fingerprint_engine,
)

logger = logging.getLogger(__name__)

fingerprint_bp = Blueprint(
    "fingerprint",
    __name__,
    url_prefix="/api/v1/presence/fingerprint",
)

# =============================================================================
# POST /api/v1/presence/fingerprint/detect
# =============================================================================


@fingerprint_bp.route("/detect", methods=["POST"])
@require_token
def detect_presence():
    """Submit fingerprint data and get presence detection result.

    Accepts Wi-Fi and/or BLE fingerprint data and returns presence detection
    with confidence scores.

    Request body::

        {
            "device_id": "optional-device-id",  # For targeted detection
            "wifi": [
                {
                    "bssid": "AA:BB:CC:DD:EE:FF",
                    "ssid": "MyNetwork",
                    "rssi": -65,
                    "frequency": 2412,
                    "channel": 1,
                    "noise": -90,
                    "timestamp": 1700000000.0
                }
            ],
            "ble": [
                {
                    "mac_address": "11:22:33:44:55:66",
                    "rssi": -72,
                    "service_uuid": "0000180A-0000-1000-8000-00805F9B34FB",
                    "manufacturer_id": 76,
                    "tx_power": -59,
                    "timestamp": 1700000000.0
                }
            ],
            "use_fusion": true  # Use multi-sensor fusion (default: true)
        }

    Response::

        {
            "ok": true,
            "detection": {
                "device_id": "a1b2c3d4e5f6g7h8",
                "device_type": "phone",
                "is_present": true,
                "confidence": 0.87,
                "location_zone": "same_room",
                "detection_method": "fusion",
                "wifi_rssi": -62.5,
                "ble_rssi": -70.0,
                "timestamp": "2024-01-15T10:30:00Z"
            },
            "processed_wifi_count": 3,
            "processed_ble_count": 2
        }
    """
    data = request.get_json(silent=True) or {}

    engine = get_fingerprint_engine()

    # Process Wi-Fi fingerprints
    wifi_data = data.get("wifi", [])
    for wifi in wifi_data:
        try:
            engine.process_wifi_fingerprint(
                bssid=wifi.get("bssid", ""),
                ssid=wifi.get("ssid", ""),
                rssi=wifi.get("rssi", -100),
                frequency=wifi.get("frequency", 2412),
                channel=wifi.get("channel", 1),
                timestamp=wifi.get("timestamp"),
                noise=wifi.get("noise"),
            )
        except Exception as e:
            logger.warning("Failed to process Wi-Fi fingerprint: %s", e)

    # Process BLE fingerprints
    ble_data = data.get("ble", [])
    for ble in ble_data:
        try:
            engine.process_ble_fingerprint(
                mac_address=ble.get("mac_address", ""),
                rssi=ble.get("rssi", -100),
                service_uuid=ble.get("service_uuid"),
                manufacturer_id=ble.get("manufacturer_id"),
                tx_power=ble.get("tx_power"),
                timestamp=ble.get("timestamp"),
            )
        except Exception as e:
            logger.warning("Failed to process BLE fingerprint: %s", e)

    # Detect presence
    device_id = data.get("device_id")
    use_fusion = data.get("use_fusion", True)

    detection = engine.detect_presence(device_id=device_id, use_fusion=use_fusion)

    if detection is None:
        return jsonify({
            "ok": True,
            "detection": None,
            "message": "No device detected in fingerprint window",
            "processed_wifi_count": len(wifi_data),
            "processed_ble_count": len(ble_data),
        })

    return jsonify({
        "ok": True,
        "detection": {
            "device_id": detection.device_id,
            "device_type": detection.device_type,
            "is_present": detection.is_present,
            "confidence": round(detection.confidence, 3),
            "location_zone": detection.location_zone,
            "detection_method": detection.detection_method,
            "wifi_rssi": round(detection.wifi_rssi, 1) if detection.wifi_rssi else None,
            "ble_rssi": round(detection.ble_rssi, 1) if detection.ble_rssi else None,
            "timestamp": detection.timestamp,
        },
        "processed_wifi_count": len(wifi_data),
        "processed_ble_count": len(ble_data),
    })


# =============================================================================
# GET /api/v1/presence/fingerprint/devices
# =============================================================================


@fingerprint_bp.route("/devices", methods=["GET"])
@require_token
def list_devices():
    """List all registered device fingerprint profiles.

    Query Parameters:
        device_type (optional): Filter by device type
        limit (optional): Limit results (default: 100)

    Response::

        {
            "ok": true,
            "devices": [
                {
                    "device_id": "a1b2c3d4e5f6g7h8",
                    "device_type": "phone",
                    "typical_rssi_mean": -65.2,
                    "typical_rssi_std": 8.5,
                    "last_seen": 1700000000.0,
                    "confidence_score": 0.87,
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-15T10:30:00Z",
                    "wifi_signature_count": 15,
                    "ble_signature_count": 8
                }
            ],
            "total": 5
        }
    """
    device_type_filter = request.args.get("device_type")
    limit = int(request.args.get("limit", 100))

    engine = get_fingerprint_engine()
    profiles = engine.get_device_profiles()

    # Filter by device type if specified
    if device_type_filter:
        profiles = [p for p in profiles if p.device_type == device_type_filter]

    # Limit results
    profiles = profiles[:limit]

    devices = []
    for profile in profiles:
        devices.append({
            "device_id": profile.device_id,
            "device_type": profile.device_type,
            "typical_rssi_mean": round(profile.typical_rssi_mean, 1),
            "typical_rssi_std": round(profile.typical_rssi_std, 1),
            "last_seen": profile.last_seen,
            "confidence_score": round(profile.confidence_score, 3),
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
            "wifi_signature_count": sum(len(v) for v in profile.wifi_signatures.values()),
            "ble_signature_count": sum(len(v) for v in profile.ble_signatures.values()),
        })

    return jsonify({
        "ok": True,
        "devices": devices,
        "total": len(devices),
    })


# =============================================================================
# POST /api/v1/presence/fingerprint/devices/register
# =============================================================================


@fingerprint_bp.route("/devices/register", methods=["POST"])
@require_token
def register_device():
    """Register a new device for fingerprint tracking.

    Request body::

        {
            "device_id": "custom-device-id",  # Optional, auto-generated if omitted
            "device_type": "phone",  # phone, tablet, watch, unknown
            "mac_address": "AA:BB:CC:DD:EE:FF",  # For anonymization
            "initial_rssi_samples": [-65, -68, -62, -70]  # Optional calibration
        }

    Response::

        {
            "ok": true,
            "device": {
                "device_id": "a1b2c3d4e5f6g7h8",
                "device_type": "phone",
                "typical_rssi_mean": -66.25,
                "typical_rssi_std": 3.2,
                ...
            }
        }
    """
    data = request.get_json(silent=True) or {}

    engine = get_fingerprint_engine()

    device_id = data.get("device_id")
    device_type = data.get("device_type", "unknown")
    mac_address = data.get("mac_address")
    initial_rssi = data.get("initial_rssi_samples", [])

    # Generate device ID from MAC if not provided
    if not device_id and mac_address:
        from copilot_core.presence.wifi_ble_fingerprint import anonymize_mac
        device_id = anonymize_mac(mac_address)
    elif not device_id:
        import uuid
        device_id = str(uuid.uuid4())[:16]

    # Register the device
    profile = engine.register_device(
        device_id=device_id,
        device_type=device_type,
        initial_wifi_rssi=initial_rssi if initial_rssi else None,
    )

    return jsonify({
        "ok": True,
        "device": {
            "device_id": profile.device_id,
            "device_type": profile.device_type,
            "typical_rssi_mean": round(profile.typical_rssi_mean, 1),
            "typical_rssi_std": round(profile.typical_rssi_std, 1),
            "last_seen": profile.last_seen,
            "confidence_score": profile.confidence_score,
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
        },
    })


# =============================================================================
# GET /api/v1/presence/fingerprint/history
# =============================================================================


@fingerprint_bp.route("/history", methods=["GET"])
@require_token
def get_history():
    """Get recent fingerprint detection history.

    Query Parameters:
        device_id (optional): Filter by device
        limit (optional): Limit results (default: 50, max: 500)

    Response::

        {
            "ok": true,
            "history": [
                {
                    "device_id": "a1b2c3d4e5f6g7h8",
                    "detection": {
                        "is_present": true,
                        "confidence": 0.87,
                        "detection_method": "fusion",
                        ...
                    },
                    "raw_wifi_count": 3,
                    "raw_ble_count": 2,
                    "processed_at": "2024-01-15T10:30:00Z"
                }
            ],
            "total": 50
        }
    """
    device_id_filter = request.args.get("device_id")
    limit = min(int(request.args.get("limit", 50)), 500)

    engine = get_fingerprint_engine()
    history = engine.get_detection_history(limit=limit)

    # Filter by device_id if specified
    if device_id_filter:
        history = [h for h in history if h.device_id == device_id_filter]

    result = []
    for entry in history:
        result.append({
            "device_id": entry.device_id,
            "detection": {
                "device_id": entry.detection.device_id,
                "device_type": entry.detection.device_type,
                "is_present": entry.detection.is_present,
                "confidence": round(entry.detection.confidence, 3),
                "location_zone": entry.detection.location_zone,
                "detection_method": entry.detection.detection_method,
                "wifi_rssi": round(entry.detection.wifi_rssi, 1) if entry.detection.wifi_rssi else None,
                "ble_rssi": round(entry.detection.ble_rssi, 1) if entry.detection.ble_rssi else None,
                "timestamp": entry.detection.timestamp,
            },
            "raw_wifi_count": entry.raw_wifi_count,
            "raw_ble_count": entry.raw_ble_count,
            "processed_at": entry.processed_at,
        })

    return jsonify({
        "ok": True,
        "history": result,
        "total": len(result),
    })


# =============================================================================
# POST /api/v1/presence/fingerprint/zones/map
# =============================================================================


@fingerprint_bp.route("/zones/map", methods=["POST"])
@require_token
def map_zone():
    """Map an AP BSSID or BLE device to a zone.

    Request body::

        {
            "identifier_type": "wifi_bssid",  # or "ble_device"
            "identifier": "AA:BB:CC:DD:EE:FF",  # Will be anonymized
            "zone_id": "living_room"
        }

    Response::

        {
            "ok": true,
            "mapping": {
                "identifier_hash": "a1b2c3d4e5f6g7h8",
                "zone_id": "living_room"
            }
        }
    """
    data = request.get_json(silent=True) or {}

    identifier_type = data.get("identifier_type")
    identifier = data.get("identifier")
    zone_id = data.get("zone_id")

    if not identifier_type or not identifier or not zone_id:
        return jsonify({
            "ok": False,
            "error": "Missing required fields: identifier_type, identifier, zone_id",
        }), 400

    from copilot_core.presence.wifi_ble_fingerprint import anonymize_mac

    identifier_hash = anonymize_mac(identifier)

    engine = get_fingerprint_engine()
    engine.set_zone_mapping(identifier_hash, zone_id)

    return jsonify({
        "ok": True,
        "mapping": {
            "identifier_type": identifier_type,
            "identifier_hash": identifier_hash,
            "zone_id": zone_id,
        },
    })


# =============================================================================
# DELETE /api/v1/presence/fingerprint/reset (admin only)
# =============================================================================


@fingerprint_bp.route("/reset", methods=["DELETE"])
@require_token
def reset_engine():
    """Reset the fingerprint engine (clear all data).

    Admin-only endpoint for testing and maintenance.

    Response::

        {
            "ok": true,
            "message": "Fingerprint engine reset"
        }
    """
    # In production, add additional auth check here
    reset_fingerprint_engine()

    logger.warning("Fingerprint engine reset by admin")

    return jsonify({
        "ok": True,
        "message": "Fingerprint engine reset successfully",
    })
