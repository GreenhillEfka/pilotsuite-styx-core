"""
Habitus module - Pattern discovery and automation suggestion mining.

The habitus module analyzes temporal sequences in the brain graph to discover
A→B patterns that could become user automations. It implements:

- Temporal sequence analysis with configurable delta-time windows
- Statistical evidence calculation (support/confidence/lift)  
- Debounce logic to prevent noise
- Integration with Candidate storage for governance

Privacy: All analysis remains local, no external transmission.

Runtime bridge:
- extends this subpackage path back to the repo-level `copilot_core/habitus`
- keeps shared modules like `habitus_storage` importable from runtime-only
  contexts
"""

from __future__ import annotations

from pathlib import Path
from pkgutil import extend_path


__path__ = extend_path(__path__, __name__)  # type: ignore[name-defined]

_pkg_dir = Path(__file__).resolve().parent
_repo_bridge_dir = _pkg_dir.parents[6] / "copilot_core" / "habitus"
_repo_bridge_path = str(_repo_bridge_dir)
if _repo_bridge_dir.is_dir() and _repo_bridge_path not in __path__:
    __path__.append(_repo_bridge_path)

from .miner import HabitusMiner, PatternEvidence
from .service import HabitusService

__all__ = ["HabitusMiner", "PatternEvidence", "HabitusService"]
