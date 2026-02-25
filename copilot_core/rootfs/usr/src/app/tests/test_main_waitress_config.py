"""Tests for waitress runtime tuning in main.py."""

from __future__ import annotations

import importlib


def test_waitress_config_defaults(monkeypatch):
    for key in (
        "WAITRESS_THREADS",
        "WAITRESS_CONNECTION_LIMIT",
        "WAITRESS_BACKLOG",
        "WAITRESS_CHANNEL_TIMEOUT",
        "WAITRESS_CLEANUP_INTERVAL",
    ):
        monkeypatch.delenv(key, raising=False)

    main = importlib.import_module("main")
    cfg = main._build_waitress_server_config()

    assert cfg["threads"] == 16
    assert cfg["connection_limit"] == 300
    assert cfg["backlog"] == 1024
    assert cfg["channel_timeout"] == 120
    assert cfg["cleanup_interval"] == 30


def test_waitress_config_applies_bounds(monkeypatch):
    monkeypatch.setenv("WAITRESS_THREADS", "-1")
    monkeypatch.setenv("WAITRESS_CONNECTION_LIMIT", "999999")
    monkeypatch.setenv("WAITRESS_BACKLOG", "abc")
    monkeypatch.setenv("WAITRESS_CHANNEL_TIMEOUT", "2")
    monkeypatch.setenv("WAITRESS_CLEANUP_INTERVAL", "1000")

    main = importlib.import_module("main")
    cfg = main._build_waitress_server_config()

    assert cfg["threads"] == 4
    assert cfg["connection_limit"] == 5000
    assert cfg["backlog"] == 1024
    assert cfg["channel_timeout"] == 30
    assert cfg["cleanup_interval"] == 300
