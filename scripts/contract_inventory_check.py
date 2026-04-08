from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path


def _app_src_root(repo_root: Path) -> Path:
    return repo_root / "pilotsuite_core" / "rootfs" / "usr" / "src" / "app"


def load_inventory_entries(repo_root: Path) -> list[dict]:
    inventory_file = _app_src_root(repo_root) / "dashboard" / "api" / "v1" / "blueprints_config.py"
    namespace: dict[str, object] = {}
    exec(inventory_file.read_text(), namespace)
    return list(namespace["BLUEPRINT_CONTRACT_INVENTORY"])


def _normalize_runtime_rule(rule: str) -> str:
    normalized_parts: list[str] = []
    for part in rule.split("/"):
        if part.startswith("<") and part.endswith(">"):
            raw_name = part[1:-1]
            normalized_parts.append("{" + raw_name.split(":", 1)[-1] + "}")
            continue
        normalized_parts.append(part)
    return "/".join(normalized_parts)


def _literal_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _blueprint_sources(module_ast: ast.Module) -> dict[str, str]:
    sources: dict[str, str] = {}
    for node in module_ast.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        if not isinstance(node.value.func, ast.Name) or node.value.func.id != "Blueprint":
            continue
        for keyword in node.value.keywords:
            if keyword.arg == "url_prefix":
                url_prefix = _literal_string(keyword.value)
                if url_prefix:
                    sources[target.id] = url_prefix
    return sources


def load_runtime_routes(repo_root: Path) -> dict[str, list[str]]:
    app_src = _app_src_root(repo_root)
    runtime_routes: dict[str, set[str]] = {}

    for entry in load_inventory_entries(repo_root):
        module_path = app_src / Path(entry["module"].replace(".", "/") + ".py")
        module_ast = ast.parse(module_path.read_text())
        url_prefixes = _blueprint_sources(module_ast)

        for node in module_ast.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                if not isinstance(decorator.func, ast.Attribute):
                    continue
                if not isinstance(decorator.func.value, ast.Name):
                    continue

                blueprint_name = decorator.func.value.id
                method = decorator.func.attr.lower()
                if method not in {"get", "post", "put", "patch", "delete"}:
                    continue

                url_prefix = url_prefixes.get(blueprint_name)
                if not url_prefix:
                    continue

                route_suffix = _literal_string(decorator.args[0]) if decorator.args else None
                if route_suffix is None:
                    continue

                full_path = _normalize_runtime_rule(f"{url_prefix}{route_suffix}")
                runtime_routes.setdefault(full_path, set()).add(method)

    return {path: sorted(methods) for path, methods in sorted(runtime_routes.items())}


def load_app_routes(repo_root: Path) -> dict[str, list[str]]:
    main_module = _app_src_root(repo_root) / "main.py"
    module_ast = ast.parse(main_module.read_text())
    app_routes: dict[str, set[str]] = {}

    for node in ast.walk(module_ast):
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if not isinstance(decorator.func, ast.Attribute):
                continue
            if not isinstance(decorator.func.value, ast.Name) or decorator.func.value.id != "app":
                continue

            method = decorator.func.attr.lower()
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue

            route = _literal_string(decorator.args[0]) if decorator.args else None
            if route is None:
                continue

            app_routes.setdefault(_normalize_runtime_rule(route), set()).add(method)

    return {path: sorted(methods) for path, methods in sorted(app_routes.items())}


def load_public_runtime_routes(repo_root: Path) -> dict[str, list[str]]:
    public_routes: dict[str, set[str]] = {}

    for source in (load_app_routes(repo_root), load_runtime_routes(repo_root)):
        for path, methods in source.items():
            if path == "/":
                continue
            public_routes.setdefault(path, set()).update(methods)

    return {path: sorted(methods) for path, methods in sorted(public_routes.items())}


def load_inventory_routes(repo_root: Path) -> dict[str, list[str]]:
    inventory_routes: dict[str, list[str]] = {}
    for blueprint in load_inventory_entries(repo_root):
        for path, methods in blueprint["paths"].items():
            inventory_routes[path] = sorted(method.lower() for method in methods)
    return dict(sorted(inventory_routes.items()))


def load_openapi_routes(repo_root: Path) -> dict[str, list[str]]:
    openapi_json = repo_root / "docs" / "openapi.json"
    if not openapi_json.exists():
        raise FileNotFoundError(f"OpenAPI inventory missing: {openapi_json}")

    spec = json.loads(openapi_json.read_text())
    openapi_routes: dict[str, list[str]] = {}
    for path, path_item in spec.get("paths", {}).items():
        methods = sorted(
            key.lower()
            for key, value in path_item.items()
            if key.lower() in {"get", "post", "put", "patch", "delete"} and isinstance(value, dict)
        )
        if methods:
            openapi_routes[path] = methods
    return dict(sorted(openapi_routes.items()))


def load_readme_routes(repo_root: Path) -> dict[str, list[str]]:
    readme = (repo_root / "README.md").read_text()
    try:
        endpoint_section = readme.split("## API Endpoints", 1)[1].split("## ", 1)[0]
    except IndexError as exc:
        raise ValueError("README API Endpoints section missing") from exc

    readme_routes: dict[str, list[str]] = {}
    for raw_line in endpoint_section.splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue

        columns = [column.strip() for column in line.strip("|").split("|")]
        if len(columns) < 2:
            continue

        endpoint = columns[0].strip("`")
        if not endpoint.startswith("/"):
            continue

        methods = sorted(method.strip().lower() for method in columns[1].split(",") if method.strip())
        if methods:
            readme_routes[endpoint] = methods

    return dict(sorted(readme_routes.items()))


def _diff(label: str, source: dict[str, list[str]], target: dict[str, list[str]]) -> list[str]:
    messages: list[str] = []

    missing_paths = sorted(set(source) - set(target))
    extra_paths = sorted(set(target) - set(source))

    for path in missing_paths:
        messages.append(f"{label}: missing path {path}")
    for path in extra_paths:
        messages.append(f"{label}: orphan path {path}")

    shared_paths = sorted(set(source) & set(target))
    for path in shared_paths:
        source_methods = source[path]
        target_methods = target[path]
        if source_methods != target_methods:
            messages.append(
                f"{label}: method drift on {path} (source={source_methods}, target={target_methods})"
            )

    return messages


def run(repo_root: Path, *, light: bool) -> int:
    runtime_routes = load_runtime_routes(repo_root)
    inventory_routes = load_inventory_routes(repo_root)

    messages = _diff("inventory vs runtime", runtime_routes, inventory_routes)

    if not light:
        public_runtime_routes = load_public_runtime_routes(repo_root)
        openapi_routes = load_openapi_routes(repo_root)
        readme_routes = load_readme_routes(repo_root)

        messages.extend(_diff("openapi vs public runtime", public_runtime_routes, openapi_routes))
        messages.extend(_diff("README vs public runtime", public_runtime_routes, readme_routes))

    if messages:
        for message in messages:
            print(message)
        return 2

    print(
        "contract inventory OK"
        + (" (light runtime check)" if light else " (runtime + OpenAPI + README check)")
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check PilotSuite contract inventory drift")
    parser.add_argument("--repo", default=".", help="Repository root")
    parser.add_argument("--light", action="store_true", help="Skip OpenAPI/README comparison")
    args = parser.parse_args()

    repo_root = Path(args.repo).resolve()
    try:
        return run(repo_root, light=args.light)
    except Exception as exc:
        print(f"contract inventory check failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
