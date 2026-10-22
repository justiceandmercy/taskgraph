"""Report formatting for task graph audits."""

from __future__ import annotations

import json
from typing import Any, List, Optional

try:
    from ..graph import TaskGraph
    from ..checks import Finding
except Exception:  # pragma: no cover
    from taskgraph.graph import TaskGraph
    from taskgraph.checks import Finding


def render_text(
    findings: List[Finding],
    graph: Optional[TaskGraph] = None,
    show_graph: bool = False,
) -> str:
    """Render findings and optional graph as human-readable text."""
    lines: List[str] = []
    errors = sum(1 for f in findings if f.severity == "error")
    warnings = sum(1 for f in findings if f.severity == "warning")
    infos = sum(1 for f in findings if f.severity == "info")
    lines.append(f"taskgraph: {errors} error(s), {warnings} warning(s), {infos} info")
    if findings:
        lines.append("")
        for finding in findings:
            location = f" ({finding.source})" if finding.source else ""
            lines.append(f"[{finding.severity}] {finding.rule}: {finding.target}{location} - {finding.message}")
    else:
        lines.append("no findings")
    if show_graph and graph is not None:
        lines.append("")
        lines.append("execution levels:")
        for index, level in enumerate(graph.topological_levels(), start=1):
            lines.append(f"  level {index}: {', '.join(level)}")
        cycle_nodes = graph.cycle_nodes()
        if cycle_nodes:
            lines.append("  cycles: " + ", ".join(sorted(cycle_nodes)))
    return "\n".join(lines) + "\n"


def render_json(
    findings: List[Finding],
    graph: Optional[TaskGraph] = None,
) -> str:
    """Render findings and optional graph as machine-readable JSON."""
    payload: dict[str, Any] = {
        "findings": [f.to_dict() for f in findings],
        "summary": {
            "errors": sum(1 for f in findings if f.severity == "error"),
            "warnings": sum(1 for f in findings if f.severity == "warning"),
            "infos": sum(1 for f in findings if f.severity == "info"),
        },
    }
    if graph is not None:
        payload["graph"] = {
            "tasks": [
                {
                    "name": task.name,
                    "source": task.source,
                    "deps": list(task.deps),
                    "command": task.command,
                    "phony": task.phony,
                }
                for task in (graph.get(name) for name in graph.names())
                if task is not None
            ],
            "levels": graph.topological_levels(),
            "cycles": graph.cycles(),
            "missing": [list(pair) for pair in graph.missing_prerequisites()],
            "duplicates": list(graph.duplicates),
        }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_dot(
    graph: TaskGraph,
    findings: Optional[List[Finding]] = None,
) -> str:
    """Render a task graph as Graphviz DOT."""
    findings = findings or []
    dead = {f.target for f in findings if f.rule == "dead-task"}
    cycle_nodes = graph.cycle_nodes()
    lines: List[str] = ["digraph taskgraph {", "  rankdir=LR;", "  node [shape=box];"]
    for name in graph.names():
        attrs = []
        if name in cycle_nodes:
            attrs.append('color="red"')
        if name in dead:
            attrs.append('style="dashed"')
        attr_str = " " + ", ".join(attrs) if attrs else ""
        lines.append(f'  "{name}"{attr_str};')
    for name in graph.names():
        for dep in graph.prerequisites(name):
            if dep in graph:
                lines.append(f'  "{name}" -> "{dep}";')
    lines.append("}")
    return "\n".join(lines) + "\n"
