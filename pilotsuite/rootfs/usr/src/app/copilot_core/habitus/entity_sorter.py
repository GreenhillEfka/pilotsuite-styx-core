"""
HA-Entity → Habitus-Zone Sorter for PilotSuite Core.

Ported from HA v15.0.0 `habitus_entity_sorting.py` (337 lines).

Maps HomeAssistant entities to Habitus zones using keyword matching
on entity_id and entity_name. Returns (zone_id, confidence) tuples.

Confidence thresholds:
  >= 0.5  → accepted zone assignment
  < 0.5   → zone:ungeordnet (unsorted)

Usage:
    from copilot_core.habitus.entity_sorter import sort_entity_to_zone
    zone_id, confidence = sort_entity_to_zone("light.wohnzimmer_decke", "Wohnzimmer Decke")
"""
from __future__ import annotations

import re
from typing import Any

# ── Zone Keyword Map ────────────────────────────────────────────────────────────
# Each entry: (zone_id, entity_id_keywords, entity_name_keywords)
# See original file for full keyword lists (ported from HA)

ZONE_KEYWORD_MAP: list[tuple[str, list[str], list[str]]] = [
    (
        "living",
        [
            "wohnen", "wohnzimmer", "livingroom", "living_room",
            "wohnraum", "couch", "sofa", "tv_wohn", "tv_wohnzimmer",
            "esstisch", "terrasse_innen",
        ],
        [
            "wohnen", "wohnzimmer", "living", "couch", "sofa",
            "wohnraum", "tv-wohnzimmer", "tv wohnzimmer", "fernseher",
            "esstisch", "wohnzimmerlampe", "wohnzimmerlicht",
        ],
    ),
    (
        "sleeping",
        [
            "schlafzimmer", "schlafen", "bedroom", "bed_room",
            "bett", "nachttisch", "nachttischlampe",
            "schlafz",
        ],
        [
            "schlafzimmer", "schlafen", "schlaf", "bedroom",
            "bett", "nachttisch", "nachttischlampe",
            "schlafzimmerlampe", "schlafzimmerlicht",
        ],
    ),
    (
        "kitchen",
        [
            "kueche", "küche", "kitchen", "kochen", "herd",
            "ofen", "kochfeld", "abzug", "geschirrspueler",
            "kuehlschrank", "kühlschrank", "spuele", "spüle",
            "esszimmer", "fruehstück", "frühstück",
        ],
        [
            "küche", "kueche", "kitchen", "kochen", "herd",
            "ofen", "kochfeld", "abzug", "geschirrspüler",
            "kühlschrank", "kuehlschrank", "spüle", "spuele",
            "esszimmer", "frühstück", "fruehstück",
            "küchenlicht", "kuechenlicht", "kochstelle",
        ],
    ),
    (
        "bathing",
        [
            "badezimmer", "bathroom", "bad", "dusche", "duschen",
            "wc", "toilette", "waschbecken", "badewanne",
            "handtuchheizung",
        ],
        [
            "badezimmer", "bathroom", "bad", "dusche", "duschen",
            "wc", "toilette", "waschbecken", "badewanne",
            "handtuchheizung", "badezimmerlampe", "badlicht",
            "duschlicht",
        ],
    ),
    (
        "office",
        [
            "büro", "buro", "office", "arbeit", "homeoffice",
            "arbeitszimmer", "studie", "computer", "pc_raum",
        ],
        [
            "büro", "buro", "office", "arbeit", "homeoffice",
            "arbeitszimmer", "studie", "computer", "arbeitszimmerlampe",
        ],
    ),
    (
        "hallway",
        [
            "gang", "hallway", "flur", "flurbereich", "diele",
            "treppenhaus", "eingang", "eingangsbereich", "windfang",
            "flur_lampe", "flurlicht",
        ],
        [
            "gang", "hallway", "flur", "flurbereich", "diele",
            "treppenhaus", "eingang", "eingangsbereich", "windfang",
        ],
    ),
    (
        "room_mira",
        [
            "mira", "kinderzimmer_mira", "zimmer_mira",
            "mira_room", "miras_zimmer",
        ],
        [
            "mira", "kinderzimmer mira", "zimmer mira",
            "mira's room", "miras zimmer",
        ],
    ),
    (
        "room_paul",
        [
            "paul", "kinderzimmer_paul", "zimmer_paul",
            "paul_room", "pauls_zimmer",
        ],
        [
            "paul", "kinderzimmer paul", "zimmer paul",
            "paul's room", "pauls zimmer",
        ],
    ),
    (
        "terrace",
        [
            "terrass", "terrace", "balkon", "loggia", "dachterrass",
            "terrasse", "balkon", "patio", "terrassenlicht",
        ],
        [
            "terrass", "terrace", "balkon", "loggia", "dachterrass",
            "terrasse", "balkon", "patio", "terrassenlicht",
        ],
    ),
    (
        "outside",
        [
            "aussen", "außen", "garten", "garden", "hof", "vorgarten",
            "garage", "carport", "abstell", "outdoor", "teich",
            "pool", "markise", "haustor", "einfahrt", "tor",
            "gartenlicht", "garagenlicht",
        ],
        [
            "aussen", "außen", "garten", "garden", "hof", "vorgarten",
            "garage", "carport", "abstell", "outdoor", "teich",
            "pool", "markise", "haustor", "einfahrt", "tor",
            "gartenlicht", "garagenlicht",
        ],
    ),
    (
        "utility",
        [
            "keller", "basement", "abstellraum", "speicher",
            "attic", "dachboden", "waschkeller", "technik",
            "utility_room", "heizungsraum",
        ],
        [
            "keller", "basement", "abstellraum", "speicher",
            "attic", "dachboden", "waschkeller", "technik",
            "utility", "heizungsraum", "kellerlicht", "kellerraum",
        ],
    ),
    (
        "multi",
        [
            "kinderzimmer", "kinder", "kids", "kidsroom",
            "spielzimmer", "playroom", "multifunktion",
            "gaestezimmer", "gästezimmer",
            "musikzimmer", "fitness", "fitnessraum",
        ],
        [
            "kinderzimmer", "kinder", "kids", "kidsroom",
            "spielzimmer", "playroom", "multifunktion",
            "gaestezimmer", "gästezimmer",
            "musikzimmer", "fitness", "fitnessraum",
        ],
    ),
]

