"""Single access seam for voice runtime services.

This keeps HTTP adapters out of the business of constructing concrete voice
services directly. Callers should resolve the shared runtime through
``get_voice_runtime()`` and then consume its narrow accessors.
"""
from __future__ import annotations

import logging
from pathlib import Path
import time
from typing import Any, MutableMapping, Optional

from flask import Flask, current_app

from copilot_core.voice import (
    SttEnginePort,
    TtsEnginePort,
    NluEnginePort,
    _create_stt_engine,
    _create_tts_engine,
    _create_nlu_engine,
    WhisperSTT,
    PiperTTS,
    NLUEngine,
)

from copilot_core.voice.command_flow import VoiceCommandFlow
from copilot_core.voice.dialog_flow import VoiceDialogFlow
from copilot_core.voice.command_router import VoiceCommandRouter
from copilot_core.voice.context_builder import VoiceContextBuilder, VoiceContextRuntime
from copilot_core.voice import dialog_state as dialog_state_module
from copilot_core.voice.proactive import HintConfig, HintPriority, ProactiveVoiceHints
from copilot_core.voice.voice_handler import VoiceIntentHandler

_LOGGER = logging.getLogger(__name__)
_EXTENSION_KEY = "copilot_core.voice_runtime"


class VoiceRuntimeAccess:
    """Shared runtime/service access seam for voice routes."""

    def __init__(self, app: Flask, services: Optional[dict[str, Any]] = None):
        self._app = app
        self._services = services or {}
        self._intent_handler: Optional[VoiceIntentHandler] = None
        self._context_builder: Optional[VoiceContextBuilder] = None
        self._context_runtime: Optional[VoiceContextRuntime] = None
        self._stt_engine: Optional[WhisperSTT] = None
        self._tts_engine: Optional[PiperTTS] = None
        self._nlu_engine: Optional[NLUEngine] = None
        self._proactive_hints: Optional[ProactiveVoiceHints] = None
        self._command_router: Optional[VoiceCommandRouter] = None
        self._command_flow: Optional[VoiceCommandFlow] = None
        self._dialog_flow: Optional[VoiceDialogFlow] = None
        self._dialog_machine: Any = None
        self._generated_audio_cache: Optional[MutableMapping[str, str]] = None

    def _get_override(self, service_key: str, *, legacy_attr: Optional[str] = None) -> Any:
        override = self._services.get(service_key)
        if override is not None:
            return override
        if legacy_attr:
            app_dict = getattr(self._app, "__dict__", {})
            if legacy_attr in app_dict:
                return app_dict[legacy_attr]
        return None

    def _build_default_mood_engine(self) -> Any:
        mood_engine = self._get_override("voice_mood_engine")
        if mood_engine is not None:
            return mood_engine

        try:
            from copilot_core.mood.engine import MoodConfig, MoodEngine, ZoneConfig

            zone_config = ZoneConfig(
                name="wohnzimmer",
                motion_entities=["binary_sensor.wohnzimmer_motion"],
                light_entities=["light.wohnzimmer"],
                media_entities=["media_player.wohnzimmer"],
                illuminance_entity="sensor.wohnzimmer_illuminance",
            )
            mood_config = MoodConfig(zones={"wohnzimmer": zone_config})
            return MoodEngine(mood_config)
        except Exception as exc:
            _LOGGER.warning("Failed to initialize mood engine for voice runtime: %s", exc)
            return None

    def get_intent_handler(self) -> VoiceIntentHandler:
        if self._intent_handler is None:
            override = self._get_override("voice_intent_handler", legacy_attr="_voice_intent_handler")
            if override is not None:
                self._intent_handler = override
            else:
                habitus_service = self._get_override("voice_habitus_service")
                if habitus_service is None:
                    habitus_service = self._services.get("habitus_service")
                if habitus_service is None and hasattr(self._app, "_habitus_service"):
                    habitus_service = getattr(self._app, "_habitus_service")

                self._intent_handler = VoiceIntentHandler(
                    mood_engine=self._build_default_mood_engine(),
                    habitus_service=habitus_service,
                    default_language="de",
                )
        return self._intent_handler

    def get_context_builder(self) -> VoiceContextBuilder:
        if self._context_builder is None:
            override = self._get_override("voice_context_builder", legacy_attr="_voice_context_builder")
            self._context_builder = override or VoiceContextBuilder()
        return self._context_builder

    def get_context_runtime(self) -> VoiceContextRuntime:
        if self._context_runtime is None:
            override = self._get_override("voice_context_runtime", legacy_attr="_voice_context_runtime")
            if override is not None:
                self._context_runtime = override
            else:
                intent_handler = self.get_intent_handler()
                self._context_runtime = VoiceContextRuntime(
                    mood_engine=getattr(intent_handler, "mood_engine", None),
                    habitus_service=getattr(intent_handler, "habitus_service", None),
                )
        return self._context_runtime

    def get_stt_engine(self) -> WhisperSTT:
        if self._stt_engine is None:
            override = self._get_override("voice_stt_engine", legacy_attr="_voice_stt_engine")
            self._stt_engine = override or _create_stt_engine()
        return self._stt_engine

    def get_tts_engine(self) -> PiperTTS:
        if self._tts_engine is None:
            override = self._get_override("voice_tts_engine", legacy_attr="_voice_tts_engine")
            self._tts_engine = override or _create_tts_engine()
        return self._tts_engine

    def get_nlu_engine(self) -> NLUEngine:
        if self._nlu_engine is None:
            override = self._get_override("voice_nlu_engine", legacy_attr="_voice_nlu_engine")
            self._nlu_engine = override or _create_nlu_engine()
        return self._nlu_engine

    def get_generated_audio_cache(self) -> MutableMapping[str, str]:
        if self._generated_audio_cache is None:
            override = self._get_override("voice_generated_audio", legacy_attr="_voice_generated_audio")
            self._generated_audio_cache = override or {}
        return self._generated_audio_cache

    def cache_generated_audio(self, audio_path: str) -> str:
        path = Path(audio_path)
        audio_id = path.stem or f"tts_{int(time.time() * 1000)}"
        self.get_generated_audio_cache()[audio_id] = str(path)
        return audio_id

    def get_proactive_hints(self) -> ProactiveVoiceHints:
        if self._proactive_hints is None:
            override = self._get_override("voice_proactive_hints", legacy_attr="_voice_proactive_hints")
            if override is not None:
                self._proactive_hints = override
            else:
                intent_handler = self.get_intent_handler()
                config = HintConfig(
                    enabled_types=[
                        hint_type for hint_type in __import__(
                            "copilot_core.voice.proactive", fromlist=["HintType"]
                        ).HintType
                    ],
                    min_priority=HintPriority.LOW,
                    hint_cooldown_seconds=300,
                    max_hints_per_hour=6,
                )
                self._proactive_hints = ProactiveVoiceHints(
                    mood_engine=intent_handler.mood_engine,
                    habitus_service=intent_handler.habitus_service,
                    config=config,
                )
        return self._proactive_hints

    def get_command_router(self) -> VoiceCommandRouter:
        if self._command_router is None:
            override = self._get_override("voice_command_router", legacy_attr="_voice_command_router")
            self._command_router = override or VoiceCommandRouter(self.get_intent_handler())
        return self._command_router

    def get_command_flow(self) -> VoiceCommandFlow:
        if self._command_flow is None:
            override = self._get_override("voice_command_flow", legacy_attr="_voice_command_flow")
            if override is not None:
                self._command_flow = override
            else:
                # Build command_flow with dialog_flow injected for transition delegation
                dialog_flow = self.get_dialog_flow()
                self._command_flow = VoiceCommandFlow(
                    intent_handler=self.get_intent_handler(),
                    context_builder=self.get_context_builder(),
                    context_runtime=self.get_context_runtime(),
                    command_router=self.get_command_router(),
                    dialog_machine=self.get_dialog_machine(),
                    dialog_flow=dialog_flow,
                )
        return self._command_flow

    def get_dialog_flow(self) -> VoiceDialogFlow:
        if self._dialog_flow is None:
            override = self._get_override("voice_dialog_flow", legacy_attr="_voice_dialog_flow")
            if override is not None:
                self._dialog_flow = override
            else:
                self._dialog_flow = VoiceDialogFlow(dialog_machine=self.get_dialog_machine())
        return self._dialog_flow

    def _get_runtime_data_dir(self) -> Optional[str]:
        config = self._services.get("config")
        if isinstance(config, dict):
            data_dir = config.get("data_dir")
            if isinstance(data_dir, str) and data_dir.strip():
                return data_dir

        cfg = self._app.config.get("COPILOT_CFG") if hasattr(self._app, "config") else None
        data_dir = getattr(cfg, "data_dir", None)
        if isinstance(data_dir, str) and data_dir.strip():
            return data_dir

        return None

    def get_dialog_machine(self):
        if self._dialog_machine is None:
            override = self._get_override("voice_dialog_machine", legacy_attr="_voice_dialog_machine")
            if override is not None:
                self._dialog_machine = override
            else:
                self._dialog_machine = dialog_state_module.get_dialog_machine(
                    data_dir=self._get_runtime_data_dir()
                )
        return self._dialog_machine


def init_voice_runtime(
    app: Flask,
    services: Optional[dict[str, Any]] = None,
    *,
    runtime: Optional[VoiceRuntimeAccess] = None,
) -> VoiceRuntimeAccess:
    """Install the voice runtime seam on a Flask app."""
    if not hasattr(app, "extensions"):
        app.extensions = {}
    installed = runtime or VoiceRuntimeAccess(app, services=services)
    app.extensions[_EXTENSION_KEY] = installed
    return installed


def get_voice_runtime(app: Optional[Flask] = None) -> VoiceRuntimeAccess:
    """Resolve the installed voice runtime seam for the current app."""
    flask_app = app or current_app
    runtime = getattr(flask_app, "extensions", {}).get(_EXTENSION_KEY)
    if runtime is not None:
        return runtime

    services = flask_app.config.get("COPILOT_SERVICES")
    injected_runtime = services.get("voice_runtime") if isinstance(services, dict) else None
    if injected_runtime is not None:
        return init_voice_runtime(flask_app, services=services, runtime=injected_runtime)

    return init_voice_runtime(flask_app, services=services)
