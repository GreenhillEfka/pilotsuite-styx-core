# Symbiosis Architecture — Technical Deep Dive

## Overview

The Symbiosis Layer bridges Home Assistant entities with Core intelligence, enabling:
- **Bidirectional Sync:** HA ↔ Core real-time state synchronization
- **Rule-Based Automation:** Complex conditions with AND/OR logic
- **Predictive Analytics:** ML-based pattern detection from event history
- **Context Management:** Stateful transitions with history tracking

## Components

### 1. Rule Engine (`rule_engine.py`)
```python
- SymbioticRuleEngine: Evaluates rules with logical operators
- ContextManager: Manages zone context transitions
- Features: AND/OR logic, trigger counting, enable/disable
```

### 2. Event Bus (`event_bus_sync.py`)
```python
- EventBusSync: Bridges HA events to Core
- WebSocket Client: Real-time event streaming
- Conflict Resolution: Priority-based action blocking
```

### 3. Predictive Stack
```python
- PredictiveSymbiosisEngine: Pattern detection from history
- RuleOptimizer: Scoring + auto-disable low-performing rules
- LearningMemorySync: Persistent pattern storage
```

### 4. Live Symbiosis (`live_symbiosis.py`)
```python
- Continuous 5s sync loop
- Zone synchronization + event processing
- Auto-start on Core startup
```

## Data Flow

```
HA Event (Motion/Presence)
    ↓
WebSocket Client (real-time)
    ↓
Event Bus Sync
    ↓
Rule Engine (evaluate_zone)
    ↓
Action Execution
    ├── context_change → ContextManager.transition()
    ├── ha_service → HA Service Call
    └── device_command → Device Control
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/habitus/zones` | GET/POST | Zone management |
| `/api/v1/contexts/rooms` | GET/POST | Room contexts |
| `/api/v1/devices/links` | GET/POST | Device links |
| `/api/v1/entities/presence` | GET/POST | Presence entities |
| `/api/v1/intents` | GET/POST | Intent management |
| `/api/v1/actions` | GET/POST | Action execution |
| `/api/v1/states` | GET/POST | State bridges |
| `/api/v1/events` | GET/POST | Event bus |
| `/api/v1/memory` | GET/POST | Learning memory |
| `/api/v1/predictive` | GET/POST | Pattern detection |
| `/api/v1/optimizer` | GET/POST | Rule optimization |
| `/admin` | GET | SOTA Dashboard UI |

## Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Event Latency | <10ms | ~50ms |
| Rule Evaluation | <5ms | ~20ms |
| Sync Interval | 5s | 5s |
| Max Throughput | 1000 evt/s | TBD |

## Testing

- `test_symbiosis_engines.py`: Rule + Context tests
- `test_predictive_symbiosis.py`: Pattern + Optimizer tests
- `test_live_symbiosis.py`: End-to-end chain test
- `test_symbiosis_load.py`: Load testing (in progress)

---
*Generated: 2026-04-06*
