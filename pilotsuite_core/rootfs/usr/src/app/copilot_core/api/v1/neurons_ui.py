"""Neuron UI API — Visualisierung für 3-Layer Neuron-System.

Endpoints:
- GET /api/v1/neurons — Alle Neuronen mit States
- GET /api/v1/neurons/context — CONTEXT Layer (12 Neurons)
- GET /api/v1/neurons/state — STATE Layer (8 Neurons)
- GET /api/v1/neurons/mood — MOOD Layer (5 Neurons)
- GET /api/v1/neurons/pipeline — Pipeline-Status
- POST /api/v1/neurons/evaluate — Pipeline manuell auslösen
"""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List
from datetime import datetime, timezone

_LOGGER = logging.getLogger(__name__)

neurons_ui_bp = Blueprint("neurons_ui", __name__, url_prefix="/api/v1/neurons")


# =============================================================================
# Neuron Definitions (3 Layers)
# =============================================================================

CONTEXT_NEURONS = [
    {"id": "presence", "name": "Präsenz", "description": "Personen im Raum", "icon": "mdi:motion-sensor", "layer": "context"},
    {"id": "timeofday", "name": "Tageszeit", "description": "Morgen, Mittag, Abend, Nacht", "icon": "mdi:clock-outline", "layer": "context"},
    {"id": "lightlevel", "name": "Lichtlevel", "description": "Ambient Light Level", "icon": "mdi:brightness-5", "layer": "context"},
    {"id": "weather", "name": "Wetter", "description": "Außenwetter-Bedingungen", "icon": "mdi:weather-partly-cloudy", "layer": "context"},
    {"id": "temperature", "name": "Temperatur", "description": "Raumtemperatur", "icon": "mdi:thermometer", "layer": "context"},
    {"id": "humidity", "name": "Luftfeuchtigkeit", "description": "Relative Luftfeuchtigkeit", "icon": "mdi:water-percent", "layer": "context"},
    {"id": "noise", "name": "Geräuschlevel", "description": "Ambient Noise Level", "icon": "mdi:volume-high", "layer": "context"},
    {"id": "co2", "name": "CO2-Level", "description": "CO2-Konzentration", "icon": "mdi:molecule-co2", "layer": "context"},
    {"id": "energy", "name": "Energieverbrauch", "description": "Aktueller Power Consumption", "icon": "mdi:flash", "layer": "context"},
    {"id": "network", "name": "Netzwerk-Qualität", "description": "UniFi Network Health", "icon": "mdi:wifi", "layer": "context"},
    {"id": "calendar", "name": "Kalender", "description": "Heutige Events", "icon": "mdi:calendar", "layer": "context"},
    {"id": "media", "name": "Media-Status", "description": "Aktuelle Media-Wiedergabe", "icon": "mdi:music", "layer": "context"},
]

STATE_NEURONS = [
    {"id": "energylevel", "name": "Energielevel", "description": "Haus-Energielevel (geglaettet)", "icon": "mdi:battery-charging", "layer": "state"},
    {"id": "stressindex", "name": "Stress-Index", "description": "Stress-Level im Haushalt", "icon": "mdi:heart-pulse", "layer": "state"},
    {"id": "comfortindex", "name": "Komfort-Index", "description": "Gesamt-Komfort", "icon": "mdi:sofa", "layer": "state"},
    {"id": "sleepdebt", "name": "Schlafdefizit", "description": "Akumuliertes Schlafdefizit", "icon": "mdi:sleep-off", "layer": "state"},
    {"id": "attentionload", "name": "Aufmerksamkeits-Last", "description": "Kognitive Belastung", "icon": "mdi:brain", "layer": "state"},
    {"id": "routinestability", "name": "Routine-Stabilität", "description": "Wie stabil ist die Tagesroutine", "icon": "mdi:repeat", "layer": "state"},
    {"id": "pvforecast", "name": "PV-Prognose", "description": "Solar-Erwartung", "icon": "mdi:solar-power", "layer": "state"},
    {"id": "energycost", "name": "Energiekosten", "description": "Aktuelle Stromkosten", "icon": "mdi:currency-eur", "layer": "state"},
]

MOOD_NEURONS = [
    {"id": "relax", "name": "Entspannt", "description": "Relaxierter Zustand", "icon": "mdi:sofa-outline", "layer": "mood"},
    {"id": "focus", "name": "Fokussiert", "description": "Konzentrierter Zustand", "icon": "mdi:target", "layer": "mood"},
    {"id": "active", "name": "Aktiv", "description": "Aktiver Zustand", "icon": "mdi:run", "layer": "mood"},
    {"id": "sleep", "name": "Müde", "description": "Schlafbedürftiger Zustand", "icon": "mdi:sleep", "layer": "mood"},
    {"id": "party", "name": "Party", "description": "Geselliger Zustand", "icon": "mdi:party-popper", "layer": "mood"},
]

