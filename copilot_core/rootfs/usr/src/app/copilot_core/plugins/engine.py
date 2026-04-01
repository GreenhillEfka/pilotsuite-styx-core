"""Plugin Engine — contract-compatible runtime implementation.

Plugin system for PilotSuite Core extensibility.

This module currently has to satisfy two historical contract surfaces:
- older Slice-27 style tests (`plugins_dir`, `manifest.json`, ACTIVE status,
  manual hook registration helpers)
- newer Slice-44 style tests (`plugin_dirs`, `plugin.json`, ENABLED status,
  statistics/lifecycle helpers)

The implementation below keeps one runtime engine while providing explicit
compatibility shims for both surfaces.
"""
from __future__ import annotations

import importlib.util
import json
import logging
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


class PluginStatus(Enum):
    """Plugin status.

    Notes:
    - `ACTIVE` exists for the older contract surface.
    - `ENABLED` exists for the newer contract surface.
    - Both are treated as semantically enabled by engine helpers.
    """

    DISCOVERED = "discovered"
    LOADED = "loaded"
    ACTIVE = "active"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"
    UNLOADED = "unloaded"


class PluginHook(Enum):
    """Plugin hook types across both contract generations."""

    ON_STARTUP = "on_startup"
    ON_SHUTDOWN = "on_shutdown"
    ON_CONFIG_LOAD = "on_config_load"
    ON_EVENT = "on_event"
    ON_REQUEST = "on_request"
    ON_RESPONSE = "on_response"
    ON_ERROR = "on_error"
    CUSTOM = "custom"

    # Legacy aliases / older contract hooks
    ON_EVENT_RECEIVED = "on_event_received"
    ON_ZONE_CREATED = "on_zone_created"
    ON_HEALTH_CHECK = "on_health_check"


@dataclass
class PluginManifest:
    """Plugin manifest definition."""

    plugin_id: str
    name: str
    version: str
    description: str = ""
    author: str = ""
    homepage: Optional[str] = ""
    license: str = "MIT"
    min_core_version: str = "15.2.0"
    dependencies: List[str] = field(default_factory=list)
    hooks: List[str] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "homepage": self.homepage,
            "license": self.license,
            "min_core_version": self.min_core_version,
            "dependencies": list(self.dependencies),
            "hooks": list(self.hooks),
            "config_schema": dict(self.config_schema),
        }


@dataclass
class Plugin:
    """Loaded plugin instance."""

    plugin_id: str
    manifest: PluginManifest
    module: Any = None
    status: PluginStatus = PluginStatus.DISCOVERED
    config: Dict[str, Any] = field(default_factory=dict)
    path: Optional[str] = None
    loaded_at: Optional[str] = None
    enabled_at: Optional[str] = None
    error_message: Optional[str] = None
    hooks_registered: Dict[str, List[Callable]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "manifest": self.manifest.to_dict(),
            "status": self.status.value,
            "config": dict(self.config),
            "path": self.path,
            "loaded_at": self.loaded_at,
            "enabled_at": self.enabled_at,
            "error_message": self.error_message,
            "hooks_registered": list(self.hooks_registered.keys()),
        }


@dataclass
class HookRegistration:
    """Registered hook."""

    hook_id: str
    hook_type: PluginHook
    plugin_id: str
    handler: Callable
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hook_id": self.hook_id,
            "hook_type": self.hook_type.value,
            "plugin_id": self.plugin_id,
            "priority": self.priority,
        }


class DiscoveryResult(int):
    """Int-like discovery result with legacy collection semantics.

    - new tests compare it directly to an integer
    - old tests use len(...) and membership (`plugin_id in result`)
    """

    def __new__(cls, plugin_ids: Iterable[str]):
        plugin_ids = tuple(plugin_ids)
        obj = int.__new__(cls, len(plugin_ids))
        obj._plugin_ids = plugin_ids
        return obj

    def __len__(self) -> int:
        return int(self)

    def __contains__(self, item: object) -> bool:
        return item in self._plugin_ids

    def __iter__(self):
        return iter(self._plugin_ids)

    def keys(self):
        return self._plugin_ids


