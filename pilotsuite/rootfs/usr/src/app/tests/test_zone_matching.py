"""
Tests für Zone-Matching und Habituszonen

Testet ML-basiertes Matching, Confidence-Scores und API-Endpoints.
"""

import pytest
from typing import List

from copilot_core.homeassistant.habitus_zones import (
    HABITUS_ZONES, ZoneType, HabitusZone, get_all_zones, 
    get_zone_by_type, get_zone_keywords
)
from copilot_core.homeassistant.zone_matcher import (
    ZoneMatcher, MatchResult, get_matcher, match_room, match_rooms,
    ZoneMatcher as ZM
)


class TestHabitusZones:
    """Tests für Habituszone-Definitionen."""
    
    def test_all_zones_defined(self):
        """Alle 10 Zonen müssen definiert sein."""
        assert len(HABITUS_ZONES) == 10
        assert len(get_all_zones()) == 10
    
    def test_zone_types(self):
        """Alle erwarteten Zone-Typen müssen existieren."""
        expected_types = [
            ZoneType.LIVING,
            ZoneType.BATH,
            ZoneType.KITCHEN,
            ZoneType.OFFICE,
            ZoneType.HALLWAY,
            ZoneType.BEDROOM,
            ZoneType.ROOM_MIRA,
            ZoneType.ROOM_PAUL,
            ZoneType.TERRACE,
            ZoneType.OUTSIDE,
        ]
        for zone_type in expected_types:
            assert zone_type in HABITUS_ZONES
    
    def test_zone_keywords_not_empty(self):
        """Jede Zone muss Keywords haben."""
        for zone in HABITUS_ZONES.values():
            assert len(zone.keywords_de) > 0, f"{zone.name_de} hat keine deutschen Keywords"
            assert len(zone.keywords_en) > 0, f"{zone.name_en} hat keine englischen Keywords"
    
    def test_get_zone_by_type(self):
        """Zone nach Typ abrufen."""
        zone = get_zone_by_type(ZoneType.LIVING)
        assert zone is not None
        assert zone.zone_type == ZoneType.LIVING
        assert zone.name_de == "Wohnbereich"
    
    def test_get_zone_keywords(self):
        """Keyword-Mapping muss funktionieren."""
        keywords = get_zone_keywords()
        assert "wohnzimmer" in keywords
        assert keywords["wohnzimmer"] == ZoneType.LIVING
        assert "bad" in keywords or "badezimmer" in keywords


