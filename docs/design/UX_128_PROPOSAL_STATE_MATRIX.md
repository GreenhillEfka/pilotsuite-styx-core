# UX-128: Proposal-State-Matrix

**Status:** Ready (2026-04-05)
**Owner:** DesignClaw
**Basis:** R4-Deferred-States (follow_up_open, follow_up_terminal, resume_conflict)

## State-Matrix

| State | Primary CTA | Secondary CTA | Terminal |
|-------|-------------|---------------|----------|
| `proposal.follow_up_open` | Weiterführen | Historie | Nein |
| `proposal.follow_up_terminal` | — | Historie ansehen | Ja |
| `proposal.resume_conflict` | — | Neuen Kontext | Ja |
| `action_closure.resume_conflict` | — | Neuen Kontext | Ja |

## Priority Rule

1. resume_conflict
2. clarification
3. proposal_*
4. action_closure_*
5. neutral
6. error

## Next: Implementation

- Core: State-Matrix in ModuleRegistry
- HA: Projection als ProposalCard
- Design: Handoff done

