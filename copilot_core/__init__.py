"""PilotSuite Core — Main Integration Module for Home Assistant."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import timedelta


_ADDON_APP_PACKAGE = Path(__file__).resolve().parent.parent / "addons" / "pilotsuite" / "app" / "copilot_core"
if _ADDON_APP_PACKAGE.is_dir():
    addon_package_path = str(_ADDON_APP_PACKAGE)
    if addon_package_path not in __path__:
        __path__.append(addon_package_path)

try:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.helpers.event import async_track_time_interval
    from homeassistant.helpers import config_validation as cv

    import voluptuous as vol

    HAS_HOMEASSISTANT = True
except ModuleNotFoundError:
    ConfigEntry = HomeAssistant = ServiceCall = Any  # type: ignore
    async_track_time_interval = None  # type: ignore
    cv = None  # type: ignore
    vol = None  # type: ignore
    HAS_HOMEASSISTANT = False

# Version — forward to addon path if available
try:
    from copilot_core import __version__ as _addon_version
    __version__ = _addon_version
except ImportError:
    __version__ = '0.0.0'


# =============================================================================
# PUBLIC API — explicit exports for repo-root compatibility surface
# =============================================================================
__all__ = [
    "__version__",
    "DOMAIN",
    "PLATFORMS",
    "CONFIG_SCHEMA",
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
    "async_remove_entry",
    "HAS_HOMEASSISTANT",
    "_require_homeassistant_runtime",
    "SERVICES",
    "_build_notification_config",
    "_build_calendar_config",
]

if HAS_HOMEASSISTANT:
    from .database.models import init_database, get_database_manager
    from .database.migrations import MigrationManager, register_default_migrations
    from .tasks.task_queue import TaskQueueManager, register_default_tasks, ScheduledTaskManager
    from .integrations.notifications import NotificationManager, NotificationManagerConfig
    from .integrations.calendar import CalendarManager, CalendarManagerConfig
    from .integrations.weather_automation import async_setup_weather_automations
    from .scenes.scene_engine import SceneEngine, get_predefined_scenes, SceneAutomationManager
    from .plugins.plugin_manager import PluginManager
    from .sync.multi_home_sync import MultiHomeSyncEngine, RemoteHome, SyncDirection
    from .analytics.advanced_analytics import async_setup_analytics
    from .reporting.engine import ReportGenerator, ReportDelivery
    from .lovelace.additional_cards import CARD_REGISTRY
    from .api.rest_server import create_app, APIConfig
    from .api.websocket_manager import WebSocketManager
    from .optimization.advanced_optimizations import init_performance_optimizations

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

DOMAIN = "pilotsuite"
DEFAULT_NAME = "PilotSuite Core"

if HAS_HOMEASSISTANT:
    CONFIG_SCHEMA = vol.Schema(
        {
            DOMAIN: vol.Schema(
                {
                    vol.Optional("debug", default=False): cv.boolean,
                    vol.Optional("data_dir", default="/config/pilotsuite"): cv.string,
                    vol.Optional("llm_model", default="ollama/qwen3.5:397b-cloud"): cv.string,

                    # Database
                    vol.Optional("database_url", default="sqlite+aiosqlite:///./pilotsuite.db"): cv.string,

                    # Task Queue
                    vol.Optional("redis_url", default="redis://localhost:6379/0"): cv.string,

                    # Notifications
                    vol.Optional("notifications"): vol.Schema(
                        {
                            vol.Optional("pushover"): vol.Schema(
                                {
                                    vol.Required("api_token"): cv.string,
                                    vol.Required("user_key"): cv.string,
                                    vol.Optional("sound"): cv.string,
                                }
                            ),
                            vol.Optional("telegram"): vol.Schema(
                                {
                                    vol.Required("bot_token"): cv.string,
                                    vol.Required("chat_ids"): vol.ensure_list(cv.string),
                                }
                            ),
                        }
                    ),

                    # Calendar
                    vol.Optional("calendar"): vol.Schema(
                        {
                            vol.Optional("google"): vol.Schema(
                                {
                                    vol.Required("credentials_file"): cv.string,
                                    vol.Optional("calendar_ids"): cv.ensure_list(cv.string),
                                }
                            ),
                            vol.Optional("caldav"): vol.Schema(
                                {
                                    vol.Required("url"): cv.string,
                                    vol.Required("username"): cv.string,
                                    vol.Required("password"): cv.string,
                                }
                            ),
                            vol.Optional("ical"): vol.Schema(
                                {
                                    vol.Required("file_paths"): cv.ensure_list(cv.string),
                                }
                            ),
                            vol.Optional("home_assistant", default=True): cv.boolean,
                        }
                    ),

                    # Weather
                    vol.Optional("weather"): vol.Schema(
                        {
                            vol.Optional("weather_entity", default="weather.home"): cv.string,
                            vol.Optional("evaluation_interval", default=5): cv.positive_int,
                            vol.Optional("custom_rules"): vol.All(cv.ensure_list, [dict]),
                        }
                    ),

                    # Scenes
                    vol.Optional("scenes"): vol.Schema(
                        {
                            vol.Optional("custom_scenes"): vol.All(cv.ensure_list, [dict]),
                        }
                    ),

                    # Multi-Home Sync
                    vol.Optional("sync"): vol.Schema(
                        {
                            vol.Optional("home_id", default="main"): cv.string,
                            vol.Optional("remote_homes"): vol.All(cv.ensure_list, [dict]),
                        }
                    ),

                    # Analytics
                    vol.Optional("analytics"): vol.Schema(
                        {
                            vol.Optional("retention_days", default=30): cv.positive_int,
                            vol.Optional("metrics_enabled", default=True): cv.boolean,
                        }
                    ),

                    # Reporting
                    vol.Optional("reporting"): vol.Schema(
                        {
                            vol.Optional("daily_enabled", default=True): cv.boolean,
                            vol.Optional("weekly_enabled", default=True): cv.boolean,
                            vol.Optional("delivery_channels"): cv.ensure_list(cv.string),
                        }
                    ),

                    # Performance
                    vol.Optional("performance"): vol.Schema(
                        {
                            vol.Optional("cache_size", default=10000): cv.positive_int,
                            vol.Optional("cache_ttl", default=300): cv.positive_int,
                            vol.Optional("max_memory_mb", default=1500): cv.positive_int,
                        }
                    ),
                }
            )
        },
        extra=vol.ALLOW_EXTRA,
    )
else:
    CONFIG_SCHEMA = None

# =============================================================================
# PLATFORMS
# =============================================================================

PLATFORMS = [
    "sensor",
    "switch",
    "binary_sensor",
    "notify",
]

# =============================================================================
# SERVICES
# =============================================================================

if HAS_HOMEASSISTANT:
    SERVICES = {
        "notify": vol.Schema(
            {
                vol.Required("title"): cv.string,
                vol.Required("message"): cv.string,
                vol.Optional("priority", default=0): vol.In([-2, -1, 0, 1, 2]),
                vol.Optional("url"): cv.string,
                vol.Optional("url_title"): cv.string,
            }
        ),
        "notify_urgent": vol.Schema(
            {
                vol.Required("title"): cv.string,
                vol.Required("message"): cv.string,
            }
        ),
        "activate_scene": vol.Schema(
            {
                vol.Required("scene_id"): cv.string,
            }
        ),
        "get_calendar_events": vol.Schema(
            {
                vol.Optional("days", default=7): cv.positive_int,
                vol.Optional("source"): cv.string,
            }
        ),
        "evaluate_weather": vol.Schema({}),
        "sync_now": vol.Schema(
            {
                vol.Optional("home_ids"): cv.ensure_list(cv.string),
            }
        ),
        "create_backup": vol.Schema(
            {
                vol.Optional("include_patterns", default=True): cv.boolean,
                vol.Optional("include_vectors", default=True): cv.boolean,
            }
        ),
        "optimize_energy": vol.Schema(
            {
                vol.Optional("device_ids"): cv.ensure_list(cv.string),
                vol.Optional("horizon_hours", default=24): cv.positive_int,
            }
        ),
    }
else:
    SERVICES = {}


def _require_homeassistant_runtime() -> None:
    """Fail clearly when the Home Assistant integration is imported standalone."""
    if not HAS_HOMEASSISTANT:
        raise ModuleNotFoundError(
            "homeassistant is required for copilot_core integration runtime; "
            "standalone subpackages like copilot_core.config remain importable without it"
        )

# =============================================================================
# MAIN INTEGRATION
# =============================================================================

async def async_setup(hass: HomeAssistant, config: Dict[str, Any]) -> bool:
    """Set up PilotSuite Core."""
    _require_homeassistant_runtime()
    logger.info("Setting up PilotSuite Core...")

    # Store config
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN]["config"] = config.get(DOMAIN, {})

    logger.info("PilotSuite Core setup complete")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PilotSuite Core from a config entry."""
    _require_homeassistant_runtime()
    logger.info("Setting up PilotSuite Core from config entry...")

    config = entry.data
    options = entry.options

    # Merge config and options
    full_config = {**config, **options}

    hass.data[DOMAIN][entry.entry_id] = {
        "config": full_config,
    }

    # Initialize all components
    await _initialize_all_components(hass, full_config)

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    await _register_services(hass, full_config)

    # Set up periodic tasks
    await _setup_periodic_tasks(hass, full_config)

    logger.info(f"PilotSuite Core entry {entry.entry_id} set up complete")
    return True


