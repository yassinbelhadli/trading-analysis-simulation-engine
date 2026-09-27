"""Verify the frozen Backend V2 architecture boundaries and contracts."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Frozen route inventory. Updated by the support/ticket phase which added the
# client support surface (list/create/detail/reply), the admin ticket sub-routes
# (metrics, assign, escalate, ban) and the pre-existing admin tickets rewrite:
#   +15 paths (134 -> 149), +18 operations (158 -> 176).
EXPECTED_PATHS = 149
EXPECTED_OPERATIONS = 176


def _source(relative: str) -> str:
    """Read one repository source file."""
    return (ROOT / relative).read_text(encoding="utf-8")


def _function_source(relative: str, name: str) -> str:
    """Extract one function body for a route-boundary check."""
    source = _source(relative)
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == name:
            end = getattr(node, "end_lineno", node.lineno)
            return "\n".join(lines[node.lineno - 1:end])
    raise AssertionError(f"function not found: {relative}:{name}")


def _check(condition: bool, label: str) -> None:
    """Print one stability check and fail immediately when it is false."""
    if not condition:
        raise AssertionError(label)
    print(f"[PASS] {label}")


def main() -> int:
    """Run static architecture and OpenAPI contract checks."""
    from api.main import app

    paths = app.openapi()["paths"]
    operations = sum(
        1 for methods in paths.values() for method in methods if method != "parameters"
    )
    _check(len(paths) == EXPECTED_PATHS, f"route paths frozen at {EXPECTED_PATHS}")
    _check(operations == EXPECTED_OPERATIONS, f"route operations frozen at {EXPECTED_OPERATIONS}")

    for path in (
        "/api/client/dashboard",
        "/api/admin/overview",
        "/api/admin/trading/trade/{trade_id}/snapshot",
    ):
        _check(path in paths, f"required compatibility path exists: {path}")

    for path in ("/api/client/dashboard", "/api/admin/overview"):
        schema = paths[path]["get"]["responses"]["200"].get("content", {}).get(
            "application/json", {}
        ).get("schema")
        _check(schema is not None, f"typed response schema exists: {path}")

    for relative in (
        "api/services/client_dashboard_query_service.py",
        "api/services/admin_dashboard_query_service.py",
    ):
        source = _source(relative)
        for forbidden in ("session.execute", "session.add", "session.commit", "session.delete", "select("):
            _check(forbidden not in source, f"query service has no {forbidden}: {relative}")

    for relative in (
        "api/services/client_dashboard_aggregator.py",
        "api/services/admin_dashboard_aggregator.py",
    ):
        source = _source(relative)
        for forbidden in ("AsyncSession", "sqlalchemy", ".commit(", ".add(", ".delete("):
            _check(forbidden not in source, f"aggregator has no {forbidden}: {relative}")

    for relative in (
        "api/routes/licenses.py",
        "api/routes/client/accounts.py",
        "api/routes/admin/overview.py",
    ):
        source = _source(relative)
        for forbidden in ("session.execute", "session.add", "session.commit", "session.delete", "select("):
            _check(forbidden not in source, f"migrated route has no {forbidden}: {relative}")

    dashboard_route = _function_source("api/routes/client/dashboard.py", "client_dashboard")
    for forbidden in ("session.execute", "session.add", "session.commit", "select("):
        _check(forbidden not in dashboard_route, f"client dashboard adapter has no {forbidden}")

    service_modules = sorted(
        path.stem for path in (ROOT / "api" / "services").glob("*.py") if path.name != "__init__.py"
    )
    repository_modules = sorted(
        path.stem for path in (ROOT / "database" / "repositories").glob("*.py") if path.name != "__init__.py"
    )
    dto_classes = 0
    for path in (ROOT / "api" / "schemas").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        dto_classes += sum(
            1 for node in tree.body
            if isinstance(node, ast.ClassDef)
            and any(getattr(base, "id", "") == "BaseModel" for base in node.bases)
        )
    print(f"[INFO] API service modules: {len(service_modules)}")
    print(f"[INFO] Repository modules: {len(repository_modules)}")
    print(f"[INFO] Pydantic DTO classes: {dto_classes}")
    print("[INFO] V2 route adapters: 4; compatibility wrapper: 1")
    print("[INFO] Out-of-scope direct-SQL routes remain documented, not silently refactored")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"[FAIL] {exc}")
        raise SystemExit(1)
