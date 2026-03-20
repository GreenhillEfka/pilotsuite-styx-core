"""Tests for the enhanced habitat zone matcher."""

import pytest
from copilot_core.homeassistant.habitus_zones_matcher import (
    HabitusZoneMatcher, match_zone, get_zone_suggestions
)
from copilot_core.homeassistant.habitus_zones import ZoneType


class TestHabitusZoneMatcher:
    """Tests for the HabitusZoneMatcher class."""
    
    def test_init(self):
        """Test initialization."""
        matcher = HabitusZoneMatcher()
        assert matcher.zones is not None
        assert len(matcher.keyword_map) > 0
    
    def test_match_zone_by_name_exact(self):
        """Test exact name matching."""
        matcher = HabitusZoneMatcher()
        
        # Test German names
        result = matcher.match_zone_by_name("Wohnbereich")
        assert result == ZoneType.LIVING
        
        # Test English names
        result = matcher.match_zone_by_name("Living Area")
        assert result == ZoneType.LIVING
        
        # Test non-existent name
        result = matcher.match_zone_by_name("Non Existent Zone")
        assert result is None
    
    def test_match_zone_by_keyword(self):
        """Test keyword matching."""
        matcher = HabitusZoneMatcher()
        
        # Test German keywords
        result = matcher.match_zone_by_keyword("wohnzimmer")
        assert result == ZoneType.LIVING
        
        # Test English keywords
        result = matcher.match_zone_by_keyword("kitchen")
        assert result == ZoneType.KITCHEN
        
        # Test non-existent keyword
        result = matcher.match_zone_by_keyword("nonexistentkeyword")
        assert result is None
    
    def test_fuzzy_match_zone(self):
        """Test fuzzy matching."""
        matcher = HabitusZoneMatcher()
        
        # Test close match to Wohnbereich
        result = matcher.fuzzy_match_zone("Wohnzimmer")
        assert result is not None
        assert result[0] == ZoneType.LIVING
        
        # Test close match to Kitchen
        result = matcher.fuzzy_match_zone("Küche")
        assert result is not None
        assert result[0] == ZoneType.KITCHEN
        
        # Test with low threshold (should still match)
        result = matcher.fuzzy_match_zone("Wohn", threshold=0.3)
        assert result is not None
        
        # Test with high threshold (might not match)
        result = matcher.fuzzy_match_zone("Wohn", threshold=0.9)
        # May or may not match depending on similarity
    
    def test_get_similar_zones(self):
        """Test getting similar zones."""
        matcher = HabitusZoneMatcher()
        
        # Test getting suggestions for "Wohn"
        results = matcher.get_similar_zones("Wohn")
        assert len(results) > 0
        # Should include LIVING zone
        zone_types = [result[0] for result in results]
        assert ZoneType.LIVING in zone_types
    
    def test_get_zone_info(self):
        """Test getting zone information."""
        matcher = HabitusZoneMatcher()
        
        # Test getting info for LIVING zone
        info = matcher.get_zone_info(ZoneType.LIVING)
        assert info is not None
        assert info.zone_type == ZoneType.LIVING
        assert info.name_de == "Wohnbereich"
        assert "wohn" in info.keywords_de


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    def test_match_zone(self):
        """Test the match_zone convenience function."""
        # Test exact match
        result = match_zone("Wohnbereich")
        assert result == ZoneType.LIVING
        
        # Test fuzzy match
        result = match_zone("Wohnzimmer")
        assert result == ZoneType.LIVING
    
    def test_get_zone_suggestions(self):
        """Test the get_zone_suggestions convenience function."""
        suggestions = get_zone_suggestions("Wohn")
        assert len(suggestions) > 0
        # Should include LIVING zone
        zone_types = [suggestion[0] for suggestion in suggestions]
        assert ZoneType.LIVING in zone_types


if __name__ == "__main__":
    pytest.main([__file__])