async def _initialize_all_components(hass: HomeAssistant, config: Dict[str, Any]):
    """Initialize all PilotSuite components."""
    _require_homeassistant_runtime()

    data_dir = config.get("data_dir", "/config/pilotsuite")

    # 1. Database
    logger.info("Initializing database...")
    db_url = config.get("database_url", f"sqlite+aiosqlite:///{data_dir}/pilotsuite.db")
    await init_database(db_url)

    # 2. Migrations
    logger.info("Running migrations...")
    migrations = MigrationManager(f"{data_dir}/migrations")
    register_default_migrations(migrations)
    await migrations.run()
    hass.data[DOMAIN]["migrations"] = migrations

    # 3. Task Queue
    logger.info("Initializing task queue...")
    redis_url = config.get("redis_url", "redis://localhost:6379/0")
    task_queue = TaskQueueManager(redis_url)
    task_queue.init_celery()
    register_default_tasks(task_queue)
    scheduled_tasks = ScheduledTaskManager(task_queue)
    hass.data[DOMAIN]["task_queue"] = task_queue
    hass.data[DOMAIN]["scheduled_tasks"] = scheduled_tasks

    # 4. Notifications
    logger.info("Initializing notifications...")
    notif_config = _build_notification_config(config.get("notifications", {}))
    if notif_config:
        notification_manager = NotificationManager(notif_config)
        hass.data[DOMAIN]["notification_manager"] = notification_manager

    # 5. Calendar
    logger.info("Initializing calendar...")
    cal_config = _build_calendar_config(config.get("calendar", {}))
    calendar_manager = CalendarManager(hass, cal_config)
    hass.data[DOMAIN]["calendar_manager"] = calendar_manager

    # 6. Weather Automations
    logger.info("Setting up weather automations...")
    await async_setup_weather_automations(hass, config.get("weather", {}))

    # 7. Scenes
    logger.info("Setting up scenes...")
    scene_engine = SceneEngine(hass)
    for scene in get_predefined_scenes():
        scene_engine.add_scene(scene)
    scene_automation = SceneAutomationManager(hass, scene_engine)
    hass.data[DOMAIN]["scene_engine"] = scene_engine
    hass.data[DOMAIN]["scene_automation"] = scene_automation

    # 8. Plugins
    logger.info("Initializing plugin system...")
    plugin_manager = PluginManager(f"{data_dir}/plugins")
    await plugin_manager.load_plugins()
    hass.data[DOMAIN]["plugin_manager"] = plugin_manager

    # 9. Multi-Home Sync
    logger.info("Setting up multi-home sync...")
    sync_config = config.get("sync", {})
    sync_engine = MultiHomeSyncEngine(hass, sync_config.get("home_id", "main"))
    for remote_config in sync_config.get("remote_homes", []):
        remote = RemoteHome(
            home_id=remote_config["home_id"],
            name=remote_config["name"],
            url=remote_config["url"],
            api_token=remote_config["api_token"],
            enabled=remote_config.get("enabled", True),
            sync_direction=SyncDirection(remote_config.get("sync_direction", "bidirectional")),
        )
        sync_engine.add_remote_home(remote)
    hass.data[DOMAIN]["sync_engine"] = sync_engine

    # 10. Analytics
    logger.info("Setting up analytics...")
    analytics_config = config.get("analytics", {})
    await async_setup_analytics(hass, analytics_config)

    # 11. Reporting
    logger.info("Setting up reporting...")
    report_generator = ReportGenerator(hass)
    report_delivery = ReportDelivery()
    hass.data[DOMAIN]["report_generator"] = report_generator
    hass.data[DOMAIN]["report_delivery"] = report_delivery

    # 12. Performance Optimizations
    logger.info("Initializing performance optimizations...")
    perf_config = config.get("performance", {})
    init_performance_optimizations(
        cache_size=perf_config.get("cache_size", 10000),
        cache_ttl=perf_config.get("cache_ttl", 300),
        max_memory_mb=perf_config.get("max_memory_mb", 1500),
    )

    # 13. REST API
    logger.info("Starting REST API server...")
    api_config = APIConfig(
        debug=config.get("debug", False),
        host="0.0.0.0",
        port=8080,
    )
    api_app = create_app(api_config)
    hass.data[DOMAIN]["api_app"] = api_app

    # 14. WebSocket Manager
    logger.info("Initializing WebSocket manager...")
    ws_manager = WebSocketManager(hass)
    hass.data[DOMAIN]["websocket_manager"] = ws_manager

    logger.info("All components initialized successfully!")


