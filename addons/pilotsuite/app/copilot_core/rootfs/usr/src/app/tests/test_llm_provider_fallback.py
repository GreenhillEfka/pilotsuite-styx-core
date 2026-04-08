"""Tests for LLM provider model fallback behavior."""

from __future__ import annotations

from typing import Any

import pytest
import requests as http_requests

from copilot_core.llm_provider import LLMProvider


class _Resp:
    def __init__(self, status_code: int, text: str, data: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self.text = text
        self._data = data or {}

    def json(self) -> dict[str, Any]:
        return self._data


def test_requested_model_falls_back_to_configured_ollama_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:11435")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:4b")
    monkeypatch.delenv("CLOUD_API_URL", raising=False)
    monkeypatch.delenv("CLOUD_API_KEY", raising=False)

    calls: list[str] = []

    def _fake_post(url: str, json: dict[str, Any], timeout: int):  # noqa: A002
        calls.append(str(json.get("model")))
        model = json.get("model")
        if model == "gpt-4o-mini":
            return _Resp(404, '{"error":"model \\"gpt-4o-mini\\" not found"}')
        if model == "qwen3:4b":
            return _Resp(200, "", {"message": {"content": "ok from qwen"}})
        return _Resp(500, "unexpected")

    monkeypatch.setattr("copilot_core.llm_provider.http_requests.post", _fake_post)

    provider = LLMProvider()
    result = provider.chat(messages=[{"role": "user", "content": "hi"}], model="gpt-4o-mini")

    assert result["provider"] == "ollama"
    assert result["content"] == "ok from qwen"
    assert calls == ["qwen3:4b"]


def test_offline_message_reports_missing_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:11435")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:4b")
    monkeypatch.delenv("CLOUD_API_URL", raising=False)
    monkeypatch.delenv("CLOUD_API_KEY", raising=False)

    def _fake_post(url: str, json: dict[str, Any], timeout: int):  # noqa: A002
        model = json.get("model")
        return _Resp(404, f'{{"error":"model \\"{model}\\" not found"}}')

    monkeypatch.setattr("copilot_core.llm_provider.http_requests.post", _fake_post)

    provider = LLMProvider()
    result = provider.chat(messages=[{"role": "user", "content": "hi"}], model="gpt-4o-mini")

    assert result["provider"] == "none"
    assert "Modell 'qwen3:4b' nicht installiert" in result["content"]


