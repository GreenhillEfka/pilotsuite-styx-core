"""
Proposal Engine - Pattern-based Automation Suggestions

Generates automation proposals from sensor/media/presence patterns.
Input: zone_id, sensor_data, patterns
Output: proposed_automations[], confidence_score, evidence

Pydantic models + OpenAPI schema definitions.
"""

from __future__ import annotations

from datetime import datetime, time
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator
from pydantic.fields import FieldInfo


# =============================================================================
# Enums & Constants
# =============================================================================


class SensorType(str, Enum):
    """Supported sensor types."""

    MOTION = "motion"
    CONTACT = "contact"  # door/window
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    LIGHT = "light"
    POWER = "power"
    PRESENCE = "presence"  # radar/mmWave
    MEDIA = "media"  # TV/music playback
    AMBIENT = "ambient"  # combined environmental


class PatternType(str, Enum):
    """Pattern categories for matching."""

    TEMPORAL = "temporal"  # time-based patterns
    SEQUENTIAL = "sequential"  # event sequences
    CO_OCCURRENCE = "co_occurrence"  # simultaneous events
    THRESHOLD = "threshold"  # value thresholds
    FREQUENCY = "frequency"  # occurrence frequency
    ABSENCE = "absence"  # lack of expected activity


class AutomationActionType(str, Enum):
    """Types of automation actions."""

    LIGHT_ON = "light_on"
    LIGHT_OFF = "light_off"
    LIGHT_DIM = "light_dim"
    CLIMATE_SET = "climate_set"
    MEDIA_PLAY = "media_play"
    MEDIA_PAUSE = "media_pause"
    SCENE_ACTIVATE = "scene_activate"
    NOTIFY = "notify"
    LOCK = "lock"
    UNLOCK = "unlock"


