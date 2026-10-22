"""Parse npm package.json scripts into task graph nodes."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

try:
    from ..graph import Task
except Exception:  # pragma: no cover - fallback for direct module loading
    from taskgraph.graph import Task

_NPM_RUN_RE = re.compile(r"(?:npm|yarn|pnpm)\s+(?:run|run-script)\s+([A-Za-z0-9:_-]+)")
_IMPLICIT_RE = re.compile(r"\bnpm\s+(test|start|build|lint)\b")


def _load(path: str | Path) -> Dict[str, Any]:
    """Load and validate a package.json file."""
    p = Path(path)
    try:
        with p.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read package.json {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"package.json root must be an object: {path}")
    return data


def _infer_deps(command: str, known: set[str]) -> List[str]:
    """Infer script dependencies referenced by an npm command."""
    deps: set[str] = set()
    for match in _NPM_RUN_RE.finditer(command):
        deps.add(match.group(1))
    for match in _IMPLICIT_RE.finditer(command):
        name = match.group(1)
        if name in known:
            deps.add(name)
    return sorted(deps)


def parse_package_json(path: str | Path) -> List[Task]:
    """Parse scripts from a package.json file into Task objects."""
    data = _load(path)
    scripts = data.get("scripts", {})
    if scripts is None:
        scripts = {}
    if not isinstance(scripts, dict):
        raise ValueError("package.json 'scripts' must be an object")
    known = {name for name in scripts if isinstance(name, str)}
    tasks: List[Task] = []
    for name, command in scripts.items():
        if not isinstance(name, str) or not isinstance(command, str):
            continue
        deps = _infer_deps(command, known)
        tasks.append(
            Task(
                name=name,
                source=str(path),
                command=command,
                deps=deps,
                metadata={"script": name},
            )
        )
    return tasks


def parse_package_json_text(text: str, source: str = "package.json") -> List[Task]:
    """Parse scripts from package.json text."""
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        handle.write(text)
        tmp = handle.name
    try:
        tasks = parse_package_json(tmp)
    finally:
        Path(tmp).unlink(missing_ok=True)
    for task in tasks:
        task.source = source
    return tasks
