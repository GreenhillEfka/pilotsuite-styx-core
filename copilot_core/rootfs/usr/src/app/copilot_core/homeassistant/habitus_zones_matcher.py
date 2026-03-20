"""Enhanced habitat zone matching with fuzzy matching capabilities."""

from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher
from .habitus_zones import HABITUS_ZONES, ZoneType, HabitusZone


class HabitusZoneMatcher:
    """Enhanced matcher for habitat zones with fuzzy matching capabilities."""
    
    def __init__(self):
        """Initialize the matcher with zone data."""
        self.zones = HABITUS_ZONES
        self.keyword_map = self._build_keyword_map()
    
    def _build_keyword_map(self) -> Dict[str, ZoneType]:
        """Build a comprehensive keyword mapping for fast lookup."""
        keyword_map = {}
        for zone in self.zones.values():
            for keyword in zone.get_all_keywords():
                keyword_map[keyword.lower()] = zone.zone_type
        return keyword_map
    
    def match_zone_by_name(self, zone_name: str) -> Optional[ZoneType]:
        """Match a zone by its exact name."""
        zone_name_lower = zone_name.lower()
        for zone_type, zone in self.zones.items():
            if zone.name_de.lower() == zone_name_lower or zone.name_en.lower() == zone_name_lower:
                return zone_type
        return None
    
    def match_zone_by_keyword(self, keyword: str) -> Optional[ZoneType]:
        """Match a zone by exact keyword."""
        return self.keyword_map.get(keyword.lower())
    
    def fuzzy_match_zone(self, input_text: str, threshold: float = 0.6) -> Optional[Tuple[ZoneType, float]]:
        """Fuzzy match a zone based on input text.
        
        Args:
            input_text: Text to match against zone names and keywords
            threshold: Minimum similarity ratio (0.0-1.0)
            
        Returns:
            Tuple of (ZoneType, similarity_score) or None
        """
        input_lower = input_text.lower()
        best_match = None
        best_score = 0.0
        
        # Check against zone names
        for zone_type, zone in self.zones.items():
            # Match against German name
            score_de = SequenceMatcher(None, input_lower, zone.name_de.lower()).ratio()
            # Match against English name
            score_en = SequenceMatcher(None, input_lower, zone.name_en.lower()).ratio()
            # Match against keywords
            keyword_scores = [
                SequenceMatcher(None, input_lower, kw.lower()).ratio()
                for kw in zone.get_all_keywords()
            ]
            max_keyword_score = max(keyword_scores) if keyword_scores else 0.0
            
            # Take the highest score among all matches
            max_score = max(score_de, score_en, max_keyword_score)
            
            if max_score > best_score and max_score >= threshold:
                best_score = max_score
                best_match = zone_type
        
        if best_match:
            return (best_match, best_score)
        return None
    
    def get_similar_zones(self, input_text: str, max_results: int = 5) -> List[Tuple[ZoneType, float]]:
        """Get similar zones ranked by similarity score."""
        results = []
        input_lower = input_text.lower()
        
        for zone_type, zone in self.zones.items():
            # Match against German name
            score_de = SequenceMatcher(None, input_lower, zone.name_de.lower()).ratio()
            # Match against English name
            score_en = SequenceMatcher(None, input_lower, zone.name_en.lower()).ratio()
            # Match against keywords
            keyword_scores = [
                SequenceMatcher(None, input_lower, kw.lower()).ratio()
                for kw in zone.get_all_keywords()
            ]
            max_keyword_score = max(keyword_scores) if keyword_scores else 0.0
            
            # Take the highest score among all matches
            max_score = max(score_de, score_en, max_keyword_score)
            
            if max_score > 0.1:  # Minimum threshold to be considered
                results.append((zone_type, max_score))
        
        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:max_results]
    
    def get_zone_info(self, zone_type: ZoneType) -> Optional[HabitusZone]:
        """Get detailed information about a zone."""
        return self.zones.get(zone_type)


def create_zone_matcher() -> HabitusZoneMatcher:
    """Factory function to create a zone matcher instance."""
    return HabitusZoneMatcher()


# Convenience functions for common use cases
def match_zone(input_text: str, fuzzy_threshold: float = 0.6) -> Optional[ZoneType]:
    """Convenience function to match a zone."""
    matcher = create_zone_matcher()
    
    # Try exact match first
    exact_match = matcher.match_zone_by_name(input_text) or matcher.match_zone_by_keyword(input_text)
    if exact_match:
        return exact_match
    
    # Try fuzzy match
    fuzzy_result = matcher.fuzzy_match_zone(input_text, fuzzy_threshold)
    if fuzzy_result:
        return fuzzy_result[0]
    
    return None


def get_zone_suggestions(input_text: str, max_results: int = 5) -> List[Tuple[ZoneType, float]]:
    """Get zone suggestions for input text."""
    matcher = create_zone_matcher()
    return matcher.get_similar_zones(input_text, max_results)