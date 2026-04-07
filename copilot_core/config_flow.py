"""PilotSuite Config Flow — Visual Configuration UI for Home Assistant."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.core import callback

from . import DOMAIN

logger = logging.getLogger(__name__)


class PilotSuiteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle PilotSuite config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self):
        """Initialize config flow."""
        self._config = {}

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle user step."""
        errors = {}

        if user_input is not None:
            self._config.update(user_input)
            return await self.async_step_integrations()

        data_schema = vol.Schema(
            {
                vol.Required("debug", default=False): bool,
                vol.Required("data_dir", default="/config/pilotsuite"): str,
                vol.Required("llm_model", default="ollama/qwen3.5:397b-cloud"): str,
                vol.Required("database_url", default="sqlite+aiosqlite:///./pilotsuite.db"): str,
                vol.Required("redis_url", default="redis://localhost:6379/0"): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_integrations(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle integrations configuration."""
        if user_input is not None:
            self._config["notifications"] = user_input
            return await self.async_step_calendar()

        data_schema = vol.Schema(
            {
                vol.Optional("enable_pushover", default=False): bool,
                vol.Optional("pushover_api_token"): str,
                vol.Optional("pushover_user_key"): str,
                vol.Optional("enable_telegram", default=False): bool,
                vol.Optional("telegram_bot_token"): str,
                vol.Optional("telegram_chat_ids"): str,
            }
        )

        return self.async_show_form(
            step_id="integrations",
            data_schema=data_schema,
        )

    async def async_step_calendar(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle calendar configuration."""
        if user_input is not None:
            self._config["calendar"] = user_input
            return await self.async_step_features()

        data_schema = vol.Schema(
            {
                vol.Optional("enable_google_calendar", default=False): bool,
                vol.Optional("google_credentials_file"): str,
                vol.Optional("enable_caldav", default=False): bool,
                vol.Optional("caldav_url"): str,
                vol.Optional("caldav_username"): str,
                vol.Optional("caldav_password"): str,
                vol.Optional("enable_ical", default=False): bool,
                vol.Optional("ical_file_paths"): str,
            }
        )

        return self.async_show_form(
            step_id="calendar",
            data_schema=data_schema,
        )

    async def async_step_features(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle features configuration."""
        if user_input is not None:
            self._config["features"] = user_input
            return await self.async_step_sync()

        data_schema = vol.Schema(
            {
                vol.Optional("enable_weather_automation", default=True): bool,
                vol.Optional("weather_entity", default="weather.home"): str,
                vol.Optional("enable_scenes", default=True): bool,
                vol.Optional("enable_analytics", default=True): bool,
                vol.Optional("enable_reporting", default=True): bool,
                vol.Optional("analytics_retention_days", default=30): int,
            }
        )

        return self.async_show_form(
            step_id="features",
            data_schema=data_schema,
        )

    async def async_step_sync(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle multi-home sync configuration."""
        if user_input is not None:
            self._config["sync"] = user_input
            return await self.async_step_performance()

        data_schema = vol.Schema(
            {
                vol.Optional("enable_multi_home_sync", default=False): bool,
                vol.Optional("home_id", default="main"): str,
            }
        )

        return self.async_show_form(
            step_id="sync",
            data_schema=data_schema,
        )

    async def async_step_performance(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle performance configuration."""
        if user_input is not None:
            self._config["performance"] = user_input
            return await self.async_step_finalize()

        data_schema = vol.Schema(
            {
                vol.Optional("cache_size", default=10000): int,
                vol.Optional("cache_ttl", default=300): int,
                vol.Optional("max_memory_mb", default=1500): int,
            }
        )

        return self.async_show_form(
            step_id="performance",
            data_schema=data_schema,
        )

    async def async_step_finalize(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Finalize configuration."""
        # Create entry with all config
        return self.async_create_entry(
            title="PilotSuite Core",
            data=self._config,
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: config_entries.ConfigEntry) -> PilotSuiteOptionsFlow:
        """Get options flow."""
        return PilotSuiteOptionsFlow(entry)


class PilotSuiteOptionsFlow(config_entries.OptionsFlow):
    """Handle PilotSuite options flow."""

    def __init__(self, entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self._entry = entry

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle options step."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get current config
        current = dict(self._entry.data)
        
        data_schema = vol.Schema(
            {
                vol.Required("debug", default=current.get("debug", False)): bool,
                vol.Required("data_dir", default=current.get("data_dir", "/config/pilotsuite")): str,
                vol.Required("llm_model", default=current.get("llm_model", "ollama/qwen3.5:397b-cloud")): str,
                vol.Required("database_url", default=current.get("database_url", "sqlite+aiosqlite:///./pilotsuite.db")): str,
                vol.Required("redis_url", default=current.get("redis_url", "redis://localhost:6379/0")): str,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
        )
