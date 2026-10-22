"""Data models for taskgraph targets, graphs, findings, and reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Severity(str, Enum):
    """Severity levels used by findings and configuration thresholds."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

    def rank(self) -> int:
        """Return a comparable numeric rank for the severity."""
        return {Severity.INFO: 0, Severity.WARNING: 1, Severity.ERROR: 2}[self]


@dataclass
class TaskTarget:
    """A normalized task target discovered from a build file."""

    name: str
    source: str
    location: str = ""
    prerequisites: List[str] = field(default_factory=list)
    commands: List[str] = field(default_factory=list)
    phony: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "name": self.name,
            "source": self.source,
            "location": self.location,
            "prerequisites": list(self.prerequisites),
            "commands": list(self.commands),
            "phony": self.phony,
            "metadata": self.metadata,
        }


@dataclass
class TaskEdge:
    """A directed dependency edge from a task to a prerequisite."""

    source: str
    target: str
    kind: str = "prerequisite"

    def to_dict(self) -> Dict[str, str]:
        """Return a JSON-serializable representation."""
        return {"source": self.source, "target": self.target, "kind": self.kind}


@dataclass
class Finding:
    """A diagnostic finding produced while auditing a task graph."""

    code: str
    message: str
    severity: Severity = Severity.WARNING
    target: Optional[str] = None
    location: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "target": self.target,
            "location": self.location,
        }


@dataclass
class TaskGraph:
    """A normalized dependency graph for tasks in a project."""

    root: str = "."
    targets: Dict[str, TaskTarget] = field(default_factory=dict)
    edges: List[TaskEdge] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def adjacency(self) -> Dict[str, List[str]]:
        """Return outgoing prerequisite adjacency for each target."""
        result: Dict[str, List[str]] = {name: [] for name in self.targets}
        for edge in self.edges:
            result.setdefault(edge.source, []).append(edge.target)
        return result

    def dependents(self) -> Dict[str, List[str]]:
        """Return reverse adjacency for each target."""
        result: Dict[str, List[str]] = {name: [] for name in self.targets}
        for edge in self.edges:
            result.setdefault(edge.target, []).append(edge.source)
        return result

    def cycles(self) -> List[List[str]]:
        """Return simple dependency cycles found in the graph."""
        adjacency = self.adjacency()
        color: Dict[str, int] = {}
        stack: List[str] = []
        found: List[List[str]] = []

        def visit(node: str) -> None:
            color[node] = 1
            stack.append(node)
            for neighbor in adjacency.get(node, []):
                if neighbor not in self.targets:
                    continue
                if neighbor not in color:
                    visit(neighbor)
                elif color.get(neighbor) == 1 and neighbor in stack:
                    index = stack.index(neighbor)
                    found.append(list(stack[index:]))
            stack.pop()
            color[node] = 2

        for node in list(self.targets):
            if node not in color:
                visit(node)
        return found

    def topological_levels(self) -> List[List[str]]:
        """Return parallel-safe topological levels for acyclic dependencies."""
        adjacency = self.adjacency()
        reverse = self.dependents()
        indegree = {name: len(adjacency.get(name, [])) for name in self.targets}
        current = [name for name, degree in indegree.items() if degree == 0]
        levels: List[List[str]] = []
        while current:
            levels.append(sorted(current))
            nxt: List[str] = []
            for node in current:
                for dependent in reverse.get(node, []):
                    if dependent in indegree:
                        indegree[dependent] -= 1
                        if indegree[dependent] == 0:
                            nxt.append(dependent)
            current = nxt
        return levels

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "root": self.root,
            "targets": {name: target.to_dict() for name, target in self.targets.items()},
            "edges": [edge.to_dict() for edge in self.edges],
            "findings": [finding.to_dict() for finding in self.findings],
            "metadata": self.metadata,
            "levels": self.topological_levels(),
        }
