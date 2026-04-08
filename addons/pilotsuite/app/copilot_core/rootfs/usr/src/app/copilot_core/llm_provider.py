"""
LLM Provider abstraction for PilotSuite.

Supports multiple backends with automatic fallback:
  1. Ollama  (offline/local)
  2. OpenAI-compatible API (cloud)

Config (addon options -> conversation section):
  ollama_url:       http://localhost:11434
  ollama_model:     qwen3:0.6b
  cloud_api_url:    https://ollama.com/v1  (or another OpenAI-compatible /v1 endpoint)
  cloud_api_key:    sk-...
  cloud_model:      gpt-oss:20b / gpt-4o-mini (provider specific)
  prefer_local:     true  (legacy toggle, maps to primary_provider=offline)

Runtime routing (stored in /data/llm_runtime_settings.json):
  primary_provider: offline|cloud
  secondary_provider: offline|cloud
  offline_model: local model id
  cloud_model: cloud model id
"""

from __future__ import annotations

import json
import logging
import os
import time
from urllib.parse import urlparse

import requests as http_requests

logger = logging.getLogger(__name__)

# Retry settings for transient failures
_MAX_RETRIES = 2
_RETRY_BASE_DELAY = 1.0  # seconds
_CLOUD_MODEL_PREFIXES = (
    "gpt-",
    "o1",
    "o3",
    "claude",
    "gemini",
    "deepseek",
)

_PROVIDER_OFFLINE = "offline"
_PROVIDER_CLOUD = "cloud"

_DEFAULT_OLLAMA_MODEL = "qwen3:0.6b"
_DEFAULT_CLOUD_MODEL = "gpt-4o-mini"
_DEFAULT_OLLAMA_CLOUD_MODEL = "gpt-oss:20b"
_DEFAULT_OLLAMA_CLOUD_MODELS = ("gpt-oss:120b", "gpt-oss:20b")
_DEFAULT_OFFLINE_MODELS = ("qwen3:0.6b", "qwen3:4b", "llama3.2:3b", "mistral:7b")
_RUNTIME_SETTINGS_PATH = "/data/llm_runtime_settings.json"
_CATALOG_CACHE_TTL_S = 45.0

_PRIMARY_MODEL_ALIASES = {"", "pilotsuite", "default", "auto", "primary"}
_SECONDARY_MODEL_ALIASES = {"secondary", "fallback"}
_OFFLINE_MODEL_ALIASES = {"offline", "local", "ollama"}
_CLOUD_MODEL_ALIASES = {"cloud", "remote"}