def _build_notification_config(notif_config: Dict[str, Any]):
    """Build notification manager config."""
    _require_homeassistant_runtime()
    from .integrations.notifications import PushoverConfig, TelegramConfig, NotificationManagerConfig

    pushover = None
    if "pushover" in notif_config:
        po = notif_config["pushover"]
        pushover = PushoverConfig(
            api_token=po["api_token"],
            user_key=po["user_key"],
            sound=po.get("sound"),
        )

    telegram = None
    if "telegram" in notif_config:
        tg = notif_config["telegram"]
        telegram = TelegramConfig(
            bot_token=tg["bot_token"],
            chat_ids=tg["chat_ids"],
        )

    if pushover or telegram:
        return NotificationManagerConfig(
            pushover=pushover,
            telegram=telegram,
        )

    return None


def _build_calendar_config(cal_config: Dict[str, Any]):
    """Build calendar manager config."""
    _require_homeassistant_runtime()
    from .integrations.calendar import GoogleCalendarConfig, CalDAVConfig, ICalConfig, CalendarManagerConfig

    google = None
    if "google" in cal_config:
        g = cal_config["google"]
        google = GoogleCalendarConfig(
            credentials_file=g["credentials_file"],
            calendar_ids=g.get("calendar_ids"),
        )

    caldav = None
    if "caldav" in cal_config:
        c = cal_config["caldav"]
        caldav = CalDAVConfig(
            url=c["url"],
            username=c["username"],
            password=c["password"],
        )

    ical = None
    if "ical" in cal_config:
        i = cal_config["ical"]
        ical = ICalConfig(
            file_paths=i["file_paths"],
        )

    return CalendarManagerConfig(
        google=google,
        caldav=caldav,
        ical=ical,
        home_assistant=cal_config.get("home_assistant", True),
    )