class TestZoneMatcher:
    """Tests für ZoneMatcher-Klasse."""
    
    @pytest.fixture
    def matcher(self):
        """Matcher-Instanz für Tests."""
        return ZoneMatcher()
    
    def test_exact_match_living(self, matcher: ZoneMatcher):
        """Exakter Match für Wohnzimmer."""
        result = matcher.match_room_to_zone("Wohnzimmer")
        assert result.zone.zone_type == ZoneType.LIVING
        assert result.confidence >= 90
        assert not result.needs_review
    
    def test_exact_match_bath(self, matcher: ZoneMatcher):
        """Exakter Match für Badezimmer."""
        result = matcher.match_room_to_zone("Badezimmer")
        assert result.zone.zone_type == ZoneType.BATH
        assert result.confidence >= 90
    
    def test_exact_match_kitchen(self, matcher: ZoneMatcher):
        """Exakter Match für Küche."""
        result = matcher.match_room_to_zone("Küche")
        assert result.zone.zone_type == ZoneType.KITCHEN
        assert result.confidence >= 90
    
    def test_exact_match_office(self, matcher: ZoneMatcher):
        """Exakter Match für Büro."""
        result = matcher.match_room_to_zone("Büro")
        assert result.zone.zone_type == ZoneType.OFFICE
        assert result.confidence >= 90
    
    def test_exact_match_bedroom(self, matcher: ZoneMatcher):
        """Exakter Match für Schlafzimmer."""
        result = matcher.match_room_to_zone("Schlafzimmer")
        assert result.zone.zone_type == ZoneType.BEDROOM
        assert result.confidence >= 90
    
    def test_specific_room_mira(self, matcher: ZoneMatcher):
        """Spezifischer Match für Miras Zimmer."""
        result = matcher.match_room_to_zone("Zimmer Mira")
        assert result.zone.zone_type == ZoneType.ROOM_MIRA
        assert result.confidence >= 90  # Hohe Priorität
    
    def test_specific_room_paul(self, matcher: ZoneMatcher):
        """Spezifischer Match für Pauls Zimmer."""
        result = matcher.match_room_to_zone("Zimmer Paul")
        assert result.zone.zone_type == ZoneType.ROOM_PAUL
        assert result.confidence >= 90
    
    def test_hallway_match(self, matcher: ZoneMatcher):
        """Match für Flur/Gang."""
        result = matcher.match_room_to_zone("Flur")
        assert result.zone.zone_type == ZoneType.HALLWAY
        assert result.confidence >= 70
    
    def test_terrace_match(self, matcher: ZoneMatcher):
        """Terrasse wird kanonisch als OUTSIDE gemappt."""
        result = matcher.match_room_to_zone("Terrasse")
        assert result.zone.zone_type == ZoneType.OUTSIDE
        assert result.confidence >= 70

    def test_outdoor_aliases_match_outside(self, matcher: ZoneMatcher):
        """Outdoor-Aliase folgen dem OUTSIDE-Kanon."""
        for room in ("Terrassentuer", "Balkon", "Loggia"):
            result = matcher.match_room_to_zone(room)
            assert result.zone.zone_type == ZoneType.OUTSIDE
            assert result.confidence >= 70

    def test_outside_match(self, matcher: ZoneMatcher):
        """Match für Aussenbereich."""
        result = matcher.match_room_to_zone("Garten")
        assert result.zone.zone_type == ZoneType.OUTSIDE
        assert result.confidence >= 70

    def test_kuechenbereich_alias_is_deterministic(self, matcher: ZoneMatcher):
        """kuechenbereich wird deterministisch auf KITCHEN kanonisiert."""
        result = matcher.match_room_to_zone("Kuechenbereich")
        assert result.zone.zone_type == ZoneType.KITCHEN
        assert result.confidence >= 95
        assert result.matched_keyword == "kuechenbereich"
    
    def test_fuzzy_match_variation(self, matcher: ZoneMatcher):
        """Fuzzy-Match für Variationen."""
        result = matcher.match_room_to_zone("Wohnraum")
        assert result.zone.zone_type == ZoneType.LIVING
        assert result.confidence >= 70  # Fuzzy aber noch sicher
    
    def test_lowercase_normalization(self, matcher: ZoneMatcher):
        """Lowercase-Normalisierung muss funktionieren."""
        result_upper = matcher.match_room_to_zone("WOHNZIMMER")
        result_lower = matcher.match_room_to_zone("wohnzimmer")
        assert result_upper.zone.zone_type == result_lower.zone.zone_type
        assert result_upper.confidence == result_lower.confidence
    
    def test_confidence_score_range(self, matcher: ZoneMatcher):
        """Confidence muss zwischen 0 und 100 liegen."""
        test_rooms = ["Wohnzimmer", "Bad", "Küche", "Unbekannter Raum"]
        for room in test_rooms:
            result = matcher.match_room_to_zone(room)
            assert 0 <= result.confidence <= 100
    
    def test_review_threshold(self, matcher: ZoneMatcher):
        """Review-Flag bei niedriger Confidence."""
        # Unsicherer Raum
        result = matcher.match_room_to_zone("Speicherraum XY123")
        # Sollte Review benötigen (niedrige Confidence)
        assert result.needs_review == (result.confidence < 70)
    
    def test_match_result_to_dict(self, matcher: ZoneMatcher):
        """MatchResult.to_dict() muss funktionieren."""
        result = matcher.match_room_to_zone("Wohnzimmer")
        d = result.to_dict()
        
        assert "room_name" in d
        assert "zone_type" in d
        assert "zone_name_de" in d
        assert "confidence" in d
        assert "needs_review" in d
        assert d["room_name"] == "Wohnzimmer"
        assert d["zone_type"] == "living"


