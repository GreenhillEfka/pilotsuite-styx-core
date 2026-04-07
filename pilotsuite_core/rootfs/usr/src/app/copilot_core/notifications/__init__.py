"""Notifications module for PilotSuite.

Der Package-Import bleibt bewusst leichtgewichtig. Konkrete Runtime-Komponenten
werden lazy geladen, damit fokussierte Imports wie
``copilot_core.notifications.engine`` nicht schon im Package-Init an optionalen
Adaptern oder Legacy-Aliases scheitern.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any, Dict, Tuple


_LAZY_EXPORTS: Dict[str, Tuple[str, str]] = {
    "NotificationEngine": (".engine", "NotificationEngine"),
    "Notification": (".engine", "Notification"),
    "NotificationPriority": (".engine", "NotificationPriority"),
    "Priority": (".engine", "NotificationPriority"),
    "NotificationStatus": (".engine", "NotificationStatus"),
    "NotificationChannel": (".engine", "NotificationChannel"),
    "NotificationTemplate": (".engine", "NotificationTemplate"),
    "UserPreferences": (".engine", "UserPreferences"),
    "create_notification_engine": (".engine", "create_notification_engine"),
    "HANotifyAdapter": (".ha_notify_adapter", "HANotifyAdapter"),
    "HADevice": (".ha_notify_adapter", "HADevice"),
    "get_ha_notify_adapter": (".ha_notify_adapter", "get_ha_notify_adapter"),
    "reset_ha_notify_adapter": (".ha_notify_adapter", "reset_ha_notify_adapter"),
    "PRIORITY_MAP": (".ha_notify_adapter", "PRIORITY_MAP"),
    "CATEGORY_MAP": (".ha_notify_adapter", "CATEGORY_MAP"),
    "SUPPORTED_NOTIFY_SERVICES": (".ha_notify_adapter", "SUPPORTED_NOTIFY_SERVICES"),
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
