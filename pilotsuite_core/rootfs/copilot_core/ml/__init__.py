"""ML package bridge with lazy exports.

The repo contains a lightweight top-level ML package plus additional runtime ML
modules under ``copilot_core/rootfs/usr/src/app/copilot_core/ml``. Importing the
package itself must stay cheap and must not eagerly import optional heavy
forecast dependencies, because API blueprints only need selected submodules to
resolve gracefully.
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from pkgutil import extend_path
from typing import Any, Dict, Tuple


__path__ = extend_path(__path__, __name__)  # type: ignore[name-defined]

_pkg_dir = Path(__file__).resolve().parent
_runtime_pkg_dir = _pkg_dir.parent / "rootfs" / "usr" / "src" / "app" / "copilot_core" / "ml"
_runtime_pkg_path = str(_runtime_pkg_dir)

if _runtime_pkg_dir.is_dir() and _runtime_pkg_path not in __path__:
    __path__.append(_runtime_pkg_path)


_LAZY_EXPORTS: Dict[str, Tuple[str, str]] = {
    "LSTMForecastManager": (".lstm_forecast", "LSTMForecastManager"),
    "LSTMForecaster": (".lstm_forecast", "LSTMForecaster"),
    "forecast_temperature": (".lstm_forecast", "forecast_temperature"),
    "TransformerForecastManager": (".transformer_model", "TransformerForecastManager"),
    "TransformerForecaster": (".transformer_model", "TransformerForecaster"),
    "TrainingPipeline": (".training_pipeline", "TrainingPipeline"),
    "TrainingConfig": (".training_pipeline", "TrainingConfig"),
    "ExperimentTracker": (".training_pipeline", "ExperimentTracker"),
}


__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = target
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