def test_cloud_used_for_explicit_external_model_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:11435")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:4b")
    monkeypatch.setenv("CLOUD_API_URL", "https://api.example.com/v1")
    monkeypatch.setenv("CLOUD_API_KEY", "sk-test")
    monkeypatch.setenv("CLOUD_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("PREFER_LOCAL", "true")

    ollama_models: list[str] = []
    cloud_calls: list[str] = []

    def _fake_post(url: str, json: dict[str, Any], timeout: int, headers=None):  # noqa: A002
        if url.endswith("/api/chat"):
            model = str(json.get("model", ""))
            ollama_models.append(model)
            return _Resp(404, f'{{"error":"model \\"{model}\\" not found"}}')
        if url.endswith("/chat/completions"):
            cloud_calls.append(str(json.get("model")))
            return _Resp(200, "", {"choices": [{"message": {"content": "ok from cloud"}}]})
        return _Resp(500, "unexpected")

    monkeypatch.setattr("copilot_core.llm_provider.http_requests.post", _fake_post)

    provider = LLMProvider()
    result = provider.chat(messages=[{"role": "user", "content": "hi"}], model="gpt-4o-mini")

    assert result["provider"] == "cloud"
    assert result["content"] == "ok from cloud"
    assert ollama_models == []
    assert cloud_calls == ["gpt-4o-mini"]


def test_ollama_cloud_url_is_normalized_to_v1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:11435")
    monkeypatch.setenv("CLOUD_API_URL", "https://ollama.com/")
    monkeypatch.setenv("CLOUD_API_KEY", "sk-test")
    monkeypatch.delenv("CLOUD_MODEL", raising=False)
    monkeypatch.setenv("PREFER_LOCAL", "false")

    cloud_urls: list[str] = []
    cloud_models: list[str] = []

    def _fake_post(url: str, json: dict[str, Any], timeout: int, headers=None):  # noqa: A002
        cloud_urls.append(url)
        cloud_models.append(str(json.get("model", "")))
        return _Resp(200, "", {"choices": [{"message": {"content": "ok from cloud"}}]})

    monkeypatch.setattr("copilot_core.llm_provider.http_requests.post", _fake_post)

    provider = LLMProvider()
    result = provider.chat(messages=[{"role": "user", "content": "hi"}])

    assert result["provider"] == "cloud"
    assert result["content"] == "ok from cloud"
    assert cloud_urls == ["https://ollama.com/v1/chat/completions"]
    assert cloud_models == ["gpt-oss:20b"]


def test_ollama_cloud_coerces_openai_model_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:11435")
    monkeypatch.setenv("CLOUD_API_URL", "https://ollama.com/v1")
    monkeypatch.setenv("CLOUD_API_KEY", "sk-test")
    monkeypatch.setenv("CLOUD_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("PREFER_LOCAL", "false")

    cloud_models: list[str] = []

    def _fake_post(url: str, json: dict[str, Any], timeout: int, headers=None):  # noqa: A002
        cloud_models.append(str(json.get("model", "")))
        return _Resp(200, "", {"choices": [{"message": {"content": "ok from cloud"}}]})

    monkeypatch.setattr("copilot_core.llm_provider.http_requests.post", _fake_post)

    provider = LLMProvider()
    result = provider.chat(messages=[{"role": "user", "content": "hi"}], model="gpt-4o-mini")

    assert result["provider"] == "cloud"
    assert result["content"] == "ok from cloud"
    assert cloud_models == ["gpt-oss:20b"]


def test_non_ollama_cloud_keeps_generic_default_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:11435")
    monkeypatch.setenv("CLOUD_API_URL", "https://api.example.com/v1")
    monkeypatch.setenv("CLOUD_API_KEY", "sk-test")
    monkeypatch.delenv("CLOUD_MODEL", raising=False)
    monkeypatch.setenv("PREFER_LOCAL", "false")

    cloud_models: list[str] = []

    def _fake_post(url: str, json: dict[str, Any], timeout: int, headers=None):  # noqa: A002
        cloud_models.append(str(json.get("model", "")))
        return _Resp(200, "", {"choices": [{"message": {"content": "ok from cloud"}}]})

    monkeypatch.setattr("copilot_core.llm_provider.http_requests.post", _fake_post)

    provider = LLMProvider()
    result = provider.chat(messages=[{"role": "user", "content": "hi"}])

    assert result["provider"] == "cloud"
    assert result["content"] == "ok from cloud"
    assert cloud_models == ["gpt-4o-mini"]


def test_cloud_url_with_chat_completions_suffix_is_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:11435")
    monkeypatch.setenv("CLOUD_API_URL", "https://api.example.com/v1/chat/completions")
    monkeypatch.setenv("CLOUD_API_KEY", "sk-test")
    monkeypatch.setenv("PREFER_LOCAL", "false")

    cloud_urls: list[str] = []

    def _fake_post(url: str, json: dict[str, Any], timeout: int, headers=None):  # noqa: A002
        cloud_urls.append(url)
        return _Resp(200, "", {"choices": [{"message": {"content": "ok from cloud"}}]})

    monkeypatch.setattr("copilot_core.llm_provider.http_requests.post", _fake_post)

    provider = LLMProvider()
    result = provider.chat(messages=[{"role": "user", "content": "hi"}])

    assert result["provider"] == "cloud"
    assert cloud_urls == ["https://api.example.com/v1/chat/completions"]


def test_cloud_url_without_key_returns_offline_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:11435")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:4b")
    monkeypatch.setenv("CLOUD_API_URL", "https://api.example.com/v1")
    monkeypatch.delenv("CLOUD_API_KEY", raising=False)
    monkeypatch.setenv("PREFER_LOCAL", "true")

    def _fake_post(url: str, json: dict[str, Any], timeout: int):  # noqa: A002
        raise http_requests.exceptions.ConnectionError("down")

    monkeypatch.setattr("copilot_core.llm_provider.http_requests.post", _fake_post)

    provider = LLMProvider()
    result = provider.chat(messages=[{"role": "user", "content": "hi"}], model="pilotsuite")

    assert isinstance(result, dict)
    assert result["provider"] == "none"
    assert "Cloud-API nicht konfiguriert" in result["content"]


def test_alias_model_maps_to_local_configured_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:11435")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:4b")
    monkeypatch.delenv("CLOUD_API_URL", raising=False)
    monkeypatch.delenv("CLOUD_API_KEY", raising=False)

    calls: list[str] = []

    def _fake_post(url: str, json: dict[str, Any], timeout: int):  # noqa: A002
        calls.append(str(json.get("model")))
        return _Resp(200, "", {"message": {"content": "ok"}})

    monkeypatch.setattr("copilot_core.llm_provider.http_requests.post", _fake_post)

    provider = LLMProvider()
    result = provider.chat(messages=[{"role": "user", "content": "hi"}], model="pilotsuite")

    assert result["provider"] == "ollama"
    assert result["content"] == "ok"
    assert calls == ["qwen3:4b"]


def test_cloud_like_ollama_config_is_forced_to_local_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:11435")
    monkeypatch.setenv("OLLAMA_MODEL", "gpt-4o-mini")
    monkeypatch.delenv("CLOUD_API_URL", raising=False)
    monkeypatch.delenv("CLOUD_API_KEY", raising=False)

    calls: list[str] = []

    def _fake_post(url: str, json: dict[str, Any], timeout: int):  # noqa: A002
        calls.append(str(json.get("model")))
        model = str(json.get("model"))
        if model == "qwen3:0.6b":
            return _Resp(200, "", {"message": {"content": "ok fallback"}})
        return _Resp(404, f'{{"error":"model \\"{model}\\" not found"}}')

    monkeypatch.setattr("copilot_core.llm_provider.http_requests.post", _fake_post)

    provider = LLMProvider()
    result = provider.chat(messages=[{"role": "user", "content": "hi"}], model="pilotsuite")
    status = provider.status()

    assert result["provider"] == "ollama"
    assert result["content"] == "ok fallback"
    assert calls == ["qwen3:0.6b"]
    assert status["ollama_model"] == "qwen3:0.6b"
    assert status["ollama_model_configured"] == "gpt-4o-mini"
    assert status["ollama_model_overridden"] is True


def test_update_routing_switches_primary_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:11435")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:0.6b")
    monkeypatch.setenv("CLOUD_API_URL", "https://api.example.com/v1")
    monkeypatch.setenv("CLOUD_API_KEY", "sk-test")
    monkeypatch.setenv("CLOUD_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("LLM_RUNTIME_SETTINGS_PATH", "/tmp/llm_provider_routing_test.json")

    provider = LLMProvider()
    before = provider.status()
    assert before["primary_provider"] == "offline"

    after = provider.update_routing(
        primary_provider="cloud",
        secondary_provider="offline",
        offline_model="qwen3:4b",
        cloud_model="gpt-oss:20b",
        persist=False,
    )

    assert after["primary_provider"] == "cloud"
    assert after["secondary_provider"] == "offline"
    assert after["ollama_model"] == "qwen3:4b"
    assert after["cloud_model"] == "gpt-oss:20b"
