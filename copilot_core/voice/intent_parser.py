"""
Voice Intent Parser with Confidence Scoring (Slice 163 Extension)

Three-Tier Confidence Routing:
- ≥0.85: Execute directly
- 0.60-0.84: Ask clarifying question
- <0.60: Fallback + suggest alternatives

Owner: homeclaw + orakel
Priority: P1
Status: IMPLEMENTING
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class IntentParseResult:
    intent: str
    confidence: float
    slots: Dict[str, Any]
    missing_slots: List[str]
    clarification_needed: bool
    action: str  # EXECUTE, CLARIFY, FALLBACK


class IntentParser:
    """Three-tier confidence routing for voice intents."""
    
    CONFIDENCE_THRESHOLDS = {
        'EXECUTE': 0.85,
        'CLARIFY': 0.60,
    }
    
    def __init__(self):
        self.regex_patterns = self._load_regex_patterns()
        self.intent_descriptions = self._load_intent_descriptions()
    
    def _load_regex_patterns(self) -> Dict[str, List[Tuple[str, float]]]:
        """Load regex patterns with confidence scores."""
        return {
            'light.turn_on': [
                (r'(mach|schalte)\s+(das\s+)?licht\s+(ein|an)', 0.95),
                (r'licht\s+(im|in)\s+(\w+)', 0.85),
                (r'(schalte|mach)\s+(\w+)\s+(ein|an)', 0.75),
            ],
            'light.turn_off': [
                (r'(mach|schalte)\s+(das\s+)?licht\s+aus', 0.95),
                (r'licht\s+(im|in)\s+(\w+)\s+aus', 0.85),
                (r'(schalte|mach)\s+(\w+)\s+aus', 0.75),
            ],
            'climate.set_temperature': [
                (r'(stell|setz)\s+(die\s+)?temperatur\s+(auf\s+)?(\d+)', 0.95),
                (r'(\d+)\s+(grad|°)\s+(im|in)\s+(\w+)', 0.85),
                (r'(heiz|kühl)\s+(auf\s+)?(\d+)', 0.75),
            ],
            'cover.open_cover': [
                (r'(mach|fahr)\s+(den\s+)?roll(laden)?\s+(auf|hoch)', 0.95),
                (r'roll(laden)?\s+(im|in)\s+(\w+)\s+(auf|hoch)', 0.85),
            ],
            'cover.close_cover': [
                (r'(mach|fahr)\s+(den\s+)?roll(laden)?\s+(zu|runter|dicht)', 0.95),
                (r'roll(laden)?\s+(im|in)\s+(\w+)\s+(zu|runter)', 0.85),
            ],
        }
    
    def _load_intent_descriptions(self) -> Dict[str, str]:
        """Load German descriptions for intents."""
        return {
            'light.turn_on': 'Licht einschalten',
            'light.turn_off': 'Licht ausschalten',
            'climate.set_temperature': 'Temperatur setzen',
            'cover.open_cover': 'Rollladen öffnen',
            'cover.close_cover': 'Rollladen schließen',
        }
    
    def parse(self, text: str) -> IntentParseResult:
        """Parse voice command with confidence scoring."""
        text = text.lower().strip()
        
        # Tier 1: Regex matching
        regex_result = self._regex_match(text)
        if regex_result and regex_result.confidence >= self.CONFIDENCE_THRESHOLDS['EXECUTE']:
            return regex_result
        
        # Tier 2: ML classification (placeholder - would use ONNX model)
        ml_result = self._ml_classify(text)
        if ml_result and ml_result.confidence >= self.CONFIDENCE_THRESHOLDS['EXECUTE']:
            return ml_result
        
        # Tier 3: LLM fallback (placeholder - would call LLM)
        llm_result = self._llm_parse(text)
        return llm_result
    
    def _regex_match(self, text: str) -> Optional[IntentParseResult]:
        """Match against regex patterns."""
        best_match = None
        best_confidence = 0.0
        
        for intent, patterns in self.regex_patterns.items():
            for pattern, confidence in patterns:
                match = re.search(pattern, text)
                if match and confidence > best_confidence:
                    best_confidence = confidence
                    best_match = intent
                    
                    # Extract slots from match groups
                    slots = self._extract_slots(intent, match, text)
        
        if best_match:
            missing_slots = self._get_required_slots(best_match)
            for slot in missing_slots:
                if slot in slots:
                    missing_slots.remove(slot)
            
            return IntentParseResult(
                intent=best_match,
                confidence=best_confidence,
                slots=slots if 'slots' in dir() else {},
                missing_slots=missing_slots,
                clarification_needed=len(missing_slots) > 0,
                action=self._determine_action(best_confidence),
            )
        
        return None
    
    def _ml_classify(self, text: str) -> Optional[IntentParseResult]:
        """ML classification (placeholder for ONNX model)."""
        # TODO: Load ONNX model and classify
        return None
    
    def _llm_parse(self, text: str) -> IntentParseResult:
        """LLM fallback parsing."""
        return IntentParseResult(
            intent='unknown',
            confidence=0.3,
            slots={},
            missing_slots=[],
            clarification_needed=True,
            action='FALLBACK',
        )
    
    def _extract_slots(self, intent: str, match: re.Match, text: str) -> Dict[str, Any]:
        """Extract slots from regex match."""
        slots = {}
        
        # Extract room from common patterns
        room_match = re.search(r'(im|in)\s+(\w+)', text)
        if room_match:
            slots['room'] = room_match.group(2)
        
        # Extract temperature
        temp_match = re.search(r'(\d+)\s*(grad|°)', text)
        if temp_match:
            slots['target_temp'] = int(temp_match.group(1))
        
        return slots
    
    def _get_required_slots(self, intent: str) -> List[str]:
        """Get required slots for intent."""
        required = {
            'light.turn_on': ['room'],
            'light.turn_off': ['room'],
            'climate.set_temperature': ['target_temp', 'room'],
            'cover.open_cover': ['room'],
            'cover.close_cover': ['room'],
        }
        return required.get(intent, [])
    
    def _determine_action(self, confidence: float) -> str:
        """Determine action based on confidence."""
        if confidence >= self.CONFIDENCE_THRESHOLDS['EXECUTE']:
            return 'EXECUTE'
        elif confidence >= self.CONFIDENCE_THRESHOLDS['CLARIFY']:
            return 'CLARIFY'
        else:
            return 'FALLBACK'
    
    def generate_clarification_question(self, result: IntentParseResult) -> str:
        """Generate German clarification question."""
        if result.action != 'CLARIFY':
            return None
        
        if result.missing_slots:
            slot = result.missing_slots[0]
            slot_questions = {
                'room': 'Welchen Raum meinst du?',
                'target_temp': 'Welche Temperatur möchtest du?',
            }
            return slot_questions.get(slot, 'Bitte genauer beschreiben.')
        
        return 'Meintest du das? Bitte bestätigen.'
    
    def generate_fallback_response(self, result: IntentParseResult) -> str:
        """Generate German fallback response."""
        suggestions = [
            'Licht im Wohnzimmer einschalten',
            'Temperatur auf 22 Grad setzen',
            'Rollladen im Schlafzimmer schließen',
        ]
        
        return f"Ich habe das nicht verstanden. Meintest du: {suggestions[0]}?"


# Global instance
_intent_parser: Optional[IntentParser] = None


def get_intent_parser() -> IntentParser:
    """Get or create global intent parser instance."""
    global _intent_parser
    if _intent_parser is None:
        _intent_parser = IntentParser()
    return _intent_parser