# ── Domain Fallback Map ─────────────────────────────────────────────────────────
# (domain, fallback_zone, confidence_boost) — only used when no keyword matched

DOMAIN_ZONE_FALLBACK: list[tuple[str, str, float]] = [
    ("cover", "living", 0.15),
    ("scene", "living", 0.15),
    ("audio", "living", 0.20),
    ("lock", "outside", 0.30),
    ("vacuum", "utility", 0.20),
    ("humidifier", "bathing", 0.25),
    ("dehumidifier", "bathing", 0.25),
    ("sensor", "transit", 0.10),
    ("plant", "outside", 0.25),
]

# ── Constants ────────────────────────────────────────────────────────────────────

UNSORTED_ZONE: str = "ungeordnet"
CONFIDENCE_THRESHOLD: float = 0.5


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _extract_domain(entity_id: str) -> str:
    """Extract domain from entity_id (e.g. 'light.wohnzimmer_decke' → 'light')."""
    if not entity_id or "." not in entity_id:
        return ""
    return entity_id.split(".", 1)[0].lower()


def _is_token_match(keyword: str, text: str) -> bool:
    """Check if keyword appears as a full token in text.

    Token = substring delimited by '.' or '_'.
    e.g. 'schlafzimmer' matches in 'schlafzimmer_decke' and 'light.schlafzimmer'.
    """
    parts = re.split(r"[._]", text)
    return keyword in parts