async def _register_services(hass: HomeAssistant, config: Dict[str, Any]):
    """Register all PilotSuite services."""
    _require_homeassistant_runtime()

    async def notify_handler(call: ServiceCall):
        """Handle notify service calls."""
        manager = hass.data[DOMAIN].get("notification_manager")
        if not manager:
            logger.error("Notification manager not initialized")
            return

        from .integrations.notifications import Notification, NotificationPriority

        notification = Notification(
            title=call.data["title"],
            message=call.data["message"],
            priority=NotificationPriority(call.data.get("priority", 0)),
            url=call.data.get("url"),
            url_title=call.data.get("url_title"),
        )

        await manager.send(notification)

    async def notify_urgent_handler(call: ServiceCall):
        """Handle urgent notify service calls."""
        manager = hass.data[DOMAIN].get("notification_manager")
        if not manager:
            logger.error("Notification manager not initialized")
            return

        await manager.send_urgent(call.data["title"], call.data["message"])

    async def activate_scene_handler(call: ServiceCall):
        """Handle scene activation."""
        engine = hass.data[DOMAIN].get("scene_engine")
        if not engine:
            logger.error("Scene engine not initialized")
            return

        await engine.activate_scene(call.data["scene_id"])

    async def get_calendar_events_handler(call: ServiceCall):
        """Handle calendar events request."""
        manager = hass.data[DOMAIN].get("calendar_manager")
        if not manager:
            logger.error("Calendar manager not initialized")
            return

        events = await manager.get_events(
            days=call.data.get("days", 7),
            calendar_source=call.data.get("source"),
        )

        return {
            "events": [
                {
                    "uid": e.uid,
                    "summary": e.summary,
                    "start": e.start.isoformat(),
                    "end": e.end.isoformat(),
                    "calendar": e.calendar_name,
                }
                for e in events
            ]
        }

    async def evaluate_weather_handler(call: ServiceCall):
        """Handle weather automation evaluation."""
        engine = hass.data[DOMAIN].get("pilotsuite_weather_engine")
        if not engine:
            logger.error("Weather engine not initialized")
            return

        triggered = await engine.evaluate_rules()
        logger.info(f"Weather automations triggered: {triggered}")

    async def sync_now_handler(call: ServiceCall):
        """Handle multi-home sync."""
        engine = hass.data[DOMAIN].get("sync_engine")
        if not engine:
            logger.error("Sync engine not initialized")
            return

        result = await engine.sync_now(call.data.get("home_ids"))
        logger.info(f"Sync result: {result}")

    async def create_backup_handler(call: ServiceCall):
        """Handle backup creation."""
        task_queue = hass.data[DOMAIN].get("task_queue")
        if not task_queue:
            logger.error("Task queue not initialized")
            return

        result = await task_queue.execute_task(
            "backup.create",
            include_patterns=call.data.get("include_patterns", True),
            include_vectors=call.data.get("include_vectors", True),
        )
        logger.info(f"Backup result: {result}")

    async def optimize_energy_handler(call: ServiceCall):
        """Handle energy optimization."""
        task_queue = hass.data[DOMAIN].get("task_queue")
        if not task_queue:
            logger.error("Task queue not initialized")
            return

        result = await task_queue.execute_task(
            "energy.optimize",
            device_ids=call.data.get("device_ids"),
            horizon_hours=call.data.get("horizon_hours", 24),
        )
        logger.info(f"Energy optimization result: {result}")

    # Register all services
    for service_name, schema in SERVICES.items():
        handler = {
            "notify": notify_handler,
            "notify_urgent": notify_urgent_handler,
            "activate_scene": activate_scene_handler,
            "get_calendar_events": get_calendar_events_handler,
            "evaluate_weather": evaluate_weather_handler,
            "sync_now": sync_now_handler,
            "create_backup": create_backup_handler,
            "optimize_energy": optimize_energy_handler,
        }.get(service_name)

        if handler:
            hass.services.async_register(DOMAIN, service_name, handler, schema=schema)
            logger.info(f"Registered service: {service_name}")


