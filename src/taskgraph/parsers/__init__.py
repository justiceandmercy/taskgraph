"""Parser registry and shared interfaces for taskgraph sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Type

from ..config import TaskgraphConfig
from ..models import TaskGraph


class BaseParser(ABC):
    """Abstract base class for all task source parsers."""

    name: str = ""

    @abstractmethod
    def can_parse(self, path: Path) -> bool:
        """Return True when this parser handles the given path."""

    @abstractmethod
    def parse(self, path: Path, graph: TaskGraph) -> None:
        """Parse a source file and populate the graph."""


class ParserRegistry:
    """Registry of available parsers keyed by name."""

    def __init__(self) -> None:
        self._parsers: Dict[str, Type[BaseParser]] = {}

    def register(self, name: str, parser_cls: Type[BaseParser]) -> None:
        """Register a parser class under a name."""
        if not name:
            raise ValueError("Parser name must be non-empty")
        self._parsers[name] = parser_cls

    def get(self, name: str) -> Optional[Type[BaseParser]]:
        """Look up a parser class by name."""
        return self._parsers.get(name)

    def names(self) -> List[str]:
        """Return sorted registered parser names."""
        return sorted(self._parsers)

    def parsers_for(self, path: Path) -> List[Type[BaseParser]]:
        """Return parser classes that claim to handle path."""
        result: List[Type[BaseParser]] = []
        for cls in self._parsers.values():
            try:
                instance = cls()
            except Exception:
                continue
            if instance.can_parse(path):
                result.append(cls)
        return result

    def parse_path(
        self,
        path: Path,
        graph: TaskGraph,
        config: Optional[TaskgraphConfig] = None,
    ) -> None:
        """Parse a single path with all applicable enabled parsers."""
        for cls in self.parsers_for(path):
            name = getattr(cls, "name", "")
            if config is not None and name and not config.is_parser_enabled(name):
                continue
            try:
                cls().parse(path, graph)
            except Exception as exc:  # pragma: no cover - defensive
                graph.findings.append(
                    FindingLike(
                        kind="parse_error",
                        severity=Severity.ERROR,
                        message=f"Failed to parse {path}: {exc}",
                        location=None,
                    )
                )


def create_default_registry() -> ParserRegistry:
    """Build a registry populated with built-in parsers."""
    registry = ParserRegistry()
    try:
        from .makefile import MakefileParser

        registry.register("makefile", MakefileParser)
    except Exception:
        pass
    try:
        from .npm import NpmParser

        registry.register("npm", NpmParser)
    except Exception:
        pass
    try:
        from .justfile import JustfileParser

        registry.register("justfile", JustfileParser)
    except Exception:
        pass
    return registry


# Avoid circular import issues by importing models lazily.
from ..models import Finding as FindingLike, Severity
