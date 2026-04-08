"""
Habitus module - Pattern discovery and automation suggestion mining.

The habitus module analyzes temporal sequences in the brain graph to discover
A→B patterns that could become user automations. It implements:

- Temporal sequence analysis with configurable delta-time windows
- Statistical evidence calculation (support/confidence/lift)  
- Debounce logic to prevent noise
- Integration with Candidate storage for governance

Privacy: All analysis remains local, no external transmission.
"""

from .miner import HabitusMiner, PatternEvidence
from .service import HabitusService

__all__ = ["HabitusMiner", "PatternEvidence", "HabitusService"]