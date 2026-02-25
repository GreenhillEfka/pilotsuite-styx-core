"""
Tests for Scene and Routine Pattern Extractors (v7.11.1)
"""

import pytest
import json
import os
import sys
from unittest.mock import Mock, patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'usr', 'src', 'app'))


class TestScenePatternExtractor:
    """Test Scene Pattern Extraction."""
    
    def test_imports(self):
        """Scene pattern extractor should be importable."""
        from copilot_core.scene_patterns import ScenePatternExtractor, get_scene_pattern_extractor
        assert ScenePatternExtractor is not None
        assert get_scene_pattern_extractor is not None
    
    def test_instantiation(self):
        """Should instantiate without errors."""
        from copilot_core.scene_patterns import ScenePatternExtractor
        extractor = ScenePatternExtractor()
        assert extractor is not None
    
    def test_record_activation(self):
        """Should record scene activations."""
        from copilot_core.scene_patterns import ScenePatternExtractor
        extractor = ScenePatternExtractor()
        extractor.record_scene_activation("abend")
        
        summary = extractor.get_pattern_summary()
        assert summary["total_activations"] >= 1
    
    def test_suggest_scenes(self):
        """Should return scene suggestions."""
        from copilot_core.scene_patterns import ScenePatternExtractor
        extractor = ScenePatternExtractor()
        
        # Record some activations
        extractor.record_scene_activation("morgen")
        extractor.record_scene_activation("morgen")
        extractor.record_scene_activation("abend")
        
        suggestions = extractor.suggest_scenes()
        assert isinstance(suggestions, list)


class TestRoutinePatternExtractor:
    """Test Routine Pattern Extraction."""
    
    def test_imports(self):
        """Routine pattern extractor should be importable."""
        from copilot_core.routine_patterns import RoutinePatternExtractor, get_routine_pattern_extractor
        assert RoutinePatternExtractor is not None
    
    def test_instantiation(self):
        """Should instantiate without errors."""
        from copilot_core.routine_patterns import RoutinePatternExtractor
        extractor = RoutinePatternExtractor()
        assert extractor is not None
    
    def test_record_action(self):
        """Should record user actions."""
        from copilot_core.routine_patterns import RoutinePatternExtractor
        extractor = RoutinePatternExtractor()
        extractor.record_action("light_turned_on", "light.living_room", "on")
        
        summary = extractor.get_pattern_summary()
        assert summary["total_actions"] >= 1
    
    def test_predict_next_action(self):
        """Should predict next actions."""
        from copilot_core.routine_patterns import RoutinePatternExtractor
        extractor = RoutinePatternExtractor()
        
        # Record some actions
        extractor.record_action("light_turned_on", "light.living_room", "on")
        extractor.record_action("light_turned_on", "light.living_room", "on")
        
        predictions = extractor.predict_next_action()
        assert isinstance(predictions, list)


class TestPatternAPI:
    """Test Pattern API endpoints."""
    
    def test_scene_patterns_api_imports(self):
        """Scene patterns API should be importable."""
        try:
            from copilot_core.api.v1.scene_patterns import scene_patterns_bp
            assert scene_patterns_bp is not None
        except ImportError as e:
            pytest.skip(f"Flask not available: {e}")
    
    def test_routine_patterns_api_imports(self):
        """Routine patterns API should be importable."""
        try:
            from copilot_core.api.v1.routine_patterns import routine_patterns_bp
            assert routine_patterns_bp is not None
        except ImportError as e:
            pytest.skip(f"Flask not available: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
