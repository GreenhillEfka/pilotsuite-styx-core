# Predictive Automation — Pattern Learning & Prediction

## Overview

This module provides ML-based pattern learning and predictive automation for PilotSuite Styx Core.

### Features

- **Pattern Learning**: Automatically learns usage patterns from Home Assistant events
  - Time-based patterns (e.g., lights on in the morning)
  - Weather-based patterns (e.g., blinds down when sunny)
  - Device-specific patterns (lights, temperature, covers)
  
- **Predictions**: Predicts next likely actions based on learned patterns
  - Confidence scoring for each prediction
  - Natural language suggestions for user confirmation
  - Context-aware (time, weather, temperature)

- **API Endpoints**: REST API for integration
  - `GET /api/v1/predictive/patterns` — Get learned patterns
  - `GET /api/v1/predictive/next` — Get next predicted action
  - `POST /api/v1/predictive/confirm` — Confirm a prediction
  - `POST /api/v1/predictive/reject` — Reject a prediction
  - `POST /api/v1/predictive/observe` — Log observation for learning
  - `GET /api/v1/predictive/stats` — Get statistics

## Module Structure

```
copilot_core/automation/
├── __init__.py              # Module initialization
├── pattern_learner.py       # PatternLearner class
├── predictor.py             # PredictiveAutomationEngine class
└── README.md                # This file

copilot_core/api/v1/
└── predictive.py            # API endpoints

tests/
└── test_predictive_automation.py  # Comprehensive tests
```

## Usage

### Pattern Learning

```python
from copilot_core.automation.pattern_learner import PatternLearner

# Initialize
learner = PatternLearner(data_dir="/data/patterns")

# Log observations
learner.observe(
    entity_id="light.living_room",
    action="turn_on",
    timestamp=datetime.now(),
    context={
        "weather_condition": "sunny",
        "temperature": 22.5
    }
)

# Get learned patterns
patterns = learner.get_patterns(min_confidence=0.5)
```

### Predictions

```python
from copilot_core.automation.predictor import PredictiveAutomationEngine, PredictionRequest

# Initialize with pattern learner
predictor = PredictiveAutomationEngine(
    pattern_learner=learner,
    min_confidence=0.5
)

# Get next prediction
prediction = predictor.predict_next(PredictionRequest(
    current_time=datetime.now(),
    weather_condition="sunny"
))

if prediction:
    print(f"Suggestion: {prediction.suggestion_text}")
    print(f"Confidence: {prediction.confidence}")
```

### API Usage

```bash
# Get patterns
curl -H "X-Auth-Token: YOUR_TOKEN" \
  http://localhost:8123/api/v1/predictive/patterns

# Get next prediction
curl -H "X-Auth-Token: YOUR_TOKEN" \
  "http://localhost:8123/api/v1/predictive/next?weather=sunny"

# Log observation
curl -X POST -H "X-Auth-Token: YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "light.living_room", "action": "turn_on"}' \
  http://localhost:8123/api/v1/predictive/observe

# Confirm prediction
curl -X POST -H "X-Auth-Token: YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prediction_id": "pred_000001", "action_performed": true}' \
  http://localhost:8123/api/v1/predictive/confirm
```

## Pattern Types

### Time-Based Patterns
Learned from repeated actions at similar times:
- Morning routines (lights on, blinds up)
- Evening routines (lights off, thermostat down)
- Weekday vs. weekend patterns

### Weather-Based Patterns
Learned from actions correlated with weather conditions:
- Sunny → Close blinds, turn off lights
- Cloudy/Rainy → Open blinds, turn on lights
- Temperature-based HVAC adjustments

## Confidence Scoring

Confidence is calculated based on:
- **Frequency**: Number of observations (logarithmic scale)
- **Recency**: How recent the last observation was
- **Consistency**: Regularity of the pattern over time

Formula:
```
confidence = 0.4 * frequency_factor + 
             0.3 * recency_factor + 
             0.3 * consistency_factor
```

## Testing

Run tests with:
```bash
cd copilot_core/rootfs/usr/src/app
pytest -q tests/test_predictive_automation.py
```

28 tests covering:
- Pattern learning and persistence
- Confidence calculation
- Time-based predictions
- Weather-based predictions
- API endpoints

## Version

v1.0.0 — Initial release

## Author

Created for PilotSuite Styx Core by @cowdya