class ConfidenceLevel(str, Enum):
    """Confidence classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


# =============================================================================
# Input Models
# =============================================================================


class SensorReading(BaseModel):
    """Single sensor reading."""

    sensor_id: str = Field(..., description="Unique sensor identifier")
    sensor_type: SensorType = Field(..., description="Type of sensor")
    value: float | bool | str = Field(..., description="Sensor value")
    unit: str | None = Field(None, description="Unit of measurement")
    timestamp: datetime = Field(..., description="Reading timestamp")
    zone_id: str | None = Field(None, description="Associated zone")

    class Config:
        json_schema_extra = {
            "example": {
                "sensor_id": "motion-living-01",
                "sensor_type": "motion",
                "value": True,
                "unit": None,
                "timestamp": "2024-01-15T18:30:00Z",
                "zone_id": "living-room",
            }
        }


class SensorData(BaseModel):
    """Collection of sensor readings."""

    readings: list[SensorReading] = Field(
        ..., min_length=1, description="List of sensor readings"
    )
    zone_id: str = Field(..., description="Primary zone identifier")
    captured_at: datetime = Field(..., description="Data capture timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "readings": [
                    {
                        "sensor_id": "motion-living-01",
                        "sensor_type": "motion",
                        "value": True,
                        "timestamp": "2024-01-15T18:30:00Z",
                        "zone_id": "living-room",
                    }
                ],
                "zone_id": "living-room",
                "captured_at": "2024-01-15T18:30:00Z",
            }
        }


class PatternDefinition(BaseModel):
    """Pattern definition for matching."""

    pattern_id: str = Field(..., description="Unique pattern identifier")
    pattern_type: PatternType = Field(..., description="Pattern category")
    name: str = Field(..., description="Human-readable pattern name")
    description: str = Field(..., description="Pattern description")
    conditions: dict[str, Any] = Field(
        ..., description="Pattern matching conditions"
    )
    priority: int = Field(1, ge=1, le=10, description="Pattern priority")
    active: bool = Field(True, description="Pattern active status")

    class Config:
        json_schema_extra = {
            "example": {
                "pattern_id": "evening-arrival",
                "pattern_type": "temporal",
                "name": "Evening Arrival",
                "description": "Motion detected between 17:00-22:00",
                "conditions": {
                    "sensor_type": "motion",
                    "time_start": "17:00",
                    "time_end": "22:00",
                    "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                },
                "priority": 5,
                "active": True,
            }
        }


class PatternsInput(BaseModel):
    """Collection of pattern definitions."""

    patterns: list[PatternDefinition] = Field(
        ..., min_length=1, description="List of patterns to match"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "patterns": [
                    {
                        "pattern_id": "evening-arrival",
                        "pattern_type": "temporal",
                        "name": "Evening Arrival",
                        "description": "Motion detected between 17:00-22:00",
                        "conditions": {
                            "sensor_type": "motion",
                            "time_start": "17:00",
                            "time_end": "22:00",
                        },
                        "priority": 5,
                        "active": True,
                    }
                ]
            }
        }


class ProposalRequest(BaseModel):
    """Request model for generating automation proposals."""

    zone_id: str = Field(..., description="Target zone identifier")
    sensor_data: SensorData = Field(..., description="Sensor data to analyze")
    patterns: PatternsInput = Field(..., description="Patterns to match against")
    max_proposals: int = Field(
        10, ge=1, le=50, description="Maximum proposals to return"
    )
    min_confidence: ConfidenceLevel = Field(
        ConfidenceLevel.LOW, description="Minimum confidence threshold"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "zone_id": "living-room",
                "sensor_data": {
                    "readings": [
                        {
                            "sensor_id": "motion-living-01",
                            "sensor_type": "motion",
                            "value": True,
                            "timestamp": "2024-01-15T18:30:00Z",
                            "zone_id": "living-room",
                        }
                    ],
                    "zone_id": "living-room",
                    "captured_at": "2024-01-15T18:30:00Z",
                },
                "patterns": {
                    "patterns": [
                        {
                            "pattern_id": "evening-arrival",
                            "pattern_type": "temporal",
                            "name": "Evening Arrival",
                            "description": "Motion detected between 17:00-22:00",
                            "conditions": {
                                "sensor_type": "motion",
                                "time_start": "17:00",
                                "time_end": "22:00",
                            },
                            "priority": 5,
                            "active": True,
                        }
                    ]
                },
                "max_proposals": 10,
                "min_confidence": "low",
            }
        }


# =============================================================================
# Output Models
# =============================================================================


class EvidenceItem(BaseModel):
    """Single piece of evidence supporting a proposal."""

    evidence_type: Literal["sensor_match", "pattern_match", "historical", "contextual"] = Field(
        ..., description="Type of evidence"
    )
    source_id: str = Field(..., description="Source identifier (sensor/pattern ID)")
    description: str = Field(..., description="Evidence description")
    weight: float = Field(
        ..., ge=0.0, le=1.0, description="Evidence weight in confidence calculation"
    )
    timestamp: datetime | None = Field(None, description="Evidence timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "evidence_type": "pattern_match",
                "source_id": "evening-arrival",
                "description": "Motion at 18:30 matches evening arrival pattern (17:00-22:00)",
                "weight": 0.7,
                "timestamp": "2024-01-15T18:30:00Z",
            }
        }


class ProposedAutomation(BaseModel):
    """Single automation proposal."""

    proposal_id: str = Field(..., description="Unique proposal identifier")
    automation_type: AutomationActionType = Field(..., description="Action type")
    target_device_id: str | None = Field(None, description="Target device identifier")
    target_zone_id: str = Field(..., description="Target zone")
    action_parameters: dict[str, Any] = Field(
        ..., description="Action-specific parameters"
    )
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score (0-1)"
    )
    confidence_level: ConfidenceLevel = Field(
        ..., description="Confidence classification"
    )
    matched_patterns: list[str] = Field(
        ..., description="Pattern IDs that matched"
    )
    evidence: list[EvidenceItem] = Field(
        ..., min_length=1, description="Supporting evidence"
    )
    rationale: str = Field(..., description="Human-readable rationale")
    suggested_trigger: str | None = Field(None, description="Suggested trigger condition")
    expires_at: datetime | None = Field(None, description="Proposal expiration")

    @field_validator("confidence_level")
    @classmethod
    def derive_confidence_level(cls, v: ConfidenceLevel, info: Any) -> ConfidenceLevel:
        """Derive confidence level from score if not provided."""
        # This validator runs after model validation
        # The actual derivation happens in the engine
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "proposal_id": "prop-001",
                "automation_type": "light_on",
                "target_device_id": "light-living-main",
                "target_zone_id": "living-room",
                "action_parameters": {"brightness": 80, "color_temperature": 3000},
                "confidence_score": 0.85,
                "confidence_level": "high",
                "matched_patterns": ["evening-arrival"],
                "evidence": [
                    {
                        "evidence_type": "pattern_match",
                        "source_id": "evening-arrival",
                        "description": "Motion at 18:30 matches evening arrival pattern",
                        "weight": 0.7,
                        "timestamp": "2024-01-15T18:30:00Z",
                    }
                ],
                "rationale": "Evening motion detected; typical time for lighting activation",
                "suggested_trigger": "motion_detected AND time_between_17_22",
                "expires_at": "2024-01-15T23:59:59Z",
            }
        }


class ProposalResponse(BaseModel):
    """Response containing automation proposals."""

    zone_id: str = Field(..., description="Zone identifier")
    analyzed_at: datetime = Field(..., description="Analysis timestamp")
    total_patterns_evaluated: int = Field(..., description="Patterns evaluated")
    proposals: list[ProposedAutomation] = Field(
        ..., description="List of automation proposals"
    )
    overall_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Overall confidence across proposals"
    )
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")

    class Config:
        json_schema_extra = {
            "example": {
                "zone_id": "living-room",
                "analyzed_at": "2024-01-15T18:30:05Z",
                "total_patterns_evaluated": 5,
                "proposals": [
                    {
                        "proposal_id": "prop-001",
                        "automation_type": "light_on",
                        "target_device_id": "light-living-main",
                        "target_zone_id": "living-room",
                        "action_parameters": {"brightness": 80},
                        "confidence_score": 0.85,
                        "confidence_level": "high",
                        "matched_patterns": ["evening-arrival"],
                        "evidence": [
                            {
                                "evidence_type": "pattern_match",
                                "source_id": "evening-arrival",
                                "description": "Motion at 18:30 matches evening arrival pattern",
                                "weight": 0.7,
                            }
                        ],
                        "rationale": "Evening motion detected; typical time for lighting activation",
                    }
                ],
                "overall_confidence": 0.82,
                "processing_time_ms": 45,
            }
        }


# =============================================================================
# OpenAPI Schema
# =============================================================================


OPENAPI_SCHEMA = {
    "paths": {
        "/api/v1/proposals": {
            "post": {
                "summary": "Generate Automation Proposals",
                "description": "Analyzes sensor data against pattern definitions to generate automation proposals.",
                "operationId": "generateProposals",
                "tags": ["Proposals"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ProposalRequest"}
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Successful proposal generation",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ProposalResponse"
                                }
                            }
                        },
                    },
                    "400": {
                        "description": "Invalid request",
                        "content": {
                            "application/json": {
                                "example": {"error": "Invalid zone_id", "details": "..."}
                            }
                        },
                    },
                    "422": {
                        "description": "Validation error",
                        "content": {
                            "application/json": {
                                "example": {"detail": [{"loc": "...", "msg": "..."}]}
                            }
                        },
                    },
                },
            }
        }
    },
    "components": {
        "schemas": {
            "ProposalRequest": ProposalRequest.model_json_schema(),
            "ProposalResponse": ProposalResponse.model_json_schema(),
            "SensorData": SensorData.model_json_schema(),
            "SensorReading": SensorReading.model_json_schema(),
            "PatternsInput": PatternsInput.model_json_schema(),
            "PatternDefinition": PatternDefinition.model_json_schema(),
            "ProposedAutomation": ProposedAutomation.model_json_schema(),
            "EvidenceItem": EvidenceItem.model_json_schema(),
            "SensorType": SensorType.model_json_schema(),
            "PatternType": PatternType.model_json_schema(),
            "AutomationActionType": AutomationActionType.model_json_schema(),
            "ConfidenceLevel": ConfidenceLevel.model_json_schema(),
        }
    },
}


# =============================================================================
# Pattern Matching Engine
# =============================================================================


class ProposalEngine:
    """
    Pattern-based automation proposal engine.

    Matches sensor data against pattern definitions and generates
    automation proposals with confidence scores and evidence.
    """

    def __init__(self) -> None:
        self._confidence_thresholds: dict[ConfidenceLevel, float] = {
            ConfidenceLevel.LOW: 0.3,
            ConfidenceLevel.MEDIUM: 0.5,
            ConfidenceLevel.HIGH: 0.7,
            ConfidenceLevel.VERY_HIGH: 0.9,
        }

    def _parse_time(self, time_str: str) -> time:
        """Parse time string (HH:MM) to time object."""
        parts = time_str.split(":")
        return time(int(parts[0]), int(parts[1]))

    def _match_temporal_pattern(
        self, reading: SensorReading, pattern: PatternDefinition
    ) -> tuple[bool, float, list[EvidenceItem]]:
        """Match temporal pattern (time-based conditions)."""
        conditions = pattern.conditions
        evidence: list[EvidenceItem] = []

        # Check sensor type match
        if conditions.get("sensor_type") and reading.sensor_type.value != conditions["sensor_type"]:
            return False, 0.0, []

        # Check time window
        if "time_start" in conditions and "time_end" in conditions:
            start = self._parse_time(conditions["time_start"])
            end = self._parse_time(conditions["time_end"])
            reading_time = reading.timestamp.time()

            if not (start <= reading_time <= end):
                return False, 0.0, []

            evidence.append(
                EvidenceItem(
                    evidence_type="pattern_match",
                    source_id=pattern.pattern_id,
                    description=f"Reading at {reading_time} matches time window {start}-{end}",
                    weight=0.5,
                    timestamp=reading.timestamp,
                )
            )

        # Check days of week
        if "days" in conditions:
            day_name = reading.timestamp.strftime("%A").lower()
            if day_name not in [d.lower() for d in conditions["days"]]:
                return False, 0.0, []

            evidence.append(
                EvidenceItem(
                    evidence_type="contextual",
                    source_id=pattern.pattern_id,
                    description=f"Day {day_name} matches pattern days",
                    weight=0.3,
                    timestamp=reading.timestamp,
                )
            )

        # Calculate confidence based on matches
        confidence = sum(e.weight for e in evidence)
        return True, min(confidence, 1.0), evidence

    def _match_threshold_pattern(
        self, reading: SensorReading, pattern: PatternDefinition
    ) -> tuple[bool, float, list[EvidenceItem]]:
        """Match threshold pattern (value-based conditions)."""
        conditions = pattern.conditions
        evidence: list[EvidenceItem] = []

        if not isinstance(reading.value, (int, float)):
            return False, 0.0, []

        # Check min threshold
        if "min_value" in conditions:
            if reading.value < conditions["min_value"]:
                return False, 0.0, []
            evidence.append(
                EvidenceItem(
                    evidence_type="sensor_match",
                    source_id=reading.sensor_id,
                    description=f"Value {reading.value} >= threshold {conditions['min_value']}",
                    weight=0.4,
                    timestamp=reading.timestamp,
                )
            )

        # Check max threshold
        if "max_value" in conditions:
            if reading.value > conditions["max_value"]:
                return False, 0.0, []
            evidence.append(
                EvidenceItem(
                    evidence_type="sensor_match",
                    source_id=reading.sensor_id,
                    description=f"Value {reading.value} <= threshold {conditions['max_value']}",
                    weight=0.4,
                    timestamp=reading.timestamp,
                )
            )

        confidence = sum(e.weight for e in evidence)
        return len(evidence) > 0, min(confidence, 1.0), evidence

    def _match_pattern(
        self, reading: SensorReading, pattern: PatternDefinition
    ) -> tuple[bool, float, list[EvidenceItem]]:
        """Match a single reading against a pattern."""
        if not pattern.active:
            return False, 0.0, []

        match_funcs = {
            PatternType.TEMPORAL: self._match_temporal_pattern,
            PatternType.THRESHOLD: self._match_threshold_pattern,
        }

        matcher = match_funcs.get(pattern.pattern_type)
        if matcher:
            return matcher(reading, pattern)

        # Default: check sensor type match only
        if conditions := pattern.conditions.get("sensor_type"):
            if reading.sensor_type.value == conditions:
                return True, 0.5, [
                    EvidenceItem(
                        evidence_type="sensor_match",
                        source_id=pattern.pattern_id,
                        description=f"Sensor type {reading.sensor_type.value} matches pattern",
                        weight=0.5,
                        timestamp=reading.timestamp,
                    )
                ]

        return False, 0.0, []

    def _derive_automation_from_pattern(
        self,
        pattern: PatternDefinition,
        reading: SensorReading,
        confidence: float,
        evidence: list[EvidenceItem],
    ) -> ProposedAutomation | None:
        """Derive automation proposal from matched pattern."""
        # Map pattern types to suggested actions
        action_map: dict[PatternType, AutomationActionType] = {
            PatternType.TEMPORAL: AutomationActionType.SCENE_ACTIVATE,
            PatternType.THRESHOLD: AutomationActionType.CLIMATE_SET,
            PatternType.SEQUENTIAL: AutomationActionType.LIGHT_ON,
            PatternType.CO_OCCURRENCE: AutomationActionType.MEDIA_PLAY,
            PatternType.FREQUENCY: AutomationActionType.NOTIFY,
            PatternType.ABSENCE: AutomationActionType.LIGHT_OFF,
        }

        automation_type = action_map.get(pattern.pattern_type)
        if not automation_type:
            return None

        # Derive confidence level
        confidence_level = ConfidenceLevel.LOW
        for level, threshold in self._confidence_thresholds.items():
            if confidence >= threshold:
                confidence_level = level

        # Build action parameters based on pattern
        action_params: dict[str, Any] = {}
        if pattern.pattern_type == PatternType.THRESHOLD:
            if "target_value" in pattern.conditions:
                action_params["target_value"] = pattern.conditions["target_value"]

        rationale = f"Pattern '{pattern.name}' matched with {confidence:.0%} confidence. "
        rationale += pattern.description

        return ProposedAutomation(
            proposal_id=f"prop-{pattern.pattern_id}-{reading.timestamp.timestamp():.0f}",
            automation_type=automation_type,
            target_device_id=None,  # To be resolved by caller
            target_zone_id=reading.zone_id or "unknown",
            action_parameters=action_params,
            confidence_score=confidence,
            confidence_level=confidence_level,
            matched_patterns=[pattern.pattern_id],
            evidence=evidence,
            rationale=rationale,
            suggested_trigger=f"{pattern.pattern_type.value}_match",
        )

    def generate_proposals(
        self,
        zone_id: str,
        sensor_data: SensorData,
        patterns: PatternsInput,
        max_proposals: int = 10,
        min_confidence: ConfidenceLevel = ConfidenceLevel.LOW,
    ) -> ProposalResponse:
        """
        Generate automation proposals from sensor data and patterns.

        Args:
            zone_id: Target zone identifier
            sensor_data: Sensor readings to analyze
            patterns: Pattern definitions to match
            max_proposals: Maximum proposals to return
            min_confidence: Minimum confidence threshold

        Returns:
            ProposalResponse with matched automation proposals
        """
        import time as time_module

        start = time_module.time()

        proposals: list[ProposedAutomation] = []
        min_threshold = self._confidence_thresholds.get(min_confidence, 0.3)

        # Evaluate each reading against each pattern
        for reading in sensor_data.readings:
            for pattern in patterns.patterns:
                matched, confidence, evidence = self._match_pattern(reading, pattern)

                if not matched or confidence < min_threshold:
                    continue

                automation = self._derive_automation_from_pattern(
                    pattern, reading, confidence, evidence
                )
                if automation:
                    proposals.append(automation)

        # Sort by confidence and limit
        proposals.sort(key=lambda p: p.confidence_score, reverse=True)
        proposals = proposals[:max_proposals]

        # Calculate overall confidence
        overall_confidence = (
            sum(p.confidence_score for p in proposals) / len(proposals)
            if proposals else 0.0
        )

        processing_time = int((time_module.time() - start) * 1000)

        return ProposalResponse(
            zone_id=zone_id,
            analyzed_at=datetime.utcnow(),
            total_patterns_evaluated=len(patterns.patterns),
            proposals=proposals,
            overall_confidence=overall_confidence,
            processing_time_ms=processing_time,
        )


# =============================================================================
# Convenience Functions
# =============================================================================


def generate_proposals(
    zone_id: str,
    sensor_data: SensorData,
    patterns: PatternsInput,
    max_proposals: int = 10,
    min_confidence: ConfidenceLevel = ConfidenceLevel.LOW,
) -> ProposalResponse:
    """
    Convenience function to generate automation proposals.

    Args:
        zone_id: Target zone identifier
        sensor_data: Sensor readings to analyze
        patterns: Pattern definitions to match
        max_proposals: Maximum proposals to return
        min_confidence: Minimum confidence threshold

    Returns:
        ProposalResponse with matched automation proposals
    """
    engine = ProposalEngine()
    return engine.generate_proposals(
        zone_id, sensor_data, patterns, max_proposals, min_confidence
    )


# =============================================================================
# Example Usage
# =============================================================================


if __name__ == "__main__":
    # Example: Generate proposals for evening motion pattern
    from datetime import datetime, timezone

    sensor_data = SensorData(
        readings=[
            SensorReading(
                sensor_id="motion-living-01",
                sensor_type=SensorType.MOTION,
                value=True,
                timestamp=datetime(2024, 1, 15, 18, 30, 0, tzinfo=timezone.utc),
                zone_id="living-room",
            )
        ],
        zone_id="living-room",
        captured_at=datetime(2024, 1, 15, 18, 30, 0, tzinfo=timezone.utc),
    )

    patterns = PatternsInput(
        patterns=[
            PatternDefinition(
                pattern_id="evening-arrival",
                pattern_type=PatternType.TEMPORAL,
                name="Evening Arrival",
                description="Motion detected between 17:00-22:00",
                conditions={
                    "sensor_type": "motion",
                    "time_start": "17:00",
                    "time_end": "22:00",
                    "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                },
                priority=5,
                active=True,
            )
        ]
    )

    response = generate_proposals(
        zone_id="living-room",
        sensor_data=sensor_data,
        patterns=patterns,
        max_proposals=5,
        min_confidence=ConfidenceLevel.LOW,
    )

    print(f"Generated {len(response.proposals)} proposals")
    print(f"Overall confidence: {response.overall_confidence:.2f}")
    for proposal in response.proposals:
        print(f"  - {proposal.automation_type.value}: {proposal.confidence_score:.2f}")
