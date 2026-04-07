"""Query Router for RAG Search.

Classifies queries as local, web, or hybrid to determine optimal search strategy.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Set

_LOGGER = logging.getLogger(__name__)


class QueryType(str, Enum):
    """Type of query for routing."""
    
    LOCAL = "local"
    """Local-only query (HA states, documents, history)"""
    
    WEB = "web"
    """Web-only query (weather, news, facts)"""
    
    HYBRID = "hybrid"
    """Hybrid query (requires both local and web context)"""


@dataclass(frozen=True)
class QueryClassification:
    """Result of query classification."""
    
    query_type: QueryType
    confidence: float
    """Confidence score 0.0-1.0"""
    
    web_keywords_found: List[str]
    """Web keywords detected in query"""
    
    local_keywords_found: List[str]
    """Local/HA keywords detected in query"""
    
    use_web_search: bool
    """Whether to enable web search"""
    
    reasoning: Optional[str] = None
    """Human-readable explanation of classification"""


# Web-related keywords (indicates need for external data)
WEB_KEYWORDS = {
    # Weather
    "wetter",
    "wettervorhersage",
    "vorhersage",
    "temperatur",
    "regen",
    "schnee",
    "sonne",
    "wind",
    "luftfeuchtigkeit",
    
    # News/Current events
    "news",
    "nachrichten",
    "aktuell",
    "neuigkeiten",
    "meldungen",
    "presse",
    
    # Time-sensitive (today/now)
    "heute",
    "jetzt",
    "gerade",
    "momentan",
    "aktuelle",
    
    # General knowledge/facts
    "wikipedia",
    "definition",
    "bedeutung",
    "was ist",
    "wer ist",
    "wann ist",
    "wo ist",
    
    # Sports/Entertainment
    "sport",
    "fußball",
    "fussball",
    "ergebnis",
    "spiel",
    "spielstand",
    "gewonnen",
    "verloren",
    "film",
    "serie",
    "kino",
    "musik",
    "konzert",
}

# Local/HomeAssistant keywords (indicates need for local data)
LOCAL_KEYWORDS = {
    # Energy/Consumption
    "verbrauch",
    "energie",
    "energieverbrauch",
    "strom",
    "stromverbrauch",
    "gas",
    "gasverbrauch",
    "wasser",
    "heizung",
    "heizungsverbrauch",
    "kwh",
    "kosten",
    "solar",
    "solarproduktion",
    
    # HA entities/states
    "state",
    "states",
    "entity",
    "entities",
    "sensor",
    "sensorwert",
    "gerät",
    "geräte",
    "device",
    "automation",
    "automatisierung",
    
    # Home-specific
    "haus",
    "wohnung",
    "raum",
    "zimmer",
    "licht",
    "lampe",
    "thermostat",
    "fenster",
    "tür",
    
    # Historical/Temporal (past)
    "gestern",
    "letzte",
    "letzten",
    "vergangen",
    "history",
    "historie",
    "protokoll",
    "log",
}

# Strong web indicators (high confidence for web-only)
STRONG_WEB_INDICATORS = {
    "wettervorhersage",
    "nachrichten",
    "wikipedia",
    "news",
}

# Strong local indicators (high confidence for local-only)
STRONG_LOCAL_INDICATORS = {
    "energieverbrauch",
    "stromverbrauch",
    "gasverbrauch",
    "automation",
    "automatisierung",
    "entity",
}


def classify_query(query: str) -> QueryClassification:
    """Classify a query as local, web, or hybrid.
    
    Analyzes the query to determine what data sources are needed:
    - **Local**: HomeAssistant states, documents, history (no web needed)
    - **Web**: Weather, news, general facts (web-only)
    - **Hybrid**: Combination (e.g., "energy consumption + weather context")
    
    Args:
        query: User query string
    
    Returns:
        QueryClassification with type, confidence, and reasoning
    
    Example:
        ```python
        # Local query
        result = classify_query("Wie war der Energieverbrauch gestern?")
        assert result.query_type == QueryType.LOCAL
        
        # Web query
        result = classify_query("Wie ist das Wetter heute?")
        assert result.query_type == QueryType.WEB
        
        # Hybrid query
        result = classify_query("Energieverbrauch bei diesem Wetter")
        assert result.query_type == QueryType.HYBRID
        ```
    """
    if not query or not query.strip():
        return QueryClassification(
            query_type=QueryType.LOCAL,
            confidence=1.0,
            web_keywords_found=[],
            local_keywords_found=[],
            use_web_search=False,
            reasoning="Empty query defaults to local",
        )
    
    query_lower = query.lower()
    
    # Find matching keywords
    web_found = _find_keywords(query_lower, WEB_KEYWORDS)
    local_found = _find_keywords(query_lower, LOCAL_KEYWORDS)
    
    # Check for strong indicators
    has_strong_web = any(kw in query_lower for kw in STRONG_WEB_INDICATORS)
    has_strong_local = any(kw in query_lower for kw in STRONG_LOCAL_INDICATORS)
    
    # Determine query type
    query_type: QueryType
    confidence: float
    reasoning: str
    
    if has_strong_web and not local_found:
        query_type = QueryType.WEB
        confidence = 0.95
        reasoning = "Strong web indicator detected, no local keywords"
    
    elif has_strong_local and not web_found:
        query_type = QueryType.LOCAL
        confidence = 0.95
        reasoning = "Strong local indicator detected, no web keywords"
    
    elif web_found and local_found:
        # Both web and local keywords present → Hybrid
        query_type = QueryType.HYBRID
        confidence = 0.85
        reasoning = f"Both web ({len(web_found)}) and local ({len(local_found)}) keywords detected"
    
    elif web_found:
        # Only web keywords
        query_type = QueryType.WEB
        # Higher confidence if time-sensitive
        if "heute" in query_lower or "jetzt" in query_lower:
            confidence = 0.9
            reasoning = "Web keywords with time-sensitive context"
        else:
            confidence = 0.75
            reasoning = f"Web keywords detected ({len(web_found)})"
    
    elif local_found:
        # Only local keywords
        query_type = QueryType.LOCAL
        confidence = 0.85
        reasoning = f"Local/HA keywords detected ({len(local_found)})"
    
    else:
        # No keywords matched → Default to local (safer for privacy)
        query_type = QueryType.LOCAL
        confidence = 0.5
        reasoning = "No specific keywords detected, defaulting to local search"
    
    return QueryClassification(
        query_type=query_type,
        confidence=confidence,
        web_keywords_found=sorted(web_found),
        local_keywords_found=sorted(local_found),
        use_web_search=query_type in (QueryType.WEB, QueryType.HYBRID),
        reasoning=reasoning,
    )


def _find_keywords(query_lower: str, keywords: Set[str]) -> List[str]:
    """Find which keywords are present in the query.
    
    Uses word-boundary matching to avoid false positives.
    
    Args:
        query_lower: Lowercase query string
        keywords: Set of keywords to search for
    
    Returns:
        List of matched keywords
    """
    found: List[str] = []
    
    for kw in keywords:
        # Use word boundary matching for multi-word keywords
        if " " in kw:
            if kw in query_lower:
                found.append(kw)
        else:
            # Single word: use word boundary regex
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, query_lower):
                found.append(kw)
    
    return found


def should_use_web_search(
    query: str,
    explicit_web: bool = False,
    min_confidence: float = 0.5,
) -> bool:
    """Determine if web search should be used for a query.
    
    Args:
        query: User query string
        explicit_web: If True, force web search regardless of classification
        min_confidence: Minimum confidence threshold for web classification
    
    Returns:
        True if web search should be enabled
    """
    if explicit_web:
        return True
    
    classification = classify_query(query)
    
    if classification.query_type == QueryType.WEB:
        return classification.confidence >= min_confidence
    
    if classification.query_type == QueryType.HYBRID:
        return classification.confidence >= min_confidence
    
    return False


# Convenience function for backward compatibility
def classify_query_simple(query: str) -> str:
    """Simple query classification returning just the type string.
    
    Args:
        query: User query string
    
    Returns:
        Query type string: "local", "web", or "hybrid"
    """
    return classify_query(query).query_type.value