MOOD_DIMENSIONS = [
    {"id": "comfort", "name": "Komfort", "description": "Wie komfortabel fühlt sich das Zuhause an", "icon": "mdi:arm-flex"},
    {"id": "joy", "name": "Freude", "description": "Positive Stimmung", "icon": "mdi:emoticon-happy"},
    {"id": "frugality", "name": "Sparsamkeit", "description": "Energiebewusstsein", "icon": "mdi:leaf"},
    {"id": "energy", "name": "Energie", "description": "Aktivitätslevel", "icon": "mdi:flash"},
    {"id": "focus", "name": "Fokus", "description": "Konzentrationslevel", "icon": "mdi:target-variant"},
]


# =============================================================================
# API Endpoints
# =============================================================================

@neurons_ui_bp.route("", methods=["GET"])
def get_all_neurons():
    """Alle Neuronen mit aktuellen States."""
    # TODO: Echte States aus NeuronManager laden
    return jsonify({
        "layers": {
            "context": {
                "name": "CONTEXT",
                "description": "Objektive Umgebungsdaten",
                "neurons": [
                    {**n, "value": 0.5, "firing": False, "last_update": datetime.now(timezone.utc).isoformat()}
                    for n in CONTEXT_NEURONS
                ],
            },
            "state": {
                "name": "STATE",
                "description": "Geglättete Zustände",
                "neurons": [
                    {**n, "value": 0.6, "firing": False, "last_update": datetime.now(timezone.utc).isoformat()}
                    for n in STATE_NEURONS
                ],
            },
            "mood": {
                "name": "MOOD",
                "description": "Aggregierte Stimmung",
                "neurons": [
                    {**n, "value": 0.4, "firing": False, "last_update": datetime.now(timezone.utc).isoformat()}
                    for n in MOOD_NEURONS
                ],
            },
        },
        "total_neurons": len(CONTEXT_NEURONS) + len(STATE_NEURONS) + len(MOOD_NEURONS),
    })


@neurons_ui_bp.route("/context", methods=["GET"])
def get_context_neurons():
    """CONTEXT Layer Neuronen."""
    # TODO: Echte States laden
    return jsonify({
        "layer": "context",
        "neurons": [
            {**n, "value": 0.5, "firing": False, "last_update": datetime.now(timezone.utc).isoformat()}
            for n in CONTEXT_NEURONS
        ],
    })


@neurons_ui_bp.route("/state", methods=["GET"])
def get_state_neurons():
    """STATE Layer Neuronen."""
    # TODO: Echte States laden
    return jsonify({
        "layer": "state",
        "neurons": [
            {**n, "value": 0.6, "firing": False, "last_update": datetime.now(timezone.utc).isoformat()}
            for n in STATE_NEURONS
        ],
    })


@neurons_ui_bp.route("/mood", methods=["GET"])
def get_mood_neurons():
    """MOOD Layer Neuronen + Dimensions."""
    # TODO: Echte States laden
    return jsonify({
        "layer": "mood",
        "neurons": [
            {**n, "value": 0.4, "firing": False, "last_update": datetime.now(timezone.utc).isoformat()}
            for n in MOOD_NEURONS
        ],
        "dimensions": [
            {"id": d["id"], "name": d["name"], "value": 0.5}
            for d in MOOD_DIMENSIONS
        ],
    })


@neurons_ui_bp.route("/pipeline", methods=["GET"])
def get_pipeline_status():
    """Neural Pipeline Status."""
    # TODO: Echte Pipeline-Stats laden
    return jsonify({
        "status": "healthy",
        "events_last_hour": 150,
        "patterns_discovered": 5,
        "suggestions_generated": 3,
        "last_run": datetime.now(timezone.utc).isoformat(),
        "avg_latency_ms": 45,
        "neuron_fire_rates": {
            "context": 12.5,  # Fires pro Minute
            "state": 8.3,
            "mood": 4.2,
        },
    })


@neurons_ui_bp.route("/evaluate", methods=["POST"])
def trigger_evaluate():
    """Neural Pipeline manuell auslösen."""
    # TODO: NeuronManager.evaluate() aufrufen
    data = request.get_json() or {}
    force = data.get("force", False)
    
    _LOGGER.info(f"Neural pipeline evaluation triggered (force={force})")
    
    return jsonify({
        "success": True,
        "message": "Pipeline evaluation triggered",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@neurons_ui_bp.route("/history", methods=["GET"])
def get_mood_history():
    """Mood History für die letzten N Stunden."""
    hours = request.args.get("hours", "24", type=int)
    
    # TODO: Echte History aus MoodHistoryStore laden
    history = [
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dominant_mood": "relax",
            "confidence": 0.85,
            "dimensions": {
                "comfort": 0.8,
                "joy": 0.7,
                "frugality": 0.5,
                "energy": 0.6,
                "focus": 0.4,
            },
        }
    ]
    
    return jsonify({
        "hours": hours,
        "history": history,
    })


@neurons_ui_bp.route("/graph", methods=["GET"])
def get_neuron_graph():
    """Neuron-Graph für Visualisierung (SVG/PNG)."""
    # TODO: SVG-Graph generieren basierend auf Neuron-Aktivität
    return jsonify({
        "svg_url": "/api/v1/neurons/graph.svg",
        "nodes": len(CONTEXT_NEURONS) + len(STATE_NEURONS) + len(MOOD_NEURONS),
        "edges": 45,  # Connections zwischen Layers
        "layout": "hierarchical",  # context → state → mood
    })
