"""Syntax smoke coverage for all Flask API v1 modules."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
API_V1_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app" / "copilot_core" / "api" / "v1"


def test_api_v1_modules_are_syntax_valid() -> None:
    failures: list[str] = []

    for path in sorted(API_V1_ROOT.glob("*.py")):
        source = path.read_text(encoding="utf-8", errors="ignore")
        try:
            compile(source, str(path), "exec")
        except Exception as exc:  # pragma: no cover - exercised only on failure
            failures.append(f"{path.name}: {type(exc).__name__}: {exc}")

    assert not failures, "\n".join(failures)
