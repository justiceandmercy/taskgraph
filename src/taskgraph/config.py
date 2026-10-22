"""Configuration loading and validation for taskgraph."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .models import Severity


@dataclass
class TaskgraphConfig:
    """Validated taskgraph configuration."""

    root: Path
    include: List[str] = field(default_factory=lambda: [
        "Makefile", "makefile", "GNUmakefile", "*.mk", "package.json",
        "justfile", "Justfile", "*.just",
    ])
    exclude: List[str] = field(default_factory=lambda: [
        ".git", "node_modules", "dist", "build", ".venv", "__pycache__",
    ])
    parsers: Dict[str, bool] = field(default_factory=lambda: {
        "make": True, "npm": True, "just": True,
    })
    severity_threshold: Severity = Severity.WARNING
    baseline: Optional[Path] = None
    ignores: List[Dict[str, Any]] = field(default_factory=list)

    def matches_include(self, relative_path: str) -> bool:
        """Return whether a relative path matches an include glob."""
        name = Path(relative_path).name
        return any(fnmatch(relative_path, pattern) or fnmatch(name, pattern) for pattern in self.include)

    def matches_exclude(self, relative_path: str) -> bool:
        """Return whether a relative path should be excluded."""
        parts = Path(relative_path).parts
        if any(part in self.exclude for part in parts):
            return True
        return any(fnmatch(relative_path, pattern) or fnmatch(Path(relative_path).name, pattern)
                   for pattern in self.exclude)


def find_config(start: Path) -> Optional[Path]:
    """Find the nearest .taskgraph.toml file at or above start."""
    current = start if start.is_dir() else start.parent
    for candidate in [current, *current.parents]:
        path = candidate / ".taskgraph.toml"
        if path.is_file():
            return path
    return None


def _as_list(value: Any, field_name: str) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings")
    return value


def _parse_severity(value: Any) -> Severity:
    if isinstance(value, Severity):
        return value
    if not isinstance(value, str):
        raise ValueError("severity must be a string")
    try:
        return Severity(value.lower())
    except ValueError as exc:
        raise ValueError(f"unknown severity: {value}") from exc


def load_config(start: Optional[Path] = None) -> TaskgraphConfig:
    """Load and validate configuration from .taskgraph.toml."""
    root = (start or Path.cwd()).resolve()
    search_root = root if root.is_dir() else root.parent
    config_path = find_config(search_root)
    base_root = config_path.parent if config_path else search_root
    config = TaskgraphConfig(root=base_root)
    if config_path is None:
        return config

    with config_path.open("rb") as handle:
        raw = tomllib.load(handle)
    section = raw.get("taskgraph", raw)
    if not isinstance(section, dict):
        raise ValueError("[taskgraph] configuration must be a table")

    if "include" in section:
        config.include = _as_list(section["include"], "include")
    if "exclude" in section:
        config.exclude = _as_list(section["exclude"], "exclude")
    if "severity" in section:
        config.severity_threshold = _parse_severity(section["severity"])
    if "baseline" in section and section["baseline"] is not None:
        config.baseline = Path(section["baseline"])
    if "ignores" in section or "ignore" in section:
        ignores = section.get("ignores", section.get("ignore", []))
        if not isinstance(ignores, list):
            raise ValueError("ignore rules must be a list")
        config.ignores = ignores
    parsers = section.get("parsers", {})
    if parsers:
        if not isinstance(parsers, dict):
            raise ValueError("parsers must be a table")
        for name, enabled in parsers.items():
            if not isinstance(enabled, bool):
                raise ValueError(f"parser {name!r} must be true or false")
            config.parsers[str(name)] = enabled
    return config


def load_baseline(config: TaskgraphConfig) -> Set[tuple[str, str]]:
    """Load baseline finding identifiers from the configured baseline file."""
    if config.baseline is None:
        return set()
    path = config.baseline if config.baseline.is_absolute() else config.root / config.baseline
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    items = data.get("findings", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return set()
    result: Set[tuple[str, str]] = set()
    for item in items:
        if isinstance(item, dict):
            result.add((str(item.get("code", "")), str(item.get("target", "") or "")))
        elif isinstance(item, str):
            result.add((item, ""))
    return result