class TestConvenienceFunctions:
    """Tests für Convenience-Funktionen."""
    
    def test_match_room_function(self):
        """match_room() Convenience-Funktion."""
        result = match_room("Küche")
        assert result.zone.zone_type == ZoneType.KITCHEN
        assert result.confidence >= 70
    
    def test_match_rooms_batch(self):
        """match_rooms() für mehrere Räume."""
        rooms = ["Wohnzimmer", "Küche", "Bad"]
        results = match_rooms(rooms)
        
        assert len(results) == 3
        assert results[0].zone.zone_type == ZoneType.LIVING
        assert results[1].zone.zone_type == ZoneType.KITCHEN
        assert results[2].zone.zone_type == ZoneType.BATH
    
    def test_get_matcher_singleton(self):
        """get_matcher() gibt Singleton zurück."""
        matcher1 = get_matcher()
        matcher2 = get_matcher()
        assert matcher1 is matcher2  # Gleiche Instanz


class TestReviewQueue:
    """Tests für Review-Queue-Funktionalität."""
    
    @pytest.fixture
    def matcher(self):
        return ZoneMatcher()
    
    def test_get_review_queue(self, matcher: ZoneMatcher):
        """Review-Queue für unsichere Matches."""
        # Mischung aus sicheren und unsicheren Räumen
        rooms = ["Wohnzimmer", "Küche", "Unbekannter Raum XYZ", "Speicher 123"]
        review = matcher.get_review_queue(rooms)
        
        # Unsichere Räume sollten im Review sein
        for item in review:
            assert item.confidence < 70
            assert item.needs_review
    
    def test_get_high_confidence_matches(self, matcher: ZoneMatcher):
        """Nur sichere Matches."""
        rooms = ["Wohnzimmer", "Küche", "Bad", "Unbekannt"]
        high_conf = matcher.get_high_confidence_matches(rooms, threshold=70)
        
        for item in high_conf:
            assert item.confidence >= 70
            assert not item.needs_review


class TestEdgeCases:
    """Tests für Randfälle."""
    
    @pytest.fixture
    def matcher(self):
        return ZoneMatcher()
    
    def test_empty_room_name(self, matcher: ZoneMatcher):
        """Leerer Raum-Name."""
        result = matcher.match_room_to_zone("")
        assert result is not None
        assert result.confidence >= 0
    
    def test_special_characters(self, matcher: ZoneMatcher):
        """Sonderzeichen im Raum-Namen."""
        result1 = matcher.match_room_to_zone("Wohnzimmer!")
        result2 = matcher.match_room_to_zone("Wohnzimmer")
        # Sollte ähnlich matchen (Sonderzeichen werden entfernt)
        assert result1.zone.zone_type == result2.zone.zone_type
    
    def test_very_long_name(self, matcher: ZoneMatcher):
        """Sehr langer Raum-Name."""
        long_name = "Das ist ein sehr sehr langer Raumname der definitiv zu lang ist"
        result = matcher.match_room_to_zone(long_name)
        assert result is not None
        assert result.confidence >= 0
    
    def test_mixed_language(self, matcher: ZoneMatcher):
        """Gemischte Sprache."""
        result = matcher.match_room_to_zone("Living Room")
        assert result.zone.zone_type == ZoneType.LIVING
    
    def test_numbers_in_name(self, matcher: ZoneMatcher):
        """Zahlen im Raum-Namen."""
        result = matcher.match_room_to_zone("Zimmer 1")
        assert result is not None


