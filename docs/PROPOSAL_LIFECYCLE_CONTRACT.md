# Proposal Lifecycle Contract — Slice 7 (2026-03-25)

## Status: IN PROGRESS

## Goal

Unified Proposal Lifecycle: candidates → suggestions → proposals → acceptance → action intents — ONE surface.

## Lifecycle States

```
┌─────────────┐    mine     ┌─────────────┐    offer    ┌─────────────┐
│  PATTERN    │ ─────────► │  CANDIDATE  │ ─────────► │  OFFERED    │
│  (raw)      │            │  (pending)  │            │  (shown)    │
└─────────────┘            └─────────────┘            └──────┬──────┘
                                                           │
                              ┌────────────────────────────┼────────────────────────────┐
                              │                            │                            │
                              ▼                            ▼                            ▼
                       ┌─────────────┐             ┌─────────────┐             ┌─────────────┐
                       │  ACCEPTED   │             │  DISMISSED  │             │  DEFERRED   │
                       │  (user ok) │             │  (rejected)│             │  (snoozed) │
                       └──────┬──────┘            └─────────────┘             └──────┬──────┘
                              │                                                       │
                              ▼                                                       │
                       ┌─────────────┐                                               │
                       │  PROPOSAL   │ ◄─────────────────────────────────────────────┘
                       │  (actionable)│
                       └──────┬──────┘
                              │
                              ▼
                       ┌─────────────┐
                       │ ACTION INTENT│
                       │ (ready to exec)│
                       └──────┬──────┘
                              │
                              ▼
                       ┌─────────────┐
                       │  EXECUTED   │
                       └─────────────┘
```

## Components

| Component | File | Role |
|---|---|---|
| **Candidate Store** | `candidates/store.py` | Persist candidates with state |
| **Habitus Miner** | `habitus_miner/` | Discover patterns → candidates |
| **Suggestions API** | `api/v1/suggestions.py` | User-facing suggestion CRUD |
| **Proposal Store** | `candidates/store.py` (extended) | Accepted → proposals |

## Typed Models

```python
@dataclass
class CandidateV1:
    candidate_id: str
    pattern_id: str
    state: Literal["pending", "offered", "accepted", "dismissed", "deferred"]
    evidence: dict  # support, confidence, lift from miner
    created_at: datetime
    updated_at: datetime
    retry_after: Optional[datetime]  # for deferred
    metadata: dict

@dataclass
class ProposalV1:
    proposal_id: str
    candidate_id: str
    action_type: str  # "automation", "scene", "script"
    action_config: dict  # HA automation config
    explanation: str
    confidence: float
    created_at: datetime
    accepted_at: Optional[datetime]

@dataclass
class ActionIntentV1:
    intent_id: str
    proposal_id: str
    action: str  # "create_automation", "create_scene", etc.
    params: dict
    status: Literal["pending", "executing", "executed", "failed"]
    created_at: datetime
    executed_at: Optional[datetime]
    result: Optional[dict]
```

## API Endpoints

| Endpoint | Method | Role |
|---|---|---|
| `/api/v1/suggestions` | GET | List pending suggestions |
| `/api/v1/suggestions/repairs` | GET | List repair/improvement suggestions |
| `/api/v1/suggestions/accept` | POST | Accept suggestion → create proposal |
| `/api/v1/suggestions/reject` | POST | Reject suggestion → dismissed |
| `/api/v1/suggestions/snooze` | POST | Defer suggestion → deferred |
| `/api/v1/proposals` | GET | List accepted proposals |
| `/api/v1/proposals/{id}` | GET | Proposal detail |
| `/api/v1/proposals/{id}/execute` | POST | Execute proposal → action intent |

## Evidence Fields

Every candidate MUST include evidence:

```python
evidence: {
    "support": float,      # How often pattern observed (0.0-1.0)
    "confidence": float,   # Pattern confidence (0.0-1.0)
    "lift": float,        # Lift over baseline (1.0 = random)
    "occurrences": int,   # Number of times observed
    "first_seen": str,    # ISO timestamp
    "last_seen": str,     # ISO timestamp
    "zones": list[str],   # Affected zones
    "entities": list[str],# Affected HA entities
}
```

## Privacy

- All data stays local
- No external transmission
- JSON file storage for MVP
- User consent required for proposal execution

## Contract Owner

- **PilotClaw** — Candidate Store, Proposal Lifecycle, Action Intents
- **Stxy** — Suggestions API, User-facing proposal management
- **HomeClaw** — HA automation creation from action intents