async def _setup_periodic_tasks(hass: HomeAssistant, config: Dict[str, Any]):
    """Set up periodic background tasks."""
    _require_homeassistant_runtime()

    # Weather automation evaluation (every 5 minutes)
    async def weather_eval(now):
        engine = hass.data[DOMAIN].get("pilotsuite_weather_engine")
        if engine:
            await engine.evaluate_rules()

    async_track_time_interval(hass, weather_eval, timedelta(minutes=5))

    # Scene automation evaluation (every 30 seconds)
    async def scene_eval(now):
        automation = hass.data[DOMAIN].get("scene_automation")
        if automation:
            await automation.evaluate_triggers()

    async_track_time_interval(hass, scene_eval, timedelta(seconds=30))

    # Multi-home sync (every 5 minutes)
    async def sync_eval(now):
        engine = hass.data[DOMAIN].get("sync_engine")
        if engine and engine.get_remote_homes():
            await engine.sync_now()

    async_track_time_interval(hass, sync_eval, timedelta(minutes=5))

    # Daily report (at 8 AM)
    async def daily_report(now):
        if now.hour == 8 and now.minute == 0:
            generator = hass.data[DOMAIN].get("report_generator")
            delivery = hass.data[DOMAIN].get("report_delivery")
            if generator and delivery:
                report = await generator.generate_daily_summary()
                await delivery.deliver_to_file(report, f"/config/pilotsuite/reports/daily_{now.strftime('%Y%m%d')}.json")

    async_track_time_interval(hass, daily_report, timedelta(minutes=1))

    logger.info("Periodic tasks set up")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _require_homeassistant_runtime()
    logger.info(f"Unloading PilotSuite Core entry {entry.entry_id}")

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Close database
        db_manager = get_database_manager()
        if db_manager:
            await db_manager.close()

        # Close task queue
        task_queue = hass.data[DOMAIN].get("task_queue")
        if task_queue:
            await task_queue.close()

        # Close notifications
        notif_manager = hass.data[DOMAIN].get("notification_manager")
        if notif_manager:
            await notif_manager.close()

        hass.data[DOMAIN].pop(entry.entry_id, None)

    logger.info(f"PilotSuite Core entry {entry.entry_id} unloaded")
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove a config entry."""
    _require_homeassistant_runtime()
    logger.info(f"Removing PilotSuite Core entry {entry.entry_id}")
    return True
