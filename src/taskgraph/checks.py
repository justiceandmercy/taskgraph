"""Audit rules for task graphs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Sequence

try:
    from ..graph import TaskGraph
except Exception:  # pragma: no cover
    from taskgraph.graph import TaskGraph


@dataclass
class Finding:
    """A single audit finding."""

    rule: str
    severity: str
    target: str
    message: str
    source: str = ""

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "target": self.target,
            "message": self.message,
            "source": self.source,
        }


SEVERITY_RANK = {"info": 0, "warning": 1, "error": 2}


def _source_for(graph: TaskGraph, name: str) -> str:
    task = graph.get(name)
    return task.source if task else ""


def _ignored(finding: Finding, ignored: set[str]) -> bool:
    return finding.target in ignored or f"{finding.rule}:{finding.target}" in ignored


def run_checks(
    graph: TaskGraph,
    roots: Optional[Iterable[str]] = None,
    ignored: Optional[Iterable[str]] = None,
    min_severity: str = "info",
    config: Optional[dict] = None,
) -> List[Finding]:
    """Run all audit rules and return findings sorted by severity."""
    ignored_set = set(ignored or [])
    if config:
        ignored_set.update(config.get("ignore", []) or [])
        min_severity = config.get("min_severity", min_severity)
    findings: List[Finding] = []

    for task_name, dep in graph.missing_prerequisites():
        findings.append(
            Finding(
                rule="missing-prerequisite",
                severity="error",
                target=task_name,
                message=f"missing prerequisite '{dep}'",
                source=_source_for(graph, task_name),
            )
        )

    for cycle in graph.cycles():
        target = ",".join(cycle)
        findings.append(
            Finding(
                rule="cycle",
                severity="error",
                target=target,
                message="dependency cycle: " + " -> ".join(cycle + [cycle[0]]),
            )
        )

    for name in graph.duplicates:
        findings.append(
            Finding(
                rule="duplicate-target",
                severity="error",
                target=name,
                message="duplicate target name",
                source=_source_for(graph, name),
            )
        )

    for name in graph.unreachable(roots):
        findings.append(
            Finding(
                rule="dead-task",
                severity="warning",
                target=name,
                message="task is unreachable from entry tasks",
                source=_source_for(graph, name),
            )
        )

    threshold = SEVERITY_RANK.get(min_severity, 0)
    filtered = [
        finding
        for finding in findings
        if SEVERITY_RANK.get(finding.severity, 0) >= threshold and not _ignored(finding, ignored_set)
    ]
    filtered.sort(key=lambda f: (-SEVERITY_RANK.get(f.severity, 0), f.target, f.rule))
    return filtered


def has_errors(findings: Sequence[Finding]) -> bool:
    """Return True if any finding has error severity."""
    return any(f.severity == "error" for f in findings)


def exit_code(findings: Sequence[Finding]) -> int:
    """Consistent automation exit code: 0 clean, 1 warnings, 2 errors."""
    if any(f.severity == "error" for f in findings):
        return 2
    if findings:
        return 1
    return 0
