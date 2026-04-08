"""
Confidence Router — Three-Tier Voice Intent Routing

Routes intents based on confidence score:
- ≥0.85: Execute directly
- 0.60-0.84: Clarify
- <0.60: Fallback

Owner: homeclaw + orakel
Priority: P1
Status: IMPLEMENTING
"""

from typing import Dict, Any, Optional
from .intent_parser import IntentParseResult, get_intent_parser


class ConfidenceRouter:
    """Routes voice intents based on confidence."""
    
    THRESHOLDS = {
        'EXECUTE': 0.85,
        'CLARIFY': 0.60,
    }
    
    def __init__(self):
        self.parser = get_intent_parser()
    
    def route(self, text: str) -> Dict[str, Any]:
        """Route voice command based on confidence."""
        result = self.parser.parse(text)
        
        response = {
            'intent': result.intent,
            'confidence': result.confidence,
            'slots': result.slots,
            'action': result.action,
        }
        
        if result.action == 'CLARIFY':
            response['clarification_question'] = self.parser.generate_clarification_question(result)
        elif result.action == 'FALLBACK':
            response['fallback_response'] = self.parser.generate_fallback_response(result)
        
        return response
    
    def execute_intent(self, intent: str, slots: Dict[str, Any]) -> bool:
        """Execute intent (placeholder for actual execution)."""
        # TODO: Route to actual HA service calls
        print(f"Executing: {intent} with slots: {slots}")
        return True


# Global instance
_router: Optional[ConfidenceRouter] = None


def get_confidence_router() -> ConfidenceRouter:
    """Get or create global router instance."""
    global _router
    if _router is None:
        _router = ConfidenceRouter()
    return _router