def _keyword_score(
    entity_id_lower: str,
    entity_name_lower: str,
    id_keywords: list[str],
    name_keywords: list[str],
) -> float:
    """Compute keyword-based confidence score (0.0 – 1.0).

    Scoring:
      +0.5  exact token match in entity_id
      +0.3  partial substring match in entity_id
      +0.3  exact match in entity_name
      +0.1  partial substring match in entity_name
    """
    score = 0.0

    # entity_id exact token (strongest signal)
    for kw in id_keywords:
        if _is_token_match(kw, entity_id_lower):
            score = max(score, 0.5)
            break

    # entity_id partial (weaker)
    if score < 0.5:
        for kw in id_keywords:
            if kw in entity_id_lower:
                score = max(score, 0.3)
                break

    # entity_name exact (moderate)
    for kw in name_keywords:
        if kw == entity_name_lower.strip():
            score = max(score, 0.3)
            break

    # entity_name partial (weakest)
    if score < 0.3:
        for kw in name_keywords:
            if kw in entity_name_lower:
                score = max(score, 0.1)
                break

    return score


# ── Main API ─────────────────────────────────────────────────────────────────────

def sort_entity_to_zone(
    entity_id: str,
    entity_name: str,
    entity_state: Any = None,
) -> tuple[str, float]:
    """Sort a HomeAssistant entity into the best-matching Habitus zone.

    Args:
        entity_id:    HA entity_id (e.g. "light.wohnzimmer_decke")
        entity_name:  Friendly name (e.g. "Wohnzimmer Decke")
        entity_state: Current state — reserved for future logic; not used for sorting

    Returns:
        (zone_id, confidence) — zone_id is "ungeordnet" when confidence < 0.5

    Examples:
        >>> sort_entity_to_zone("light.wohnzimmer_decke", "Wohnzimmer Decke")
        ('living', 0.8)

        >>> sort_entity_to_zone("sensor.unknown_temp", "Temperature Sensor")
        ('ungeordnet', 0.1)
    """
    if not entity_id:
        return (UNSORTED_ZONE, 0.0)

    entity_id_lower = entity_id.lower()
    entity_name_lower = entity_name.lower() if entity_name else ""

    best_zone: str | None = None
    best_score: float = 0.0

    # 1. Keyword matching
    for zone_id, id_keywords, name_keywords in ZONE_KEYWORD_MAP:
        kw_score = _keyword_score(
            entity_id_lower, entity_name_lower, id_keywords, name_keywords
        )
        if kw_score > best_score:
            best_score = kw_score
            best_zone = zone_id

    # 2. Domain fallback (only if no keyword hit)
    if best_zone is None or best_score < 0.5:
        entity_domain = _extract_domain(entity_id_lower)
        for fallback_domain, fallback_zone, boost in DOMAIN_ZONE_FALLBACK:
            if entity_domain == fallback_domain:
                if best_score < boost:
                    best_score = boost
                    best_zone = fallback_zone
                break

    # 3. Confidence threshold
    if best_score < CONFIDENCE_THRESHOLD or best_zone is None:
        return (UNSORTED_ZONE, round(best_score, 2))

    return (best_zone, round(best_score, 2))


def sort_entities_batch(
    entities: list[dict[str, Any]],
) -> list[tuple[str, float]]:
    """Sort a batch of entities.

    Args:
        entities: List of dicts with keys: entity_id, entity_name, entity_state (optional)

    Returns:
        List of (zone_id, confidence) tuples — same order as input
    """
    return [
        sort_entity_to_zone(
            entity.get("entity_id", ""),
            entity.get("entity_name", ""),
            entity.get("entity_state"),
        )
        for entity in entities
    ]


__all__ = [
    "sort_entity_to_zone",
    "sort_entities_batch",
    "UNSORTED_ZONE",
    "CONFIDENCE_THRESHOLD",
]
