"""Self-repair API for PilotSuite.

Provides guarded self-check and advisory repair planning:
- integrity snapshot (healthy/degraded/critical)
- recent error aggregation (last N errors)
- repo/channel metadata (official vs private)
- manual repair jobs powered by configured offline/cloud LLM routing

The v1 implementation is intentionally safe-by-default:
- no automatic code changes in this process
- no automatic git push or upstream PR creation
- all repair output is advisory unless explicitly extended
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, request
import requests as http_requests

from copilot_core.api.security import require_token
from copilot_core.api.v1 import system_status
from copilot_core.dev_surface.service import dev_surface
from copilot_core.llm_provider import LLMProvider

_LOGGER = logging.getLogger(__name__)

self_repair_bp = Blueprint("self_repair", __name__, url_prefix="/api/v1/self-repair")

_SETTINGS_PATH = os.environ.get("SELF_REPAIR_SETTINGS_PATH", "/data/self_repair_settings.json")
_JOBS_PATH = os.environ.get("SELF_REPAIR_JOBS_PATH", "/data/self_repair_jobs.json")
_WORKSPACE_ROOT = os.environ.get("SELF_REPAIR_WORKSPACE_ROOT", "/data/self_repair/workspaces")
_GIT_ASKPASS_PATH = os.environ.get("SELF_REPAIR_GIT_ASKPASS_PATH", "/tmp/pilotsuite_git_askpass.sh")
_MAX_JOB_HISTORY = 80
_MAX_ERROR_LIMIT = 100

_LOG_FALLBACK_PATHS = (
    "/data/dev_logs.jsonl",
    "/data/logs/pilotsuite.log",
    "/data/logs/pilotsuite_core.log",
    "/data/logs/supervisor.log",
    "/config/home-assistant.log",
)

_DEFAULT_SETTINGS: dict[str, Any] = {
    "enabled": True,
    "repair_mode": "advisory",  # advisory | assisted | auto
    "repair_provider": "auto",  # auto | offline | cloud
    "offline_repair_model": "",
    "cloud_repair_model": "",
    "max_errors_per_job": 6,
    "auto_self_check_on_start": False,
    "auto_self_check_on_degraded": False,
    "source_channel": "official",  # official | private
    "official_repo": {
        "owner": "GreenhillEfka",
        "name": "pilotsuite-styx-core",
        "default_branch": "main",
        "ha_repo": "GreenhillEfka/pilotsuite-styx-ha",
    },
    "github": {
        "enabled": False,
        "token": "",
        "repo_url": "",
        "repo_owner": "",
        "repo_name": "",
        "default_branch": "main",
        "working_branch": "styx-self-repair",
        "allow_push": False,
        "allow_upstream_pr": False,
        "upstream_repo": "GreenhillEfka/pilotsuite-styx-core",
    },
    "workspace": {
        "enabled": True,
        "root_path": _WORKSPACE_ROOT,
        "sync_on_job": True,
    },
}

_ERROR_HINTS: list[tuple[re.Pattern[str], dict[str, str]]] = [
    (
        re.compile(r"never awaited", re.IGNORECASE),
        {
            "category": "async-await",
            "hint": "Coroutine wird nicht awaited. Sync-Call auf async_create_task/await umstellen.",
            "fixability": "high",
        },
    ),
    (
        re.compile(r"already registered for a different blueprint", re.IGNORECASE),
        {
            "category": "blueprint-duplication",
            "hint": "Blueprint-Namen kollidieren. Registrierung mit Guard oder eindeutigen Namen absichern.",
            "fixability": "high",
        },
    ),
    (
        re.compile(r"model .* not found", re.IGNORECASE),
        {
            "category": "llm-model-missing",
            "hint": "Gewaehltes Modell ist nicht installiert/verfuegbar. Routing oder Modellwahl korrigieren.",
            "fixability": "high",
        },
    ),
    (
        re.compile(r"not reachable|failed to connect|connection", re.IGNORECASE),
        {
            "category": "connectivity",
            "hint": "Dienst-/Netzwerk-Konnektivitaet pruefen (Host, Port, Auth, Container-Netz).",
            "fixability": "medium",
        },
    ),
    (
        re.compile(r"memory .* exceeds", re.IGNORECASE),
        {
            "category": "resource-pressure",
            "hint": "RAM-Druck erkannt. Polling/Module/Logs optimieren oder Schwellwerte dynamisch anpassen.",
            "fixability": "medium",
        },
    ),
]

_LOCK = threading.Lock()
_JOBS_CACHE: list[dict[str, Any]] | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _deep_copy(value: Any) -> Any:
    return json.loads(json.dumps(value))


def _normalize_repo_url(url: str) -> tuple[str, str]:
    value = str(url or "").strip()
    if not value:
        return "", ""

    # owner/name
    if "/" in value and not value.startswith("http") and not value.startswith("git@"):
        parts = value.split("/")
        if len(parts) >= 2:
            return parts[-2].strip(), parts[-1].replace(".git", "").strip()

    # https://github.com/owner/name(.git)
    match = re.search(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?$", value)
    if match:
        return match.group(1).strip(), match.group(2).strip()

    return "", ""


def _read_json(path: str, fallback: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return _deep_copy(fallback)


def _write_json(path: str, payload: Any) -> None:
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
    try:
        os.chmod(path, 0o600)
    except Exception:
        # Best effort only.
        pass


def _load_settings() -> dict[str, Any]:
    stored = _read_json(_SETTINGS_PATH, _DEFAULT_SETTINGS)
    settings = _deep_copy(_DEFAULT_SETTINGS)

    if isinstance(stored, dict):
        for key in ("enabled", "repair_mode", "repair_provider", "offline_repair_model", "cloud_repair_model"):
            if key in stored:
                settings[key] = stored[key]

        for key in (
            "max_errors_per_job",
            "auto_self_check_on_start",
            "auto_self_check_on_degraded",
            "source_channel",
        ):
            if key in stored:
                settings[key] = stored[key]

        if isinstance(stored.get("official_repo"), dict):
            settings["official_repo"].update(stored["official_repo"])

        if isinstance(stored.get("github"), dict):
            settings["github"].update(stored["github"])

        if isinstance(stored.get("workspace"), dict):
            settings["workspace"].update(stored["workspace"])

    # Normalize
    settings["repair_mode"] = str(settings.get("repair_mode", "advisory")).strip().lower()
    if settings["repair_mode"] not in {"advisory", "assisted", "auto"}:
        settings["repair_mode"] = "advisory"

    settings["repair_provider"] = str(settings.get("repair_provider", "auto")).strip().lower()
    if settings["repair_provider"] not in {"auto", "offline", "cloud"}:
        settings["repair_provider"] = "auto"

    try:
        settings["max_errors_per_job"] = int(settings.get("max_errors_per_job", 6))
    except Exception:
        settings["max_errors_per_job"] = 6
    settings["max_errors_per_job"] = max(1, min(settings["max_errors_per_job"], 20))

    settings["source_channel"] = str(settings.get("source_channel", "official")).strip().lower()
    if settings["source_channel"] not in {"official", "private"}:
        settings["source_channel"] = "official"

    github = settings.get("github", {})
    github["enabled"] = bool(github.get("enabled", False))
    github["allow_push"] = bool(github.get("allow_push", False))
    github["allow_upstream_pr"] = bool(github.get("allow_upstream_pr", False))
    github["default_branch"] = str(github.get("default_branch") or "main").strip() or "main"
    github["working_branch"] = str(github.get("working_branch") or "styx-self-repair").strip() or "styx-self-repair"

    owner, name = _normalize_repo_url(str(github.get("repo_url") or ""))
    if owner and not github.get("repo_owner"):
        github["repo_owner"] = owner
    if name and not github.get("repo_name"):
        github["repo_name"] = name

    settings["github"] = github
    workspace = settings.get("workspace", {})
    workspace["enabled"] = bool(workspace.get("enabled", True))
    workspace["sync_on_job"] = bool(workspace.get("sync_on_job", True))
    root_path = str(workspace.get("root_path") or _WORKSPACE_ROOT).strip()
    workspace["root_path"] = root_path or _WORKSPACE_ROOT
    settings["workspace"] = workspace
    return settings


def _save_settings(settings: dict[str, Any]) -> None:
    _write_json(_SETTINGS_PATH, settings)


def _sanitize_settings(settings: dict[str, Any]) -> dict[str, Any]:
    out = _deep_copy(settings)
    github = out.get("github", {})
    token = str(github.get("token") or "").strip()
    github["token_configured"] = bool(token)
    github["token_preview"] = ("***" + token[-4:]) if token else ""
    github.pop("token", None)
    out["github"] = github
    return out


def _update_settings(patch: dict[str, Any]) -> dict[str, Any]:
    settings = _load_settings()

    for key in (
        "enabled",
        "repair_mode",
        "repair_provider",
        "offline_repair_model",
        "cloud_repair_model",
        "max_errors_per_job",
        "auto_self_check_on_start",
        "auto_self_check_on_degraded",
        "source_channel",
    ):
        if key in patch:
            settings[key] = patch[key]

    if isinstance(patch.get("official_repo"), dict):
        settings["official_repo"].update(patch["official_repo"])

    if isinstance(patch.get("github"), dict):
        settings["github"].update(patch["github"])

    if isinstance(patch.get("workspace"), dict):
        settings["workspace"].update(patch["workspace"])

    normalized = _load_settings_from_payload(settings)
    _save_settings(normalized)
    return normalized


def _load_settings_from_payload(settings: dict[str, Any]) -> dict[str, Any]:
    """Normalize already merged settings using the same logic as load."""
    # Temporary write/read is robust and keeps one normalization path.
    _write_json(_SETTINGS_PATH, settings)
    return _load_settings()


def _load_jobs() -> list[dict[str, Any]]:
    global _JOBS_CACHE
    with _LOCK:
        if _JOBS_CACHE is not None:
            return _deep_copy(_JOBS_CACHE)
        data = _read_json(_JOBS_PATH, [])
        jobs = data if isinstance(data, list) else []
        _JOBS_CACHE = jobs[-_MAX_JOB_HISTORY:]
        return _deep_copy(_JOBS_CACHE)


def _save_jobs(jobs: list[dict[str, Any]]) -> None:
    global _JOBS_CACHE
    with _LOCK:
        clipped = jobs[-_MAX_JOB_HISTORY:]
        _JOBS_CACHE = _deep_copy(clipped)
        _write_json(_JOBS_PATH, clipped)


def _append_job(job: dict[str, Any]) -> None:
    jobs = _load_jobs()
    jobs.append(job)
    _save_jobs(jobs)


def _to_epoch(value: Any) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _signature(message: str, module: str, level: str) -> str:
    raw = f"{level.lower()}|{module.lower()}|{message.strip().lower()}"
    return "err_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _classify_error(message: str, module: str, level: str) -> dict[str, Any]:
    msg = str(message or "")
    lowered_level = str(level or "").upper()

    payload = {
        "category": "generic",
        "hint": "Manuelle Analyse erforderlich.",
        "fixability": "low",
        "severity": "error" if lowered_level == "ERROR" else "warning",
    }

    for pattern, hit in _ERROR_HINTS:
        if pattern.search(msg) or pattern.search(module):
            payload.update(hit)
            if payload["fixability"] == "high":
                payload["severity"] = "error"
            return payload
    return payload


def _tail_lines(path: str, max_lines: int = 220, max_bytes: int = 512 * 1024) -> list[str]:
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            start = max(0, size - max_bytes)
            handle.seek(start)
            raw = handle.read().decode("utf-8", errors="replace")
        return raw.splitlines()[-max_lines:]
    except Exception:
        return []


def _collect_error_events(limit: int = 10, include_warnings: bool = True) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), _MAX_ERROR_LIMIT))
    levels = {"ERROR"}
    if include_warnings:
        levels.add("WARN")
        levels.add("WARNING")

    events: dict[str, dict[str, Any]] = {}

    # Structured logs from dev surface.
    try:
        recent = dev_surface.get_recent_logs(limit=max(limit * 10, 120), level_filter=None)
    except Exception:
        recent = []

    for row in recent:
        level = str(row.get("level") or "").upper()
        if level not in levels:
            continue
        module = str(row.get("module") or "unknown")
        message = str(row.get("message") or "")
        if not message:
            continue
        sig = _signature(message, module, level)
        cls = _classify_error(message, module, level)
        event = {
            "id": sig,
            "time": row.get("timestamp") or _now_iso(),
            "level": level,
            "module": module,
            "message": message,
            "error_type": row.get("error_type"),
            "stack_trace": row.get("stack_trace"),
            "category": cls["category"],
            "severity": cls["severity"],
            "fixability": cls["fixability"],
            "hint": cls["hint"],
            "source": "dev_surface",
        }
        # Keep latest occurrence.
        old = events.get(sig)
        if old is None or _to_epoch(event["time"]) >= _to_epoch(old.get("time")):
            events[sig] = event

    # Fallback raw log scan (best effort).
    for path in _LOG_FALLBACK_PATHS:
        if len(events) >= max(limit * 3, 40):
            break
        if not os.path.exists(path):
            continue

        for line in _tail_lines(path):
            text = str(line or "").strip()
            if not text:
                continue
            upper = text.upper()
            if not any(token in upper for token in ("ERROR", "WARNING", "RUNTIMEWARNING", "TRACEBACK")):
                continue

            level = "ERROR" if "ERROR" in upper or "TRACEBACK" in upper else "WARNING"
            if level not in levels:
                continue

            # rough parsing: "[module] message"
            module = "log"
            message = text
            module_match = re.search(r"\[([^\]]{2,80})\]", text)
            if module_match:
                module = module_match.group(1)

            sig = _signature(message, module, level)
            cls = _classify_error(message, module, level)
            event = {
                "id": sig,
                "time": _now_iso(),
                "level": level,
                "module": module,
                "message": message[:400],
                "error_type": None,
                "stack_trace": None,
                "category": cls["category"],
                "severity": cls["severity"],
                "fixability": cls["fixability"],
                "hint": cls["hint"],
                "source": f"file:{path}",
            }
            if sig not in events:
                events[sig] = event

    out = sorted(events.values(), key=lambda row: _to_epoch(row.get("time")), reverse=True)
    return out[:limit]


def _build_integrity_snapshot(force: bool = False) -> dict[str, Any]:
    overview, _ = system_status._build_overview_payload(force=bool(force), sensor_limit=220)
    overall = overview.get("overall", {}) if isinstance(overview, dict) else {}
    status = str(overall.get("status") or "unknown").lower()
    score = int(overall.get("score") or 0)

    color = "gray"
    if status == "healthy":
        color = "green"
    elif status == "degraded":
        color = "orange"
    elif status == "critical":
        color = "red"

    modules = overview.get("modules", {})
    services = overview.get("services", {})
    sensors = overview.get("sensors", {})

    return {
        "status": status,
        "color": color,
        "score": score,
        "summary": overall.get("summary") or "",
        "issues": overall.get("issues") or [],
        "module_count": int(modules.get("count") or 0),
        "module_service_ready": int(modules.get("service_ready_count") or 0),
        "service_count": int(services.get("count") or 0),
        "service_available": int(services.get("available_count") or 0),
        "sensor_count": int(sensors.get("sensor_count") or 0),
        "sensor_available": int(sensors.get("sensor_available") or 0),
        "sensor_target_94_reached": bool(sensors.get("target_94_reached", False)),
    }


def _recommended_repair_models(catalog: dict[str, Any]) -> dict[str, list[str]]:
    offline_models = catalog.get("offline", {}).get("models", []) if isinstance(catalog, dict) else []
    cloud_models = catalog.get("cloud", {}).get("models", []) if isinstance(catalog, dict) else []

    def _rank(models: list[str], cloud_only: bool = False) -> list[str]:
        scored: list[tuple[int, str]] = []
        for model in models:
            m = str(model or "").strip()
            if not m:
                continue
            if cloud_only and ":cloud" not in m.lower():
                continue
            s = 0
            l = m.lower()
            if "coder" in l or "code" in l:
                s += 5
            if "qwen" in l:
                s += 3
            if "4b" in l or "7b" in l or "8b" in l:
                s += 2
            if "0.6b" in l:
                s += 1
            if ":cloud" in l:
                s += 2
            scored.append((s, m))
        scored.sort(key=lambda row: (-row[0], row[1]))
        return [m for _s, m in scored[:6]]

    out_offline = _rank(list(offline_models), cloud_only=False)
    out_cloud = _rank(list(cloud_models), cloud_only=True)

    if not out_offline and offline_models:
        out_offline = [str(offline_models[0])]
    if not out_cloud and cloud_models:
        out_cloud = [str(cloud_models[0])]

    return {"offline": out_offline, "cloud": out_cloud}


def _llm_snapshot(force_refresh: bool = False) -> dict[str, Any]:
    try:
        provider = LLMProvider()
        status = provider.status()
        catalog = provider.model_catalog(force_refresh=bool(force_refresh))
        return {
            "ok": True,
            "status": status,
            "catalog": catalog,
            "recommended_for_repair": _recommended_repair_models(catalog),
        }
    except Exception as exc:
        _LOGGER.debug("Failed to build LLM snapshot", exc_info=True)
        return {
            "ok": False,
            "error": str(exc),
            "status": {},
            "catalog": {"offline": {"models": []}, "cloud": {"models": []}},
            "recommended_for_repair": {"offline": [], "cloud": []},
        }


def _repo_snapshot(settings: dict[str, Any]) -> dict[str, Any]:
    official = settings.get("official_repo", {}) if isinstance(settings, dict) else {}
    github = settings.get("github", {}) if isinstance(settings, dict) else {}

    private_owner = str(github.get("repo_owner") or "").strip()
    private_name = str(github.get("repo_name") or "").strip()
    private_repo = f"{private_owner}/{private_name}" if private_owner and private_name else ""

    channel = str(settings.get("source_channel") or "official").strip().lower()
    if channel not in {"official", "private"}:
        channel = "official"

    official_repo = f"{official.get('owner','')}/{official.get('name','')}".strip("/")

    return {
        "active_channel": channel,
        "official_repo": official_repo,
        "official_branch": str(official.get("default_branch") or "main"),
        "private_repo": private_repo,
        "private_branch": str(github.get("default_branch") or "main"),
        "private_connected": bool(private_repo and github.get("enabled") and github.get("token")),
        "working_branch": str(github.get("working_branch") or "styx-self-repair"),
        "allow_push": bool(github.get("allow_push")),
        "allow_upstream_pr": bool(github.get("allow_upstream_pr")),
        "upstream_repo": str(github.get("upstream_repo") or ""),
    }


def _github_headers(token: str) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "PilotSuite-Styx-SelfRepair",
    }
    clean = str(token or "").strip()
    if clean:
        headers["Authorization"] = f"Bearer {clean}"
    return headers


def _github_get(path: str, token: str, timeout: float = 8.0) -> tuple[int, dict[str, Any] | None]:
    url = f"https://api.github.com{path}"
    try:
        response = http_requests.get(url, headers=_github_headers(token), timeout=timeout)
        payload = response.json() if response.content else None
        if isinstance(payload, dict):
            return response.status_code, payload
        return response.status_code, None
    except Exception:
        return 0, None


def _sanitize_git_ref(value: str, fallback: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9._/-]+", "-", str(value or "").strip()).strip(".-/")
    return text[:120] if text else fallback


def _workspace_dir_name(owner: str, name: str) -> str:
    combined = f"{owner}__{name}".lower()
    return re.sub(r"[^a-z0-9._-]+", "_", combined)[:120]


def _active_repo_descriptor(settings: dict[str, Any]) -> dict[str, Any]:
    official = settings.get("official_repo", {}) if isinstance(settings, dict) else {}
    github = settings.get("github", {}) if isinstance(settings, dict) else {}
    channel = str(settings.get("source_channel") or "official").strip().lower()
    if channel not in {"official", "private"}:
        channel = "official"

    if channel == "private":
        owner = str(github.get("repo_owner") or "").strip()
        name = str(github.get("repo_name") or "").strip()
        if owner and name:
            return {
                "channel": "private",
                "owner": owner,
                "name": name,
                "base_branch": str(github.get("default_branch") or "main").strip() or "main",
                "clone_url": f"https://github.com/{owner}/{name}.git",
                "token": str(github.get("token") or "").strip(),
                "working_branch_prefix": str(github.get("working_branch") or "styx-self-repair").strip()
                or "styx-self-repair",
            }

    owner = str(official.get("owner") or "").strip() or "GreenhillEfka"
    name = str(official.get("name") or "").strip() or "pilotsuite-styx-core"
    return {
        "channel": "official",
        "owner": owner,
        "name": name,
        "base_branch": str(official.get("default_branch") or "main").strip() or "main",
        "clone_url": f"https://github.com/{owner}/{name}.git",
        "token": "",
        "working_branch_prefix": "styx-self-repair",
    }


def _workspace_settings(settings: dict[str, Any]) -> dict[str, Any]:
    workspace = settings.get("workspace", {}) if isinstance(settings, dict) else {}
    root_path = str(workspace.get("root_path") or _WORKSPACE_ROOT).strip() or _WORKSPACE_ROOT
    return {
        "enabled": bool(workspace.get("enabled", True)),
        "sync_on_job": bool(workspace.get("sync_on_job", True)),
        "root_path": root_path,
    }


def _workspace_repo_path(settings: dict[str, Any]) -> Path:
    workspace = _workspace_settings(settings)
    repo = _active_repo_descriptor(settings)
    return Path(workspace["root_path"]).expanduser() / _workspace_dir_name(repo["owner"], repo["name"])


def _workspace_status(settings: dict[str, Any]) -> dict[str, Any]:
    workspace = _workspace_settings(settings)
    repo = _active_repo_descriptor(settings)
    repo_path = _workspace_repo_path(settings)
    git_path = shutil.which("git")
    return {
        "enabled": workspace["enabled"],
        "sync_on_job": workspace["sync_on_job"],
        "git_available": bool(git_path),
        "git_path": git_path or "",
        "root_path": workspace["root_path"],
        "repo_path": str(repo_path),
        "repo_present": bool((repo_path / ".git").exists()),
        "active_channel": repo["channel"],
        "repo": f"{repo['owner']}/{repo['name']}",
        "base_branch": repo["base_branch"],
    }


def _ensure_git_askpass_script() -> str | None:
    path = Path(_GIT_ASKPASS_PATH)
    script = (
        "#!/bin/sh\n"
        "case \"$1\" in\n"
        "  *sername*) printf '%s\\n' \"${PILOTSUITE_GIT_USERNAME:-x-access-token}\" ;;\n"
        "  *assword*) printf '%s\\n' \"${PILOTSUITE_GIT_TOKEN:-}\" ;;\n"
        "  *) printf '\\n' ;;\n"
        "esac\n"
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_text(encoding="utf-8", errors="ignore") != script:
            path.write_text(script, encoding="utf-8")
        path.chmod(0o700)
        return str(path)
    except Exception:
        return None


def _run_git(args: list[str], *, cwd: Path | None = None, token: str = "", timeout: float = 45.0) -> dict[str, Any]:
    binary = shutil.which("git")
    if not binary:
        return {"ok": False, "error": "git_not_available", "code": None, "stdout": "", "stderr": ""}

    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = ""
    clean_token = str(token or "").strip()
    if clean_token:
        askpass = _ensure_git_askpass_script()
        if not askpass:
            return {"ok": False, "error": "git_askpass_unavailable", "code": None, "stdout": "", "stderr": ""}
        env["GIT_ASKPASS"] = askpass
        env["PILOTSUITE_GIT_USERNAME"] = "x-access-token"
        env["PILOTSUITE_GIT_TOKEN"] = clean_token

    cmd = [binary, *args]
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "error": "timeout",
            "code": None,
            "stdout": (exc.stdout or "")[-2000:],
            "stderr": (exc.stderr or "")[-2000:],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "code": None, "stdout": "", "stderr": ""}

    return {
        "ok": completed.returncode == 0,
        "error": "",
        "code": completed.returncode,
        "stdout": (completed.stdout or "")[-2000:],
        "stderr": (completed.stderr or "")[-2000:],
    }


def _prepare_workspace_branch(
    settings: dict[str, Any],
    *,
    force_sync: bool = False,
    branch_hint: str = "",
) -> dict[str, Any]:
    workspace = _workspace_settings(settings)
    repo = _active_repo_descriptor(settings)
    status = _workspace_status(settings)

    if not workspace["enabled"]:
        return {"ok": False, "error": "workspace_disabled", "workspace": status}
    if not status["git_available"]:
        return {"ok": False, "error": "git_not_available", "workspace": status}
    if repo["channel"] == "private" and not repo["token"]:
        return {"ok": False, "error": "private_repo_token_required", "workspace": status}

    root = Path(workspace["root_path"]).expanduser()
    repo_path = _workspace_repo_path(settings)
    actions: list[str] = []
    try:
        root.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return {"ok": False, "error": f"workspace_root_unwritable:{exc}", "workspace": status}

    clone_timeout = 150.0
    if not (repo_path / ".git").exists():
        clone = _run_git(
            [
                "clone",
                "--origin",
                "origin",
                "--branch",
                repo["base_branch"],
                "--single-branch",
                repo["clone_url"],
                str(repo_path),
            ],
            token=repo["token"],
            timeout=clone_timeout,
        )
        if not clone["ok"]:
            return {
                "ok": False,
                "error": "clone_failed",
                "workspace": status,
                "git": {"clone": clone},
            }
        actions.append("cloned")

    should_sync = bool(force_sync or workspace["sync_on_job"])
    if should_sync:
        fetch = _run_git(["fetch", "--all", "--prune"], cwd=repo_path, token=repo["token"], timeout=60.0)
        if not fetch["ok"]:
            return {"ok": False, "error": "fetch_failed", "workspace": status, "git": {"fetch": fetch}}
        actions.append("fetched")

    base_branch = _sanitize_git_ref(repo["base_branch"], "main")
    branch_prefix = _sanitize_git_ref(repo["working_branch_prefix"], "styx-self-repair")
    branch_name = _sanitize_git_ref(
        branch_hint or f"{branch_prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}",
        branch_prefix,
    )

    source_ref = f"origin/{base_branch}"
    check_origin = _run_git(["rev-parse", "--verify", source_ref], cwd=repo_path, token=repo["token"])
    if not check_origin["ok"]:
        source_ref = base_branch

    checkout = _run_git(["checkout", "-B", branch_name, source_ref], cwd=repo_path, token=repo["token"], timeout=45.0)
    if not checkout["ok"]:
        return {"ok": False, "error": "checkout_failed", "workspace": status, "git": {"checkout": checkout}}
    actions.append("branch_prepared")

    head = _run_git(["rev-parse", "--short", "HEAD"], cwd=repo_path, token=repo["token"])
    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path, token=repo["token"])

    prepared = {
        **status,
        "repo_path": str(repo_path),
        "repo_present": True,
        "working_branch": (branch.get("stdout") or "").strip() if branch.get("ok") else branch_name,
        "head": (head.get("stdout") or "").strip() if head.get("ok") else "",
        "prepared_at": _now_iso(),
        "actions": actions,
    }
    return {"ok": True, "workspace": prepared}


def _build_self_check(limit: int = 10, force: bool = False) -> dict[str, Any]:
    settings = _load_settings()
    integrity = _build_integrity_snapshot(force=force)
    errors = _collect_error_events(limit=limit, include_warnings=True)
    repo = _repo_snapshot(settings)
    llm = _llm_snapshot(force_refresh=force)
    workspace = _workspace_status(settings)

    fixability_counts: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    for row in errors:
        fx = str(row.get("fixability") or "low").lower()
        if fx not in fixability_counts:
            fx = "low"
        fixability_counts[fx] += 1

    actionable = [e for e in errors if str(e.get("fixability", "low")) in {"high", "medium"}]

    return {
        "ok": True,
        "time": _now_iso(),
        "integrity": integrity,
        "repo": repo,
        "workspace": workspace,
        "llm": llm,
        "errors": errors,
        "summary": {
            "error_count": len(errors),
            "actionable_count": len(actionable),
            "fixability": fixability_counts,
            "self_repair_ready": bool(settings.get("enabled", True)),
            "auto_mode": str(settings.get("repair_mode") or "advisory"),
        },
    }


def _model_selector_for_repair(settings: dict[str, Any], llm_status: dict[str, Any]) -> str:
    provider_pref = str(settings.get("repair_provider") or "auto").strip().lower()

    if provider_pref == "offline":
        model = str(settings.get("offline_repair_model") or "").strip()
        return f"offline:{model}" if model else "offline"

    if provider_pref == "cloud":
        model = str(settings.get("cloud_repair_model") or "").strip()
        return f"cloud:{model}" if model else "cloud"

    # auto -> follow primary routing
    primary = str(llm_status.get("primary_provider") or "offline").strip().lower()
    if primary == "cloud":
        model = str(settings.get("cloud_repair_model") or "").strip()
        return f"cloud:{model}" if model else "primary"
    model = str(settings.get("offline_repair_model") or "").strip()
    return f"offline:{model}" if model else "primary"


def _extract_json_payload(content: str) -> dict[str, Any] | None:
    text = str(content or "").strip()
    if not text:
        return None

    # direct JSON
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # fenced JSON block
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict):
                return data
        except Exception:
            return None
    return None


def _generate_repair_plan(
    *,
    selected_errors: list[dict[str, Any]],
    integrity: dict[str, Any],
    settings: dict[str, Any],
    repo: dict[str, Any],
    llm: dict[str, Any],
) -> dict[str, Any]:
    provider = LLMProvider()
    status = provider.status()

    model_selector = _model_selector_for_repair(settings, status)

    payload = {
        "integrity": integrity,
        "errors": [
            {
                "id": row.get("id"),
                "level": row.get("level"),
                "module": row.get("module"),
                "message": row.get("message"),
                "category": row.get("category"),
                "hint": row.get("hint"),
            }
            for row in selected_errors
        ],
        "repo": repo,
        "constraints": {
            "no_unverified_destructive_changes": True,
            "prefer_config_fix_first": True,
            "ha_compat_required": True,
        },
    }

    system_prompt = (
        "You are Styx self-repair planner for a Home Assistant addon. "
        "Return strict JSON with keys: diagnosis, actions, tests, rollback, risk. "
        "Each action must be concrete and safe."
    )
    user_prompt = "Create a repair plan for this runtime snapshot:\n" + json.dumps(payload, ensure_ascii=False)

    result = provider.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=model_selector,
        temperature=0.2,
        max_tokens=1100,
    )

    content = str(result.get("content") or "").strip()
    parsed = _extract_json_payload(content)

    if parsed is None:
        parsed = {
            "diagnosis": "LLM lieferte kein strukturiertes JSON. Rohantwort als advisory_text gespeichert.",
            "actions": [
                {
                    "type": "manual_review",
                    "title": "Rohantwort pruefen",
                    "detail": content[:1200] if content else "Keine Antwort erhalten",
                }
            ],
            "tests": [],
            "rollback": "Vor Aenderungen Branch erstellen und Config/Dateien sichern.",
            "risk": "medium",
        }

    return {
        "provider_result": result,
        "model_selector": model_selector,
        "plan": parsed,
        "raw_content": content,
    }


@self_repair_bp.route("/status", methods=["GET"])
@require_token
def get_self_repair_status():
    settings = _load_settings()
    check = _build_self_check(limit=10, force=False)
    jobs = _load_jobs()

    return jsonify(
        {
            "ok": True,
            "time": _now_iso(),
            "settings": _sanitize_settings(settings),
            "integrity": check.get("integrity", {}),
            "repo": check.get("repo", {}),
            "workspace": check.get("workspace", _workspace_status(settings)),
            "llm": check.get("llm", {}),
            "errors_preview": check.get("errors", [])[:10],
            "jobs": {
                "count": len(jobs),
                "latest": jobs[-1] if jobs else None,
                "items": jobs[-5:],
            },
        }
    )


@self_repair_bp.route("/settings", methods=["GET"])
@require_token
def get_self_repair_settings():
    return jsonify({"ok": True, "settings": _sanitize_settings(_load_settings())})


@self_repair_bp.route("/settings", methods=["POST"])
@require_token
def update_self_repair_settings():
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": "invalid_payload"}), 400

    settings = _update_settings(body)
    return jsonify({"ok": True, "settings": _sanitize_settings(settings), "time": _now_iso()})


@self_repair_bp.route("/workspace/status", methods=["GET"])
@require_token
def get_workspace_status():
    settings = _load_settings()
    return jsonify({"ok": True, "workspace": _workspace_status(settings), "time": _now_iso()})


@self_repair_bp.route("/workspace/prepare", methods=["POST"])
@require_token
def prepare_workspace():
    settings = _load_settings()
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        body = {}

    result = _prepare_workspace_branch(
        settings,
        force_sync=bool(body.get("force_sync", False)),
        branch_hint=str(body.get("branch") or "").strip(),
    )
    code = 200 if bool(result.get("ok")) else 400
    result["time"] = _now_iso()
    return jsonify(result), code


@self_repair_bp.route("/github/test", methods=["POST"])
@require_token
def test_github_connection():
    """Validate GitHub PAT + repo access and optionally persist connection."""
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": "invalid_payload"}), 400

    settings = _load_settings()
    github = settings.get("github", {}) if isinstance(settings, dict) else {}

    token = str(body.get("token") or github.get("token") or "").strip()
    repo_input = str(body.get("repo") or "").strip()
    owner = str(body.get("repo_owner") or github.get("repo_owner") or "").strip()
    name = str(body.get("repo_name") or github.get("repo_name") or "").strip()
    if repo_input and not (owner and name):
        parsed_owner, parsed_name = _normalize_repo_url(repo_input)
        owner = owner or parsed_owner
        name = name or parsed_name

    if not token:
        return jsonify({"ok": False, "error": "github_token_required"}), 400
    if not owner or not name:
        return jsonify({"ok": False, "error": "repo_required"}), 400

    user_status, user_payload = _github_get("/user", token=token)
    repo_status, repo_payload = _github_get(f"/repos/{owner}/{name}", token=token)

    auth_ok = user_status == 200 and isinstance(user_payload, dict)
    repo_ok = repo_status == 200 and isinstance(repo_payload, dict)

    result: dict[str, Any] = {
        "ok": auth_ok and repo_ok,
        "auth_ok": auth_ok,
        "repo_ok": repo_ok,
        "authenticated_as": (user_payload or {}).get("login") if auth_ok else None,
        "repo": f"{owner}/{name}",
        "repo_default_branch": (repo_payload or {}).get("default_branch") if repo_ok else None,
        "repo_private": bool((repo_payload or {}).get("private")) if repo_ok else None,
        "permissions": (repo_payload or {}).get("permissions") if repo_ok else None,
        "http_status": {"user": user_status, "repo": repo_status},
        "time": _now_iso(),
    }

    if bool(body.get("save", False)) and result["ok"]:
        update_payload = {
            "github": {
                "enabled": True,
                "token": token,
                "repo_owner": owner,
                "repo_name": name,
                "repo_url": f"https://github.com/{owner}/{name}.git",
            }
        }
        settings = _update_settings(update_payload)
        result["settings"] = _sanitize_settings(settings)

    return jsonify(result), (200 if result["ok"] else 400)


@self_repair_bp.route("/errors", methods=["GET"])
@require_token
def get_self_repair_errors():
    try:
        limit = int(request.args.get("limit", "10"))
    except Exception:
        limit = 10
    limit = max(1, min(limit, _MAX_ERROR_LIMIT))

    include_warnings = str(request.args.get("include_warnings", "true")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    errors = _collect_error_events(limit=limit, include_warnings=include_warnings)
    return jsonify({"ok": True, "count": len(errors), "errors": errors, "time": _now_iso()})


@self_repair_bp.route("/self-check", methods=["POST"])
@require_token
def run_self_check():
    body = request.get_json(silent=True) or {}
    force = bool(body.get("force", False))
    try:
        limit = int(body.get("limit", 10))
    except Exception:
        limit = 10
    limit = max(1, min(limit, _MAX_ERROR_LIMIT))

    check = _build_self_check(limit=limit, force=force)
    return jsonify(check)


@self_repair_bp.route("/jobs", methods=["GET"])
@require_token
def list_self_repair_jobs():
    jobs = _load_jobs()
    try:
        limit = int(request.args.get("limit", "20"))
    except Exception:
        limit = 20
    limit = max(1, min(limit, _MAX_JOB_HISTORY))

    return jsonify({"ok": True, "count": len(jobs), "jobs": jobs[-limit:], "time": _now_iso()})


@self_repair_bp.route("/jobs/<job_id>", methods=["GET"])
@require_token
def get_self_repair_job(job_id: str):
    jobs = _load_jobs()
    for job in reversed(jobs):
        if str(job.get("id")) == str(job_id):
            return jsonify({"ok": True, "job": job})
    return jsonify({"ok": False, "error": "job_not_found"}), 404


@self_repair_bp.route("/jobs", methods=["POST"])
@require_token
def create_self_repair_job():
    settings = _load_settings()
    if not bool(settings.get("enabled", True)):
        return jsonify({"ok": False, "error": "self_repair_disabled"}), 400

    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": "invalid_payload"}), 400

    requested_ids = [str(x).strip() for x in (body.get("error_ids") or []) if str(x).strip()]
    try:
        requested_limit = int(body.get("limit", settings.get("max_errors_per_job", 6)))
    except Exception:
        requested_limit = int(settings.get("max_errors_per_job", 6))
    requested_limit = max(1, min(requested_limit, int(settings.get("max_errors_per_job", 6))))

    all_errors = _collect_error_events(limit=max(40, requested_limit * 4), include_warnings=True)
    by_id = {str(row.get("id")): row for row in all_errors}

    selected_errors: list[dict[str, Any]] = []
    for eid in requested_ids:
        row = by_id.get(eid)
        if row:
            selected_errors.append(row)

    if not selected_errors:
        selected_errors = all_errors[:requested_limit]

    if not selected_errors:
        return jsonify({"ok": False, "error": "no_errors_available"}), 400

    integrity = _build_integrity_snapshot(force=bool(body.get("force", False)))
    llm = _llm_snapshot(force_refresh=False)
    repo = _repo_snapshot(settings)
    workspace_sync = bool(body.get("workspace_force_sync", False))
    workspace_branch_hint = str(body.get("workspace_branch") or "").strip()
    workspace = _prepare_workspace_branch(
        settings,
        force_sync=workspace_sync,
        branch_hint=workspace_branch_hint,
    )

    job_id = "sr_" + uuid.uuid4().hex[:12]
    started = _now_iso()

    job: dict[str, Any] = {
        "id": job_id,
        "status": "running",
        "mode": str(settings.get("repair_mode") or "advisory"),
        "created_at": started,
        "started_at": started,
        "finished_at": None,
        "requested_error_ids": requested_ids,
        "errors": selected_errors,
        "integrity": integrity,
        "repo": repo,
        "workspace": workspace.get("workspace", _workspace_status(settings)),
        "execution": {
            "code_changes_applied": False,
            "git_push_attempted": False,
            "upstream_pr_attempted": False,
            "notes": "Safety guard active: advisory-only execution in this version.",
        },
    }

    try:
        if not workspace.get("ok"):
            job["execution"]["notes"] = (
                "Workspace-Preparation fehlgeschlagen. Repair-Plan wurde trotzdem erstellt, "
                "aber Branch-Flow ist nicht bereit."
            )
            job["execution"]["workspace_error"] = workspace.get("error")

        repair = _generate_repair_plan(
            selected_errors=selected_errors,
            integrity=integrity,
            settings=settings,
            repo=repo,
            llm=llm,
        )

        provider_result = repair.get("provider_result") or {}
        job["llm"] = {
            "selector": repair.get("model_selector"),
            "provider": provider_result.get("provider") or "none",
            "status": llm.get("status", {}),
        }
        job["plan"] = repair.get("plan") or {}
        job["advisory_text"] = (repair.get("raw_content") or "")[:6000]

        mode = str(settings.get("repair_mode") or "advisory")
        if mode in {"assisted", "auto"}:
            job["execution"]["notes"] = (
                "Assisted/auto mode angefordert, aber Code-Patching + Git-Push sind in v1 absichtlich deaktiviert. "
                "Nutze den Plan zur gezielten Umsetzung in Branch/PR."
            )

        job["status"] = "completed"
        job["finished_at"] = _now_iso()
    except Exception as exc:
        _LOGGER.exception("Self-repair job failed")
        job["status"] = "failed"
        job["finished_at"] = _now_iso()
        job["error"] = str(exc)

    _append_job(job)
    return jsonify({"ok": True, "job": job})