class LLMProvider:
    """Unified chat provider with explicit primary/secondary routing."""

    def __init__(self):
        self._settings_path = os.environ.get("LLM_RUNTIME_SETTINGS_PATH", _RUNTIME_SETTINGS_PATH)
        self._catalog_cache: dict[str, dict] = {
            _PROVIDER_OFFLINE: {"models": [], "ts": 0.0},
            _PROVIDER_CLOUD: {"models": [], "ts": 0.0},
        }
        self._load_config()

    def _load_config(self):
        """Load config from env + runtime routing overrides."""
        self.ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        configured_ollama_model = str(os.environ.get("OLLAMA_MODEL", _DEFAULT_OLLAMA_MODEL) or "").strip()
        if not configured_ollama_model:
            configured_ollama_model = _DEFAULT_OLLAMA_MODEL

        self.cloud_api_url = str(os.environ.get("CLOUD_API_URL", "") or "").strip()
        self.cloud_api_key = os.environ.get("CLOUD_API_KEY", "")
        configured_cloud_model = str(os.environ.get("CLOUD_MODEL", "") or "").strip()
        self.timeout = int(os.environ.get("LLM_TIMEOUT", "120"))
        self._last_ollama_issue = "unknown"
        self.ollama_model_configured = configured_ollama_model
        self.ollama_model_overridden = False

        runtime = self._load_runtime_overrides()
        runtime_offline_model = str(runtime.get("offline_model", "") or "").strip()
        runtime_cloud_model = str(runtime.get("cloud_model", "") or "").strip()

        self.ollama_model = runtime_offline_model or configured_ollama_model
        if self._is_cloud_model_name(self.ollama_model):
            self.ollama_model = _DEFAULT_OLLAMA_MODEL
            self.ollama_model_overridden = True
            logger.warning(
                "Configured OLLAMA_MODEL '%s' looks cloud-only; forcing local fallback '%s'",
                configured_ollama_model,
                self.ollama_model,
            )

        self.cloud_model = runtime_cloud_model or configured_cloud_model
        if not self.cloud_model:
            self.cloud_model = self._default_cloud_model_for_url(self.cloud_api_url)

        prefer_local_env = os.environ.get("PREFER_LOCAL", "true").lower() == "true"
        default_primary = _PROVIDER_OFFLINE if prefer_local_env else _PROVIDER_CLOUD
        self.primary_provider = self._normalize_provider(runtime.get("primary_provider"), default_primary)
        self.secondary_provider = self._normalize_provider(
            runtime.get("secondary_provider"),
            _PROVIDER_CLOUD if self.primary_provider == _PROVIDER_OFFLINE else _PROVIDER_OFFLINE,
        )
        if self.secondary_provider == self.primary_provider:
            self.secondary_provider = (
                _PROVIDER_CLOUD if self.primary_provider == _PROVIDER_OFFLINE else _PROVIDER_OFFLINE
            )

        # If cloud is not configured, always prefer offline first.
        if self.primary_provider == _PROVIDER_CLOUD and not self.has_cloud_fallback:
            self.primary_provider = _PROVIDER_OFFLINE
            self.secondary_provider = _PROVIDER_CLOUD

        # Legacy compatibility field used by status endpoint/tests.
        self.prefer_local = self.primary_provider == _PROVIDER_OFFLINE

    def _load_runtime_overrides(self) -> dict:
        """Read runtime routing overrides from disk (best effort)."""
        try:
            with open(self._settings_path, "r", encoding="utf-8") as fh:
                data = json.load(fh) or {}
            if isinstance(data, dict):
                return data
        except FileNotFoundError:
            return {}
        except Exception:
            logger.warning("Could not load LLM runtime overrides from %s", self._settings_path)
        return {}

    def _save_runtime_overrides(self, overrides: dict) -> None:
        """Persist runtime routing overrides to disk (best effort)."""
        try:
            folder = os.path.dirname(self._settings_path)
            if folder:
                os.makedirs(folder, exist_ok=True)
            with open(self._settings_path, "w", encoding="utf-8") as fh:
                json.dump(overrides, fh, ensure_ascii=False, indent=2, sort_keys=True)
        except Exception:
            logger.warning("Could not persist LLM runtime overrides to %s", self._settings_path)

    def reload_config(self):
        """Explicitly reload config from environment/runtime storage."""
        self._load_config()
        self._catalog_cache[_PROVIDER_OFFLINE] = {"models": [], "ts": 0.0}
        self._catalog_cache[_PROVIDER_CLOUD] = {"models": [], "ts": 0.0}
        logger.info("LLM provider config reloaded")

    def update_routing(
        self,
        *,
        primary_provider: str | None = None,
        secondary_provider: str | None = None,
        offline_model: str | None = None,
        cloud_model: str | None = None,
        persist: bool = True,
    ) -> dict:
        """Update routing/model config at runtime, optionally persisted on disk."""
        runtime = self._load_runtime_overrides()

        if primary_provider is not None:
            runtime["primary_provider"] = self._normalize_provider(primary_provider, self.primary_provider)
        if secondary_provider is not None:
            runtime["secondary_provider"] = self._normalize_provider(secondary_provider, self.secondary_provider)

        if offline_model is not None:
            value = str(offline_model or "").strip()
            if value:
                runtime["offline_model"] = value
            else:
                runtime.pop("offline_model", None)

        if cloud_model is not None:
            value = str(cloud_model or "").strip()
            if value:
                runtime["cloud_model"] = value
            else:
                runtime.pop("cloud_model", None)

        os.environ["PREFER_LOCAL"] = "true" if runtime.get("primary_provider", self.primary_provider) == _PROVIDER_OFFLINE else "false"
        if "offline_model" in runtime:
            os.environ["OLLAMA_MODEL"] = str(runtime["offline_model"])
        if "cloud_model" in runtime:
            os.environ["CLOUD_MODEL"] = str(runtime["cloud_model"])

        if persist:
            self._save_runtime_overrides(runtime)

        self.reload_config()
        return self.status()

    @property
    def active_model(self) -> str:
        return self._default_model_for_provider(self.primary_provider)

    @property
    def has_cloud_fallback(self) -> bool:
        return bool(self.cloud_api_url and self.cloud_api_key)

    def status(self) -> dict:
        """Return provider/routing status info."""
        ollama_ok = self._ping_ollama()
        active_provider = "none"
        for provider in (self.primary_provider, self.secondary_provider):
            if provider == _PROVIDER_OFFLINE and ollama_ok:
                active_provider = "ollama"
                break
            if provider == _PROVIDER_CLOUD and self.has_cloud_fallback:
                active_provider = "cloud"
                break

        return {
            "ollama_available": ollama_ok,
            "ollama_url": self.ollama_url,
            "ollama_model": self.ollama_model,
            "ollama_model_configured": self.ollama_model_configured,
            "ollama_model_overridden": self.ollama_model_overridden,
            "cloud_configured": self.has_cloud_fallback,
            "cloud_api_url": self.cloud_api_url or None,
            "cloud_model": self.cloud_model or None,
            "prefer_local": self.prefer_local,
            "active_provider": active_provider,
            "primary_provider": self.primary_provider,
            "secondary_provider": self.secondary_provider,
            "primary_model": self._default_model_for_provider(self.primary_provider),
            "secondary_model": self._default_model_for_provider(self.secondary_provider),
            "routing_runtime_path": self._settings_path,
        }

    def model_catalog(self, *, force_refresh: bool = False) -> dict:
        """Return offline/cloud model lists for dashboard selectors."""
        offline_models = self._get_offline_models(force_refresh=force_refresh)
        cloud_models = self._get_cloud_models(force_refresh=force_refresh)
        return {
            "offline": {
                "models": offline_models,
                "active_model": self.ollama_model,
                "recommended": list(_DEFAULT_OFFLINE_MODELS),
            },
            "cloud": {
                "models": cloud_models,
                "active_model": self.cloud_model,
                "recommended": self._recommended_cloud_models(),
                "configured": self.has_cloud_fallback,
            },
            "routing": {
                "primary_provider": self.primary_provider,
                "secondary_provider": self.secondary_provider,
            },
        }

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def _normalize_provider(self, value: object, default: str) -> str:
        text = str(value or "").strip().lower()
        if text in {"offline", "local", "ollama"}:
            return _PROVIDER_OFFLINE
        if text in {"cloud", "remote"}:
            return _PROVIDER_CLOUD
        return default

    def _default_model_for_provider(self, provider: str) -> str:
        if provider == _PROVIDER_CLOUD:
            return str(self.cloud_model or self._default_cloud_model_for_url(self.cloud_api_url))
        return str(self.ollama_model or _DEFAULT_OLLAMA_MODEL)

    def _default_cloud_model_for_url(self, raw_url: str) -> str:
        base_url = self._normalize_cloud_base_url(raw_url)
        if self._is_ollama_cloud_host(base_url):
            return _DEFAULT_OLLAMA_CLOUD_MODEL
        return _DEFAULT_CLOUD_MODEL

    def _build_routing_targets(self, requested_model: str | None) -> list[tuple[str, str]]:
        request = str(requested_model or "").strip()
        lowered = request.lower()

        def _chain(primary: str, secondary: str) -> list[tuple[str, str]]:
            return [
                (primary, self._default_model_for_provider(primary)),
                (secondary, self._default_model_for_provider(secondary)),
            ]

        raw_targets: list[tuple[str, str]] = []

        if lowered in _SECONDARY_MODEL_ALIASES:
            raw_targets.extend(_chain(self.secondary_provider, self.primary_provider))
        elif lowered.startswith("offline:") or lowered.startswith("ollama:"):
            model = request.split(":", 1)[1].strip()
            raw_targets.append((_PROVIDER_OFFLINE, model or self.ollama_model))
            raw_targets.append((_PROVIDER_CLOUD, self.cloud_model))
        elif lowered.startswith("cloud:"):
            model = request.split(":", 1)[1].strip()
            raw_targets.append((_PROVIDER_CLOUD, model or self.cloud_model))
            raw_targets.append((_PROVIDER_OFFLINE, self.ollama_model))
        elif lowered in _OFFLINE_MODEL_ALIASES:
            raw_targets.extend(_chain(_PROVIDER_OFFLINE, _PROVIDER_CLOUD))
        elif lowered in _CLOUD_MODEL_ALIASES:
            raw_targets.extend(_chain(_PROVIDER_CLOUD, _PROVIDER_OFFLINE))
        elif lowered in _PRIMARY_MODEL_ALIASES:
            raw_targets.extend(_chain(self.primary_provider, self.secondary_provider))
        elif request and self._is_cloud_model_name(request):
            raw_targets.append((_PROVIDER_CLOUD, request))
            raw_targets.append((_PROVIDER_OFFLINE, self.ollama_model))
        elif request:
            raw_targets.append((_PROVIDER_OFFLINE, request))
            raw_targets.append((_PROVIDER_CLOUD, self.cloud_model))
        else:
            raw_targets.extend(_chain(self.primary_provider, self.secondary_provider))

        resolved: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for provider, model in raw_targets:
            p = self._normalize_provider(provider, _PROVIDER_OFFLINE)
            m = str(model or "").strip() or self._default_model_for_provider(p)
            if p == _PROVIDER_CLOUD and not self.has_cloud_fallback:
                continue
            key = (p, m)
            if key in seen:
                continue
            seen.add(key)
            resolved.append(key)
        return resolved

    def chat(
        self,
        messages: list,
        tools: list = None,
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
    ) -> dict:
        """Send chat request with configurable primary/secondary fallback."""
        for provider, selected_model in self._build_routing_targets(model):
            if provider == _PROVIDER_OFFLINE:
                result = self._try_ollama(messages, tools, selected_model, temperature, max_tokens)
            else:
                result = self._try_cloud(messages, tools, selected_model, temperature, max_tokens)
            if result is not None:
                return result
        return {"content": self._offline_msg(), "tool_calls": None, "provider": "none"}

    # ------------------------------------------------------------------
    # Model catalog
    # ------------------------------------------------------------------

    def _get_offline_models(self, *, force_refresh: bool = False) -> list[str]:
        now = time.monotonic()
        cache = self._catalog_cache[_PROVIDER_OFFLINE]
        if not force_refresh and cache["models"] and (now - cache["ts"]) < _CATALOG_CACHE_TTL_S:
            return list(cache["models"])

        models: list[str] = []
        try:
            resp = http_requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                for model in resp.json().get("models", []):
                    name = str(model.get("name", "")).strip()
                    if name and name not in models:
                        models.append(name)
        except Exception:
            logger.debug("Could not list Ollama models", exc_info=True)

        for model in (self.ollama_model, *list(_DEFAULT_OFFLINE_MODELS)):
            model_name = str(model or "").strip()
            if model_name and model_name not in models:
                models.append(model_name)

        cache["models"] = list(models)
        cache["ts"] = now
        return models

    def _recommended_cloud_models(self) -> list[str]:
        base_url = self._normalize_cloud_base_url(self.cloud_api_url)
        if self._is_ollama_cloud_host(base_url):
            models = list(_DEFAULT_OLLAMA_CLOUD_MODELS)
            if self.cloud_model and self.cloud_model not in models:
                models.append(self.cloud_model)
            return models
        models = []
        if self.cloud_model:
            models.append(self.cloud_model)
        if _DEFAULT_CLOUD_MODEL not in models:
            models.append(_DEFAULT_CLOUD_MODEL)
        return models

    def _fetch_cloud_models(self) -> list[str]:
        if not self.has_cloud_fallback:
            return []

        base_url = self._normalize_cloud_base_url(self.cloud_api_url).rstrip("/")
        if not base_url:
            return []

        models_base = base_url
        if models_base.endswith("/chat/completions"):
            models_base = models_base[: -len("/chat/completions")]
        url = models_base if models_base.endswith("/models") else f"{models_base}/models"
        headers = {"Authorization": f"Bearer {self.cloud_api_key}"}
        try:
            resp = http_requests.get(url, headers=headers, timeout=8)
            if resp.status_code != 200:
                return []
            payload = resp.json()
            models: list[str] = []
            data = payload.get("data") if isinstance(payload, dict) else payload
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        model = str(item.get("id", "")).strip()
                    else:
                        model = str(item).strip()
                    if model and model not in models:
                        models.append(model)
            return models
        except Exception:
            logger.debug("Could not list cloud models", exc_info=True)
            return []

    def _get_cloud_models(self, *, force_refresh: bool = False) -> list[str]:
        now = time.monotonic()
        cache = self._catalog_cache[_PROVIDER_CLOUD]
        if not force_refresh and cache["models"] and (now - cache["ts"]) < _CATALOG_CACHE_TTL_S:
            return list(cache["models"])

        models = self._fetch_cloud_models()
        for model in self._recommended_cloud_models():
            model_name = str(model or "").strip()
            if model_name and model_name not in models:
                models.append(model_name)

        cache["models"] = list(models)
        cache["ts"] = now
        return models

    # ------------------------------------------------------------------
    # Ollama backend
    # ------------------------------------------------------------------

    def _ping_ollama(self) -> bool:
        try:
            resp = http_requests.get(f"{self.ollama_url}/api/tags", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def _try_ollama(self, messages, tools, model, temperature, max_tokens):
        requested_model = (model or self.ollama_model or "").strip()
        alias_models = {"", "pilotsuite", "default", "auto", "local", "ollama", "primary"}
        candidate_models: list[str] = []
        explicit_cloud_model = self._is_cloud_model_name(requested_model)

        # If a cloud-style model is requested but cloud fallback is unavailable,
        # transparently map to configured local model to avoid repeated 404 noise.
        if explicit_cloud_model and not self.has_cloud_fallback and self.ollama_model:
            candidate_models.append(self.ollama_model)
            logger.info(
                "Requested model '%s' looks cloud-only; using local model '%s' instead",
                requested_model,
                self.ollama_model,
            )
        elif requested_model.lower() in alias_models:
            if self.ollama_model:
                candidate_models.append(self.ollama_model)
        else:
            candidate_models.append(requested_model)
            # Explicit external model requests should fall back to cloud when configured.
            # Only try the configured local model as second chance if no cloud fallback exists.
            if not self.has_cloud_fallback and self.ollama_model and self.ollama_model not in candidate_models:
                candidate_models.append(self.ollama_model)

        if not candidate_models and self.ollama_model:
            candidate_models = [self.ollama_model]

        opts = {}
        if temperature is not None:
            opts["temperature"] = temperature
        if max_tokens is not None:
            opts["num_predict"] = max_tokens

        for i, candidate_model in enumerate(candidate_models):
            should_try_next_model = False
            payload = {"model": candidate_model, "messages": messages, "stream": False}
            if opts:
                payload["options"] = opts
            if tools:
                payload["tools"] = tools

            for attempt in range(_MAX_RETRIES + 1):
                try:
                    resp = http_requests.post(
                        f"{self.ollama_url}/api/chat", json=payload, timeout=self.timeout,
                    )
                    if resp.status_code == 200:
                        self._last_ollama_issue = ""
                        msg = resp.json().get("message", {})
                        logger.info("LLM response via ollama/%s", candidate_model)
                        return {
                            "content": msg.get("content", ""),
                            "tool_calls": msg.get("tool_calls"),
                            "provider": "ollama",
                        }

                    body = (resp.text or "")[:200]
                    if resp.status_code == 404 and "not found" in body.lower():
                        self._last_ollama_issue = f"model_not_found:{candidate_model}"
                        logger.warning("Ollama model not found: %s", candidate_model)
                        should_try_next_model = True
                        break

                    self._last_ollama_issue = f"http_{resp.status_code}"
                    logger.warning("Ollama %s: %s", resp.status_code, body)
                    break
                except http_requests.exceptions.ConnectionError:
                    self._last_ollama_issue = "unreachable"
                    if attempt < _MAX_RETRIES:
                        delay = _RETRY_BASE_DELAY * (2 ** attempt)
                        logger.info(
                            "Ollama connection failed, retry %d/%d in %.1fs",
                            attempt + 1,
                            _MAX_RETRIES,
                            delay,
                        )
                        time.sleep(delay)
                        continue
                    logger.warning("Ollama not reachable at %s after %d retries", self.ollama_url, _MAX_RETRIES)
                    break
                except http_requests.exceptions.Timeout:
                    self._last_ollama_issue = "timeout"
                    logger.warning("Ollama timeout after %ds", self.timeout)
                    break
                except Exception:
                    self._last_ollama_issue = "error"
                    logger.exception("Ollama error")
                    break

            if should_try_next_model and i + 1 < len(candidate_models):
                logger.info(
                    "Falling back from requested model '%s' to configured Ollama model '%s'",
                    requested_model,
                    candidate_models[i + 1],
                )
                continue
            if not should_try_next_model:
                break
        return None

    @staticmethod
    def _is_cloud_model_name(model: str) -> bool:
        """Best-effort detection for cloud-style model identifiers."""
        value = str(model or "").strip().lower()
        if not value:
            return False
        return value.startswith(_CLOUD_MODEL_PREFIXES)

    @staticmethod
    def _is_ollama_cloud_host(url: str) -> bool:
        """Return True if URL targets ollama.com's hosted API."""
        value = str(url or "").strip()
        if not value:
            return False
        try:
            parsed = urlparse(value if "://" in value else f"https://{value}")
        except Exception:
            return False
        host = (parsed.hostname or "").lower()
        return host in {"ollama.com", "www.ollama.com"}

    @classmethod
    def _normalize_cloud_base_url(cls, raw_url: str) -> str:
        """Normalize cloud base URL for OpenAI-style /chat/completions calls."""
        url = str(raw_url or "").strip().rstrip("/")
        if not url:
            return ""
        if url.endswith("/chat/completions"):
            return url[: -len("/chat/completions")]
        if url.endswith("/models"):
            return url[: -len("/models")]
        if not cls._is_ollama_cloud_host(url):
            return url

        # Accept common user inputs for Ollama Cloud and normalize to /v1.
        parsed = urlparse(url if "://" in url else f"https://{url}")
        path = parsed.path.rstrip("/")
        if path in ("", "/api", "/v1"):
            return "https://ollama.com/v1"
        return url

    @classmethod
    def _coerce_cloud_model_for_ollama_cloud(cls, model: str, base_url: str) -> str:
        """Map incompatible OpenAI model names to an Ollama Cloud default."""
        selected = str(model or "").strip()
        if not cls._is_ollama_cloud_host(base_url):
            return selected
        lowered = selected.lower()
        if lowered in {"gpt-4o-mini", "gpt-4o", "gpt-4.1", "gpt-5", "o1", "o3"}:
            return _DEFAULT_OLLAMA_CLOUD_MODEL
        return selected

    # ------------------------------------------------------------------
    # Cloud / OpenAI-compatible backend
    # ------------------------------------------------------------------

    def _try_cloud(self, messages, tools, model, temperature, max_tokens):
        if not self.cloud_api_url or not self.cloud_api_key:
            return None

        base_url = self._normalize_cloud_base_url(self.cloud_api_url)
        if model:
            selected_model = model
        elif self.cloud_model:
            selected_model = self.cloud_model
        elif self._is_ollama_cloud_host(base_url):
            selected_model = _DEFAULT_OLLAMA_CLOUD_MODEL
        else:
            selected_model = _DEFAULT_CLOUD_MODEL
        selected_model = self._coerce_cloud_model_for_ollama_cloud(selected_model, base_url)
        headers = {
            "Authorization": f"Bearer {self.cloud_api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": selected_model, "messages": messages, "stream": False}
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools

        url = base_url
        if not url.endswith("/chat/completions"):
            url = f"{url}/chat/completions"

        try:
            resp = http_requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            if resp.status_code != 200:
                # Sanitize: don't log full response which might echo the API key.
                logger.warning("Cloud API %s (model=%s)", resp.status_code, selected_model)
                return None
            data = resp.json()
            choice = data.get("choices", [{}])[0]
            msg = choice.get("message", {})
            logger.info("LLM response via cloud/%s", selected_model)
            return {
                "content": msg.get("content", ""),
                "tool_calls": msg.get("tool_calls"),
                "provider": "cloud",
            }
        except Exception:
            logger.exception("Cloud API error (url=%s)", url)
            return None

    def _offline_msg(self) -> str:
        issue = str(getattr(self, "_last_ollama_issue", "") or "")
        if issue.startswith("model_not_found:"):
            model = issue.split(":", 1)[1]
            ollama_state = f"Ollama erreichbar, aber Modell '{model}' nicht installiert"
        elif issue == "timeout":
            ollama_state = f"Ollama ({self.ollama_url}) antwortet nicht rechtzeitig"
        elif issue in ("unreachable", "error", "unknown"):
            ollama_state = f"Ollama ({self.ollama_url}) nicht erreichbar"
        elif issue.startswith("http_"):
            ollama_state = f"Ollama ({self.ollama_url}) liefert {issue.replace('_', ' ').upper()}"
        else:
            ollama_state = f"Ollama ({self.ollama_url}) nicht erreichbar"

        return (
            f"Kein LLM-Provider verfuegbar. {ollama_state}"
            + (", Cloud-API nicht konfiguriert." if not self.has_cloud_fallback
               else ", Cloud-API ebenfalls nicht erreichbar.")
            + " Bitte pruefe die Addon-Konfiguration."
        )
