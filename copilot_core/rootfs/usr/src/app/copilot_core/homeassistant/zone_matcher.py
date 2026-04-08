"""
ML-basiertes Zone-Matching für PilotSuite Styx Core

Matcht Raum-Namen zu Habituszonen mit Fuzzy-Matching und Confidence-Scores.
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from .habitus_zones import HabitusZone, ZoneType, HABITUS_ZONES, get_zone_keywords


@dataclass
class MatchResult:
    """Ergebnis eines Zone-Matchings."""
    room_name: str
    zone: HabitusZone
    confidence: float  # 0-100
    matched_keyword: Optional[str] = None
    needs_review: bool = False  # True wenn Confidence < 70%
    
    def to_dict(self) -> Dict:
        """Als Dictionary für API-Responses."""
        return {
            "room_name": self.room_name,
            "zone_type": self.zone.zone_type.value,
            "zone_name_de": self.zone.name_de,
            "zone_name_en": self.zone.name_en,
            "confidence": self.confidence,
            "matched_keyword": self.matched_keyword,
            "needs_review": self.needs_review
        }


class ZoneMatcher:
    """
    ML-basierter Zone-Matcher mit Fuzzy-Matching.
    
    Features:
    - Keyword-basiertes Matching mit Prioritäten
    - Fuzzy-Matching für ähnliche Begriffe
    - Confidence-Score Berechnung
    - Review-Queue für unsichere Zuordnungen
    """
    
    REVIEW_THRESHOLD = 70.0  # Confidence unter diesem Wert → Review
    
    def __init__(self):
        self.keyword_map = get_zone_keywords()
        self.zones = HABITUS_ZONES
        
        # Fuzzy-Mapping für häufige Variationen
        self.fuzzy_mappings = {
            "wohnzimmer": "wohn",
            "wohnraum": "wohn",
            "wohn-bereich": "wohn",
            "badezimmer": "bad",
            "badzimmer": "bad",
            "bade": "bad",
            "küche": "koch",
            "kochzimmer": "koch",
            "kochbereich": "koch",
            "büro": "büro",
            "arbeitszimmer": "büro",
            "homeoffice": "büro",
            "flur": "gang",
            "diele": "gang",
            "schlafzimmer": "schlaf",
            "schlafraum": "schlaf",
            "schlaf": "schlaf",
            "kinderzimmer": "kinder",
            "terra": "terrass",
            "balkon": "terrass",
            "garten": "aussen",
            "außen": "aussen",
            "mira": "mira",
            "zimmer mira": "mira",
            "paul": "paul",
            "zimmer paul": "paul",
        }
    
    def _normalize_room_name(self, room_name: str) -> str:
        """Raum-Namen normalisieren (lowercase, Sonderzeichen entfernen)."""
        normalized = room_name.lower().strip()
        # Sonderzeichen und Mehrfach-Leerzeichen entfernen
        normalized = re.sub(r'[^\w\säöüß]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized
    
    def _calculate_keyword_match_score(self, room_name: str, keywords: List[str]) -> Tuple[float, Optional[str]]:
        """
        Berechnet Match-Score basierend auf Keywords.
        Returns: (score, best_matched_keyword)
        """
        normalized = self._normalize_room_name(room_name)
        best_score = 0.0
        best_keyword = None
        
        for keyword in keywords:
            keyword_norm = keyword.lower()
            
            # Exakter Match
            if keyword_norm == normalized:
                return 100.0, keyword
            
            # Teilstring-Match
            if keyword_norm in normalized:
                score = 85.0 + (len(keyword_norm) / len(normalized)) * 15.0
                if score > best_score:
                    best_score = score
                    best_keyword = keyword
            
            # Fuzzy-Match (einfache Ähnlichkeit)
            similarity = self._string_similarity(normalized, keyword_norm)
            if similarity > 0.7:  # Nur bei hoher Ähnlichkeit
                score = similarity * 80.0
                if score > best_score:
                    best_score = score
                    best_keyword = keyword
        
        return best_score, best_keyword
    
    def _string_similarity(self, s1: str, s2: str) -> float:
        """
        Berechnet String-Ähnlichkeit (Levenshtein-basiert).
        Returns: Wert zwischen 0.0 und 1.0
        """
        if not s1 or not s2:
            return 0.0
        
        # Einfache Implementierung für Performance
        len1, len2 = len(s1), len(s2)
        if abs(len1 - len2) > 3:  # Zu unterschiedlich
            return 0.0
        
        # Character-basierte Ähnlichkeit
        common_chars = sum(1 for c in s1 if c in s2)
        max_len = max(len1, len2)
        return common_chars / max_len if max_len > 0 else 0.0
    
    def _apply_fuzzy_mappings(self, room_name: str) -> Optional[str]:
        """Wendet Fuzzy-Mappings an und gibt normalisierten Begriff zurück."""
        normalized = self._normalize_room_name(room_name)
        
        for fuzzy, base in self.fuzzy_mappings.items():
            if fuzzy in normalized or normalized in fuzzy:
                return base
        return None

    def _match_outdoor_canonical_alias(self, room_name: str) -> Optional[Tuple[HabitusZone, float, str]]:
        """Kanonisiert Terrassen-/Outdoor-Aliase deterministisch auf OUTSIDE."""
        normalized = self._normalize_room_name(room_name)
        outdoor_aliases = ("terrasse", "terrass", "balkon", "loggia")

        for alias in outdoor_aliases:
            if alias in normalized:
                return self.zones[ZoneType.OUTSIDE], 98.0, alias

        return None

    def _match_kitchen_canonical_alias(self, room_name: str) -> Optional[Tuple[HabitusZone, float, str]]:
        """Kanonisiert kuechenbereich deterministisch auf KITCHEN."""
        normalized = self._normalize_room_name(room_name)
        if "kuechenbereich" in normalized:
            return self.zones[ZoneType.KITCHEN], 98.0, "kuechenbereich"
        return None
    
    def match_room_to_zone(self, room_name: str) -> MatchResult:
        """
        Matcht einen Raum-Namen zu einer Habituszone.
        
        Args:
            room_name: Name des Raums
            
        Returns:
            MatchResult mit Zone, Confidence und Metadata
        """
        normalized = self._normalize_room_name(room_name)
        best_match: Optional[Tuple[HabitusZone, float, str]] = None

        # 0. Outdoor-Kanonisierung vor generischem Fuzzy-/Keyword-Matching.
        outdoor_match = self._match_outdoor_canonical_alias(room_name)
        if outdoor_match is not None:
            zone, confidence, matched_keyword = outdoor_match
            return MatchResult(
                room_name=room_name,
                zone=zone,
                confidence=confidence,
                matched_keyword=matched_keyword,
                needs_review=confidence < self.REVIEW_THRESHOLD,
            )

        # 0b. Kuechenbereich-Kanonisierung vor generischem Fuzzy-/Keyword-Matching.
        kitchen_match = self._match_kitchen_canonical_alias(room_name)
        if kitchen_match is not None:
            zone, confidence, matched_keyword = kitchen_match
            return MatchResult(
                room_name=room_name,
                zone=zone,
                confidence=confidence,
                matched_keyword=matched_keyword,
                needs_review=confidence < self.REVIEW_THRESHOLD,
            )
        
        # 1. Fuzzy-Mapping versuchen (für spezifische Namen wie Mira, Paul)
        fuzzy_base = self._apply_fuzzy_mappings(room_name)
        if fuzzy_base:
            # Suche Zone mit diesem Keyword
            for zone in self.zones.values():
                for keyword in zone.keywords_de + zone.keywords_en:
                    if fuzzy_base in keyword.lower() or keyword.lower() in fuzzy_base:
                        # Hohe Priorität für spezifische Namen
                        if zone.zone_type in [ZoneType.ROOM_MIRA, ZoneType.ROOM_PAUL]:
                            score = 95.0
                        else:
                            score = 75.0  # Fuzzy-Match hat mittlere Confidence
                        if best_match is None or score > best_match[1]:
                            best_match = (zone, score, keyword)
        
        # 2. Keyword-basiertes Matching für alle Zonen
        for zone in self.zones.values():
            score, matched_keyword = self._calculate_keyword_match_score(
                room_name, 
                zone.get_all_keywords()
            )
            
            # Prioritäts-Bonus (höher für spezifische Zonen)
            if score > 0:
                if zone.zone_type in [ZoneType.ROOM_MIRA, ZoneType.ROOM_PAUL]:
                    score += min(zone.priority, 20)  # Bis zu 20 Punkte für spezifische
                else:
                    score += min(zone.priority, 10)  # Max 10 Punkte Bonus
            
            if score > 99.0:
                score = 99.0  # Cap bei 99% (100% nur bei exaktem Match)
            
            if best_match is None or score > best_match[1]:
                best_match = (zone, score, matched_keyword)
        
        # Fallback: Wenn kein Match, dann Outside als Default
        if best_match is None:
            best_match = (
                self.zones[ZoneType.OUTSIDE],
                30.0,  # Niedrige Confidence für Fallback
                None
            )
        
        zone, confidence, matched_keyword = best_match
        
        return MatchResult(
            room_name=room_name,
            zone=zone,
            confidence=confidence,
            matched_keyword=matched_keyword,
            needs_review=confidence < self.REVIEW_THRESHOLD
        )
    
    def match_multiple_rooms(self, room_names: List[str]) -> List[MatchResult]:
        """Matcht mehrere Räume auf einmal."""
        return [self.match_room_to_zone(name) for name in room_names]
    
    def get_review_queue(self, room_names: List[str]) -> List[MatchResult]:
        """
        Gibt alle Räume zurück, die Review benötigen (Confidence < 70%).
        """
        results = self.match_multiple_rooms(room_names)
        return [r for r in results if r.needs_review]
    
    def get_high_confidence_matches(self, room_names: List[str], threshold: float = 70.0) -> List[MatchResult]:
        """
        Gibt alle sicheren Matches zurück (Confidence >= threshold).
        """
        results = self.match_multiple_rooms(room_names)
        return [r for r in results if r.confidence >= threshold]


# Singleton-Instanz für einfache Nutzung
_matcher_instance: Optional[ZoneMatcher] = None

def get_matcher(refresh: bool = False) -> ZoneMatcher:
    """Singleton-Zugriff auf ZoneMatcher."""
    global _matcher_instance
    if _matcher_instance is None or refresh:
        _matcher_instance = ZoneMatcher()
    return _matcher_instance


def match_room(room_name: str) -> MatchResult:
    """Convenience-Funktion für einzelnes Room-Matching."""
    return get_matcher().match_room_to_zone(room_name)


def match_rooms(room_names: List[str]) -> List[MatchResult]:
    """Convenience-Funktion für multiples Room-Matching."""
    return get_matcher().match_multiple_rooms(room_names)