class TestZoneMatcherInitialization:
    """Tests für Matcher-Initialisierung."""
    
    def test_matcher_has_keyword_map(self):
        """Matcher muss Keyword-Map haben."""
        matcher = ZoneMatcher()
        assert len(matcher.keyword_map) > 0
    
    def test_matcher_has_zones(self):
        """Matcher muss Zonen haben."""
        matcher = ZoneMatcher()
        assert len(matcher.zones) == 10
    
    def test_matcher_has_fuzzy_mappings(self):
        """Matcher muss Fuzzy-Mappings haben."""
        matcher = ZoneMatcher()
        assert len(matcher.fuzzy_mappings) > 0


# === API-Tests (wenn FastAPI verfügbar) ===

try:
    from fastapi.testclient import TestClient
    from copilot_core.api.v1.zones import router as zones_router
    from fastapi import FastAPI
    
    app = FastAPI()
    app.include_router(zones_router, prefix="/api/v1")
    client = TestClient(app)
    
    class TestZoneAPI:
        """Tests für Zone-API-Endpoints."""
        
        def test_get_habitus_zones(self):
            """GET /api/v1/zones/habitus"""
            response = client.get("/api/v1/zones/habitus")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 10
            
            # Prüfe Struktur
            zone = data[0]
            assert "zone_type" in zone
            assert "name_de" in zone
            assert "keywords_de" in zone
        
        def test_get_matched_rooms(self):
            """GET /api/v1/zones/matched"""
            response = client.get("/api/v1/zones/matched?rooms=Wohnzimmer,Küche")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["zone_type"] == "living"
            assert data[1]["zone_type"] == "kitchen"
        
        def test_match_single_room(self):
            """GET /api/v1/zones/match/{room_name}"""
            response = client.get("/api/v1/zones/match/Badezimmer")
            assert response.status_code == 200
            data = response.json()
            assert data["zone_type"] == "bath"
            assert data["confidence"] >= 70
        
        def test_assign_room(self):
            """POST /api/v1/zones/assign"""
            payload = {
                "room_name": "Gästeklo",
                "zone_type": "bath",
                "override_existing": False
            }
            response = client.post("/api/v1/zones/assign", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["zone_type"] == "bath"
            assert data["confidence"] == 100.0  # Manuell = 100%
        
        def test_add_tag(self):
            """POST /api/v1/zones/tag"""
            payload = {
                "room_name": "Abstellraum",
                "tag": "zone:kitchen"
            }
            response = client.post("/api/v1/zones/tag", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["zone_type"] == "kitchen"
            assert "tag:zone:kitchen" in data["matched_keyword"]
        
        def test_invalid_zone_type(self):
            """Ungültiger Zone-Typ."""
            payload = {
                "room_name": "Test",
                "zone_type": "invalid_zone"
            }
            response = client.post("/api/v1/zones/assign", json=payload)
            assert response.status_code == 400
        
        def test_invalid_tag_format(self):
            """Ungültiges Tag-Format."""
            payload = {
                "room_name": "Test",
                "tag": "invalid_tag"  # Muss "zone:" prefix haben
            }
            response = client.post("/api/v1/zones/tag", json=payload)
            assert response.status_code == 400
        
        def test_review_queue(self):
            """GET /api/v1/zones/review"""
            response = client.get(
                "/api/v1/zones/review?rooms=Wohnzimmer,UnbekannterRaumXYZ"
            )
            assert response.status_code == 200
            data = response.json()
            assert "total_count" in data
            assert "rooms" in data
            # Nur unsichere Räume sollten im Review sein
            for room in data["rooms"]:
                assert room["confidence"] < 70
        
        def test_batch_match(self):
            """POST /api/v1/zones/match/batch"""
            payload = ["Wohnzimmer", "Küche", "Bad", "Flur"]
            response = client.post("/api/v1/zones/match/batch", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 4

except ImportError:
    # FastAPI nicht verfügbar, Tests überspringen
    pass