class PluginEngine:
    """Plugin management engine with legacy/current contract compatibility."""

    def __init__(
        self,
        plugin_dirs: Optional[List[str]] = None,
        *,
        plugins_dir: Optional[str] = None,
        core_version: str = "15.3.0",
    ):
        if plugins_dir is not None:
            normalized_dirs = [str(plugins_dir)]
        elif plugin_dirs is not None:
            normalized_dirs = [str(item) for item in plugin_dirs]
        else:
            normalized_dirs = ["plugins", "~/.pilotclaw/plugins"]

        self._plugins: Dict[str, Plugin] = {}
        self._hooks: Dict[str, List[HookRegistration]] = {}
        self._plugin_dirs: List[str] = normalized_dirs
        self._plugins_dir: Path = Path(normalized_dirs[0]).expanduser()
        self._core_version = core_version

        self._lifecycle_callbacks: Dict[str, List[Callable]] = {
            "on_load": [],
            "on_enable": [],
            "on_disable": [],
            "on_unload": [],
        }

    # ------------------------------------------------------------------
    # Compatibility helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _is_enabled_status(status: PluginStatus) -> bool:
        return status in (PluginStatus.ACTIVE, PluginStatus.ENABLED)

    @staticmethod
    def _serialize_status_for_api(status: PluginStatus) -> str:
        # Public engine APIs normalize ACTIVE -> enabled for the newer contract.
        if status == PluginStatus.ACTIVE:
            return PluginStatus.ENABLED.value
        return status.value

    @staticmethod
    def _parse_version(version: str) -> tuple[int, ...]:
        parts: List[int] = []
        for piece in str(version).split("."):
            digits = "".join(ch for ch in piece if ch.isdigit())
            parts.append(int(digits or 0))
        return tuple(parts)

    def _normalize_hook_key(self, hook_type: str | PluginHook) -> str:
        return hook_type.value if isinstance(hook_type, PluginHook) else str(hook_type)

    def _normalize_hook_enum(self, hook_type: str | PluginHook) -> PluginHook:
        if isinstance(hook_type, PluginHook):
            return hook_type
        for candidate in PluginHook:
            if candidate.value == hook_type:
                return candidate
        return PluginHook.CUSTOM

    def _plugin_to_api_dict(self, plugin: Plugin) -> Dict[str, Any]:
        payload = plugin.to_dict()
        payload["status"] = self._serialize_status_for_api(plugin.status)
        return payload

    # ------------------------------------------------------------------
    # Discovery / manifest loading
    # ------------------------------------------------------------------
    def discover_plugins(self) -> DiscoveryResult:
        """Discover plugins in configured directories.

        Supports both `plugin.json` and legacy `manifest.json` manifests.
        Discovery does not require `plugin.py`; loading does.
        """

        discovered_ids: List[str] = []

        for plugin_dir in self._plugin_dirs:
            plugin_path = Path(plugin_dir).expanduser()
            if not plugin_path.exists() or not plugin_path.is_dir():
                continue

            for item in plugin_path.iterdir():
                if not item.is_dir():
                    continue

                manifest_path = self._find_manifest_path(item)
                if manifest_path is None:
                    continue

                try:
                    manifest = self._load_manifest(manifest_path)
                    if not manifest.plugin_id:
                        raise ValueError("plugin manifest missing plugin_id")

                    existing = self._plugins.get(manifest.plugin_id)
                    plugin = Plugin(
                        plugin_id=manifest.plugin_id,
                        manifest=manifest,
                        path=str(item),
                        status=existing.status if existing else PluginStatus.DISCOVERED,
                        module=existing.module if existing else None,
                        config=dict(existing.config) if existing else {},
                        loaded_at=existing.loaded_at if existing else None,
                        enabled_at=existing.enabled_at if existing else None,
                        error_message=existing.error_message if existing else None,
                        hooks_registered=dict(existing.hooks_registered) if existing else {},
                    )
                    self._plugins[manifest.plugin_id] = plugin
                    discovered_ids.append(manifest.plugin_id)
                    logger.info("Plugin discovered: %s (%s)", manifest.name, manifest.plugin_id)
                except Exception as exc:
                    logger.error("Failed to discover plugin at %s: %s", item, exc)

        logger.info("Discovered %d plugins", len(discovered_ids))
        return DiscoveryResult(discovered_ids)

    def _find_manifest_path(self, plugin_dir: Path) -> Optional[Path]:
        for candidate in ("plugin.json", "manifest.json"):
            path = plugin_dir / candidate
            if path.exists():
                return path
        return None

    def _load_manifest(self, manifest_path: Path) -> PluginManifest:
        with open(manifest_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        return PluginManifest(
            plugin_id=data.get("plugin_id", data.get("id", "")),
            name=data.get("name", ""),
            version=data.get("version", "0.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            homepage=data.get("homepage"),
            license=data.get("license", "MIT"),
            min_core_version=data.get("min_core_version", "15.2.0"),
            dependencies=list(data.get("dependencies", [])),
            hooks=list(data.get("hooks", [])),
            config_schema=dict(data.get("config_schema", {})),
        )

    # ------------------------------------------------------------------
    # Version / dependency checks
    # ------------------------------------------------------------------
    def _check_version_compatibility(self, min_core_version: str) -> bool:
        return self._parse_version(self._core_version) >= self._parse_version(min_core_version)

    def _check_dependencies(self, dependencies: Iterable[str]) -> List[str]:
        missing: List[str] = []
        for dep in dependencies:
            plugin = self._plugins.get(dep)
            if plugin is None or not self._is_enabled_status(plugin.status):
                missing.append(dep)
        return missing

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def load_plugin(self, plugin_id: str) -> bool:
        if plugin_id not in self._plugins:
            logger.error("Plugin not found: %s", plugin_id)
            return False

        plugin = self._plugins[plugin_id]
        if plugin.status not in (PluginStatus.DISCOVERED, PluginStatus.UNLOADED):
            logger.warning("Plugin %s cannot be loaded (status: %s)", plugin_id, plugin.status.value)
            return False

        if not self._check_version_compatibility(plugin.manifest.min_core_version):
            plugin.status = PluginStatus.ERROR
            plugin.error_message = (
                f"Plugin requires core>={plugin.manifest.min_core_version}, "
                f"current={self._core_version}"
            )
            return False

        missing = self._check_dependencies(plugin.manifest.dependencies)
        if missing:
            plugin.status = PluginStatus.ERROR
            plugin.error_message = f"Missing dependency: {missing[0]}"
            return False

        try:
            if plugin.module is None:
                plugin_path = Path(plugin.path or "")
                module_path = plugin_path / "plugin.py"
                if not module_path.exists():
                    raise FileNotFoundError(f"plugin module not found: {module_path}")

                spec = importlib.util.spec_from_file_location(f"plugin_{plugin_id}", module_path)
                if spec is None or spec.loader is None:
                    raise ImportError(f"unable to create import spec for {module_path}")

                module = importlib.util.module_from_spec(spec)
                sys.modules[f"plugin_{plugin_id}"] = module
                spec.loader.exec_module(module)
                plugin.module = module

            plugin.status = PluginStatus.LOADED
            plugin.loaded_at = datetime.now(timezone.utc).isoformat()
            plugin.error_message = None
            self._call_lifecycle_callbacks("on_load", plugin)
            logger.info("Plugin loaded: %s", plugin_id)
            return True
        except Exception as exc:
            logger.exception("Failed to load plugin %s: %s", plugin_id, exc)
            plugin.status = PluginStatus.ERROR
            plugin.error_message = str(exc)
            return False

    def enable_plugin(self, plugin_id: str, config: Optional[Dict[str, Any]] = None) -> bool:
        if plugin_id not in self._plugins:
            return False

        plugin = self._plugins[plugin_id]
        if self._is_enabled_status(plugin.status):
            return False

        if plugin.status != PluginStatus.LOADED and not self.load_plugin(plugin_id):
            return False

        try:
            plugin.config = dict(config or {})
            if hasattr(plugin.module, "on_enable"):
                plugin.module.on_enable(plugin.config)

            self._register_plugin_hooks(plugin)
            plugin.status = PluginStatus.ACTIVE
            plugin.enabled_at = datetime.now(timezone.utc).isoformat()
            plugin.error_message = None
            self._call_lifecycle_callbacks("on_enable", plugin)
            logger.info("Plugin enabled: %s", plugin_id)
            return True
        except Exception as exc:
            logger.exception("Failed to enable plugin %s: %s", plugin_id, exc)
            plugin.status = PluginStatus.ERROR
            plugin.error_message = str(exc)
            return False

    def disable_plugin(self, plugin_id: str) -> bool:
        if plugin_id not in self._plugins:
            return False

        plugin = self._plugins[plugin_id]
        if not self._is_enabled_status(plugin.status):
            return False

        try:
            if hasattr(plugin.module, "on_disable"):
                plugin.module.on_disable()
            self._unregister_plugin_hooks(plugin)
            plugin.status = PluginStatus.DISABLED
            plugin.enabled_at = None
            self._call_lifecycle_callbacks("on_disable", plugin)
            logger.info("Plugin disabled: %s", plugin_id)
            return True
        except Exception as exc:
            logger.exception("Failed to disable plugin %s: %s", plugin_id, exc)
            plugin.error_message = str(exc)
            return False

    def unload_plugin(self, plugin_id: str) -> bool:
        if plugin_id not in self._plugins:
            return False

        plugin = self._plugins[plugin_id]
        if self._is_enabled_status(plugin.status):
            self.disable_plugin(plugin_id)

        if plugin.status not in (PluginStatus.LOADED, PluginStatus.DISABLED, PluginStatus.ERROR):
            return False

        try:
            if hasattr(plugin.module, "on_unload"):
                plugin.module.on_unload()

            module_name = f"plugin_{plugin_id}"
            if module_name in sys.modules:
                del sys.modules[module_name]

            plugin.module = None
            plugin.status = PluginStatus.UNLOADED
            plugin.loaded_at = None
            plugin.enabled_at = None
            self._call_lifecycle_callbacks("on_unload", plugin)
            logger.info("Plugin unloaded: %s", plugin_id)
            return True
        except Exception as exc:
            logger.exception("Failed to unload plugin %s: %s", plugin_id, exc)
            plugin.error_message = str(exc)
            return False

    # ------------------------------------------------------------------
    # Hook registration / triggering
    # ------------------------------------------------------------------
    def register_hook(
        self,
        hook_type: str | PluginHook,
        callback: Callable,
        *,
        priority: int = 0,
        plugin_id: str = "runtime",
    ) -> str:
        hook_enum = self._normalize_hook_enum(hook_type)
        hook_key = self._normalize_hook_key(hook_type)
        hook_id = f"hook_{uuid.uuid4().hex}"

        registration = HookRegistration(
            hook_id=hook_id,
            hook_type=hook_enum,
            plugin_id=plugin_id,
            handler=callback,
            priority=priority,
        )
        hook_bucket = self._hooks.setdefault(hook_key, [])
        hook_bucket.append(registration)
        if isinstance(hook_type, PluginHook):
            self._hooks[hook_type] = hook_bucket
        return hook_id

    def unregister_hook(self, hook_id: str) -> bool:
        for hook_key, hooks in self._hooks.items():
            for index, hook in enumerate(hooks):
                if hook.hook_id != hook_id:
                    continue
                del hooks[index]
                return True
        return False

    def _register_plugin_hooks(self, plugin: Plugin) -> None:
        module = plugin.module
        hook_map = {
            "on_startup": PluginHook.ON_STARTUP,
            "on_shutdown": PluginHook.ON_SHUTDOWN,
            "on_config_load": PluginHook.ON_CONFIG_LOAD,
            "on_event": PluginHook.ON_EVENT,
            "on_request": PluginHook.ON_REQUEST,
            "on_response": PluginHook.ON_RESPONSE,
            "on_error": PluginHook.ON_ERROR,
            "on_event_received": PluginHook.ON_EVENT_RECEIVED,
            "on_zone_created": PluginHook.ON_ZONE_CREATED,
            "on_health_check": PluginHook.ON_HEALTH_CHECK,
        }

        for hook_name, hook_type in hook_map.items():
            if not hasattr(module, hook_name):
                continue
            handler = getattr(module, hook_name)
            hook_key = hook_type.value
            registration = HookRegistration(
                hook_id=f"{plugin.plugin_id}:{hook_name}",
                hook_type=hook_type,
                plugin_id=plugin.plugin_id,
                handler=handler,
            )
            self._hooks.setdefault(hook_key, []).append(registration)
            plugin.hooks_registered.setdefault(hook_key, []).append(handler)

    def _unregister_plugin_hooks(self, plugin: Plugin) -> None:
        for hook_key in list(plugin.hooks_registered.keys()):
            if hook_key in self._hooks:
                self._hooks[hook_key] = [
                    hook for hook in self._hooks[hook_key] if hook.plugin_id != plugin.plugin_id
                ]
                if not self._hooks[hook_key]:
                    del self._hooks[hook_key]
        plugin.hooks_registered.clear()

    def trigger_hook(self, hook_type: str | PluginHook, *args, **kwargs) -> List[Any]:
        hook_key = self._normalize_hook_key(hook_type)
        if hook_key not in self._hooks:
            return []

        results: List[Any] = []
        hooks = sorted(self._hooks[hook_key], key=lambda hook: hook.priority, reverse=True)
        for hook in hooks:
            try:
                result = hook.handler(*args, **kwargs)
                if result is not None:
                    results.append(result)
            except Exception as exc:
                logger.exception("Hook %s failed: %s", hook.hook_id, exc)
        return results

    # ------------------------------------------------------------------
    # Query / update helpers
    # ------------------------------------------------------------------
    def get_plugin(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        plugin = self._plugins.get(plugin_id)
        return None if plugin is None else self._plugin_to_api_dict(plugin)

    def get_all_plugins(self, status: Optional[PluginStatus] = None) -> List[Dict[str, Any]]:
        plugins = list(self._plugins.values())
        if status is not None:
            if status == PluginStatus.ENABLED:
                plugins = [p for p in plugins if self._is_enabled_status(p.status)]
            else:
                plugins = [p for p in plugins if p.status == status]
        return [self._plugin_to_api_dict(plugin) for plugin in plugins]

    def get_enabled_plugins(self) -> List[Dict[str, Any]]:
        return self.get_all_plugins(status=PluginStatus.ENABLED)

    def get_plugin_config(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        plugin = self._plugins.get(plugin_id)
        return None if plugin is None else dict(plugin.config)

    def update_plugin_config(self, plugin_id: str, config: Dict[str, Any]) -> bool:
        plugin = self._plugins.get(plugin_id)
        if plugin is None:
            return False
        plugin.config.update(config)
        return True

    def get_plugin_summary(self) -> Dict[str, Any]:
        enabled_count = sum(1 for plugin in self._plugins.values() if self._is_enabled_status(plugin.status))
        return {
            "total_plugins": len(self._plugins),
            "active_plugins": enabled_count,
            "plugins_dir": str(self._plugins_dir),
            "core_version": self._core_version,
        }

    def register_plugin(self, plugin_id: str, manifest: Dict[str, Any], module: Any = None) -> bool:
        if plugin_id in self._plugins:
            return False

        plugin_manifest = PluginManifest(
            plugin_id=manifest.get("plugin_id", plugin_id),
            name=manifest.get("name", plugin_id),
            version=manifest.get("version", "0.0.0"),
            description=manifest.get("description", ""),
            author=manifest.get("author", ""),
            homepage=manifest.get("homepage"),
            license=manifest.get("license", "MIT"),
            min_core_version=manifest.get("min_core_version", "15.2.0"),
            dependencies=list(manifest.get("dependencies", [])),
            hooks=list(manifest.get("hooks", [])),
            config_schema=dict(manifest.get("config_schema", {})),
        )

        plugin = Plugin(
            plugin_id=plugin_id,
            manifest=plugin_manifest,
            module=module,
            status=PluginStatus.LOADED if module is not None else PluginStatus.DISCOVERED,
            loaded_at=datetime.now(timezone.utc).isoformat() if module is not None else None,
        )
        self._plugins[plugin_id] = plugin
        logger.info("Plugin registered: %s", plugin_id)
        return True

    def get_statistics(self) -> Dict[str, Any]:
        by_status: Dict[str, int] = {}
        for plugin in self._plugins.values():
            bucket = "enabled" if self._is_enabled_status(plugin.status) else plugin.status.value
            by_status[bucket] = by_status.get(bucket, 0) + 1

        total_loaded = sum(
            1
            for plugin in self._plugins.values()
            if plugin.status in (PluginStatus.LOADED, PluginStatus.ACTIVE, PluginStatus.ENABLED, PluginStatus.DISABLED)
        )
        total_enabled = sum(1 for plugin in self._plugins.values() if self._is_enabled_status(plugin.status))
        total_errors = sum(1 for plugin in self._plugins.values() if plugin.status == PluginStatus.ERROR)

        string_hook_values = [hooks for key, hooks in self._hooks.items() if isinstance(key, str)]

        return {
            "total_discovered": len(self._plugins),
            "total_loaded": total_loaded,
            "total_enabled": total_enabled,
            "total_errors": total_errors,
            "by_status": by_status,
            "total_hooks": sum(len(hooks) for hooks in string_hook_values),
            "hook_types": len(string_hook_values),
        }

    def get_hooks(self, hook_type: Optional[str] = None) -> List[Dict[str, Any]]:
        hooks: List[Dict[str, Any]] = []
        for current_hook_type, hook_list in self._hooks.items():
            if not isinstance(current_hook_type, str):
                continue
            if hook_type is not None and current_hook_type != hook_type:
                continue
            hooks.extend(hook.to_dict() for hook in hook_list)
        return hooks

    def validate_plugin_dependencies(self, plugin_id: str) -> Dict[str, Any]:
        plugin = self._plugins.get(plugin_id)
        if plugin is None:
            return {"valid": False, "errors": ["Plugin not found"]}

        errors: List[str] = []
        missing: List[str] = []
        for dep in plugin.manifest.dependencies:
            dep_plugin = self._plugins.get(dep)
            if dep_plugin is None:
                missing.append(dep)
                errors.append(f"Missing dependency: {dep}")
            elif not self._is_enabled_status(dep_plugin.status):
                errors.append(f"Dependency not enabled: {dep}")

        return {"valid": not errors, "errors": errors, "missing": missing}

    def register_lifecycle_callback(self, callback_type: str, callback: Callable[[Plugin], None]) -> bool:
        if callback_type not in self._lifecycle_callbacks:
            return False
        self._lifecycle_callbacks[callback_type].append(callback)
        return True

    def _call_lifecycle_callbacks(self, callback_type: str, plugin: Plugin) -> None:
        for callback in self._lifecycle_callbacks.get(callback_type, []):
            try:
                callback(plugin)
            except Exception as exc:
                logger.exception("Lifecycle callback failed: %s", exc)


def create_plugin_engine(
    plugin_dirs: Optional[List[str]] = None,
    *,
    plugins_dir: Optional[str] = None,
    core_version: str = "15.3.0",
) -> PluginEngine:
    """Factory function to create plugin engine.

    Supports both:
    - `plugin_dirs=[...]` (current contract)
    - `plugins_dir="..."` (legacy contract)
    - `core_version="..."` for compatibility tests
    """

    return PluginEngine(
        plugin_dirs=plugin_dirs,
        plugins_dir=plugins_dir,
        core_version=core_version,
    )
