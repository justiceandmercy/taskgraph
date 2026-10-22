"""Command line interface for taskgraph."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import TaskgraphConfig, load_baseline, load_config
from .models import Finding, Severity, TaskGraph, TaskTarget

MAKE_NAMES = {"Makefile", "makefile", "GNUmakefile"}
JUST_NAMES = {"justfile", "Justfile"}
ROOT_SCRIPTS = {"start", "dev", "build", "test", "lint", "format", "prepare"}


def _scan_files(root: Path, config: TaskgraphConfig) -> List[Path]:
    files: List[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if config.matches_exclude(relative):
            continue
        if config.matches_include(relative):
            files.append(path)
    return sorted(files)


def _path_exists(root: Path, value: str) -> bool:
    candidate = Path(value)
    if candidate.exists():
        return True
    return (root / value).exists()


def _resolve(graph: TaskGraph, name: str) -> Optional[str]:
    for candidate in (name, f"make:{name}", f"npm:{name}", f"just:{name}"):
        if candidate in graph.targets:
            return candidate
    return None


def _add_target(graph: TaskGraph, target: TaskTarget) -> None:
    if target.name in graph.targets:
        graph.findings.append(Finding(
            code="duplicate-target",
            message=f"target {target.name!r} is declared more than once",
            severity=Severity.ERROR,
            target=target.name,
            location=target.location,
        ))
        return
    graph.targets[target.name] = target


def _parse_makefile(path: Path, graph: TaskGraph, root: Path) -> None:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    current: Optional[TaskTarget] = None
    is_first = True
    roots = graph.metadata.setdefault("roots", set())
    phony = graph.metadata.setdefault("phony", set())
    for lineno, raw in enumerate(lines, 1):
        if not raw.strip():
            current = None
            continue
        if raw.startswith(("\t", " ")) and current is not None:
            command = raw.strip()
            current.commands.append(command)
            for match in re.finditer(r"\bnpm\s+run(?:-script)?\s+([A-Za-z0-9:._-]+)", command):
                current.prerequisites.append(f"npm:{match.group(1)}")
            continue
        match = re.match(r"^([^\s#:][^:]*?)\s*:\s*(.*)$", raw)
        if not match:
            current = None
            continue
        names = match.group(1).split()
        prereqs = match.group(2).split()
        if names == [".PHONY"]:
            for item in prereqs:
                phony.add(f"make:{item}")
            current = None
            continue
        if not names or any(name.startswith(".") for name in names):
            current = None
            continue
        for name in names:
            target_name = f"make:{name}"
            target = TaskTarget(
                name=target_name,
                source="make",
                location=f"{path}:{lineno}",
                prerequisites=[f"make:{item}" for item in prereqs],
            )
            _add_target(graph, target)
            if is_first:
                roots.add(target_name)
                is_first = False
            current = target


def _parse_package(path: Path, graph: TaskGraph) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        graph.findings.append(Finding(
            code="invalid-package-json",
            message=f"could not parse {path}",
            severity=Severity.ERROR,
            location=str(path),
        ))
        return
    scripts = data.get("scripts", {})
    if not isinstance(scripts, dict):
        return
    roots = graph.metadata.setdefault("roots", set())
    for name, command in scripts.items():
        target_name = f"npm:{name}"
        target = TaskTarget(
            name=target_name,
            source="npm",
            location=f"{path}:{name}",
            commands=[str(command)],
        )
        for match in re.finditer(r"\bnpm\s+run(?:-script)?\s+([A-Za-z0-9:._-]+)", str(command)):
            target.prerequisites.append(f"npm:{match.group(1)}")
        _add_target(graph, target)
        if name in ROOT_SCRIPTS:
            roots.add(target_name)


def _parse_justfile(path: Path, graph: TaskGraph) -> None:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    current: Optional[TaskTarget] = None
    is_first = True
    roots = graph.metadata.setdefault("roots", set())
    for lineno, raw in enumerate(lines, 1):
        if not raw.strip():
            current = None
            continue
        if raw.startswith(("\t", " ")) and current is not None:
            current.commands.append(raw.strip())
            continue
        match = re.match(r"^([A-Za-z0-9_./-]+)\s*:(.*)$", raw)
        if not match:
            current = None
            continue
        name = match.group(1).strip()
        prereqs = match.group(2).split()
        target_name = f"just:{name}"
        target = TaskTarget(
            name=target_name,
            source="just",
            location=f"{path}:{lineno}",
            prerequisites=[f"just:{item}" for item in prereqs],
        )
        _add_target(graph, target)
        if is_first:
            roots.add(target_name)
            is_first = False
        current = target


def scan_project(root: Path, config: TaskgraphConfig) -> TaskGraph:
    """Scan a project and return its normalized task graph."""
    graph = TaskGraph(root=str(root))
    phony = graph.metadata.setdefault("phony", set())
    for path in _scan_files(root, config):
        if path.name in MAKE_NAMES and config.parsers.get("make", True):
            _parse_makefile(path, graph, root)
        elif path.name == "package.json" and config.parsers.get("npm", True):
            _parse_package(path, graph)
        elif path.name in JUST_NAMES and config.parsers.get("just", True):
            _parse_justfile(path, graph)

    for name in phony:
        if name in graph.targets:
            graph.targets[name].phony = True
            graph.metadata.setdefault("roots", set()).add(name)

    roots = graph.metadata.setdefault("roots", set())
    for target in list(graph.targets.values()):
        for prerequisite in list(target.prerequisites):
            resolved = _resolve(graph, prerequisite)
            if resolved is not None:
                edge = TaskEdge(target.name, resolved)
                if edge not in graph.edges:
                    graph.edges.append(edge)
            else:
                raw = prerequisite.split(":", 1)[-1] if ":" in prerequisite else prerequisite
                if not _path_exists(root, raw):
                    graph.findings.append(Finding(
                        code="missing-prerequisite",
                        message=f"{target.name!r} references missing prerequisite {prerequisite!r}",
                        severity=Severity.ERROR,
                        target=target.name,
                        location=target.location,
                    ))

    for cycle in graph.cycles():
        graph.findings.append(Finding(
            code="dependency-cycle",
            message="dependency cycle: " + " -> ".join(cycle),
            severity=Severity.ERROR,
            target=cycle[0],
        ))

    visited: set[str] = set()
    stack = list(roots)
    adjacency = graph.adjacency()
    while stack:
        node = stack.pop()
        if node in visited or node not in graph.targets:
            continue
        visited.add(node)
        stack.extend(adjacency.get(node, []))
    if not roots:
        visited = set(graph.targets)
    for name, target in graph.targets.items():
        if name not in visited:
            graph.findings.append(Finding(
                code="unreachable-task",
                message=f"task {name!r} is not reachable from configured entry points",
                severity=Severity.WARNING,
                target=name,
                location=target.location,
            ))
    return graph


def _apply_rules(graph: TaskGraph, config: TaskgraphConfig) -> None:
    baseline = load_baseline(config)
    filtered: List[Finding] = []
    for finding in graph.findings:
        key = (finding.code, finding.target or "")
        if key in baseline:
            continue
        ignored = False
        for rule in config.ignores:
            if not isinstance(rule, dict):
                continue
            if rule.get("code") and rule.get("code") != finding.code:
                continue
            if rule.get("target") and not _matches(rule["target"], finding.target or ""):
                continue
            ignored = True
            break
        if not ignored:
            filtered.append(finding)
    graph.findings = filtered


def _matches(pattern: str, value: str) -> bool:
    return re.fullmatch(pattern.replace("*", ".*"), value) is not None or pattern == value


def _render_text(graph: TaskGraph) -> str:
    lines = [
        f"TaskGraph: {graph.root}",
        f"Targets: {len(graph.targets)}",
        f"Edges: {len(graph.edges)}",
        f"Findings: {len(graph.findings)}",
        "",
        "Execution levels:",
    ]
    for index, level in enumerate(graph.topological_levels()):
        lines.append(f"  {index}: {', '.join(level) if level else '(empty)'}")
    if graph.findings:
        lines.append("")
        lines.append("Findings:")
        for finding in graph.findings:
            target = f" [{finding.target}]" if finding.target else ""
            lines.append(f"  {finding.severity.value.upper()} {finding.code}{target}: {finding.message}")
    return "\n".join(lines)


def _render_json(graph: TaskGraph) -> str:
    return json.dumps(graph.to_dict(), indent=2, sort_keys=True)


def _render_dot(graph: TaskGraph) -> str:
    lines = ["digraph taskgraph {", "  rankdir=LR;"]
    for name, target in graph.targets.items():
        label = name.replace('"', '\\"')
        lines.append(f'  "{name}" [label="{label}\n({target.source})"];')
    for edge in graph.edges:
        lines.append(f'  "{edge.source}" -> "{edge.target}";')
    lines.append("}")
    return "\n".join(lines)


def _render(graph: TaskGraph, output_format: str) -> str:
    if output_format == "json":
        return _render_json(graph)
    if output_format == "dot":
        return _render_dot(graph)
    return _render_text(graph)


def _common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", nargs="?", default=".", help="project path to scan")
    parser.add_argument("--config", help="path to .taskgraph.toml")
    parser.add_argument("--format", choices=("text", "json", "dot"), default="text")
    parser.add_argument("--output", help="write report to this file")
    parser.add_argument("--severity", choices=("info", "warning", "error"))


def _load(path: str, config_path: Optional[str]) -> tuple[Path, TaskgraphConfig, TaskGraph]:
    root = Path(path).resolve()
    search = Path(config_path).resolve() if config_path else root
    config = load_config(search)
    if config_path:
        config.root = root
    graph = scan_project(root, config)
    _apply_rules(graph, config)
    if not graph.findings and config.severity_threshold:
        pass
    return root, config, graph


def _threshold(config: TaskgraphConfig, override: Optional[str]) -> Severity:
    if override:
        return Severity(override)
    return config.severity_threshold


def _write(report: str, output: Optional[str]) -> None:
    if output:
        Path(output).write_text(report + "\n", encoding="utf-8")
    else:
        print(report)


def _has_failure(graph: TaskGraph, threshold: Severity) -> bool:
    return any(finding.severity.rank() >= threshold.rank() for finding in graph.findings)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="taskgraph", description="Audit task dependency graphs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="scan a project and report findings")
    _common_arguments(scan_parser)

    check_parser = subparsers.add_parser("check", help="scan and fail on configured findings")
    _common_arguments(check_parser)

    graph_parser = subparsers.add_parser("graph", help="render a dependency graph")
    _common_arguments(graph_parser)
    graph_parser.set_defaults(format="dot")

    export_parser = subparsers.add_parser("export", help="export a report or graph")
    _common_arguments(export_parser)
    export_parser.add_argument("--format", choices=("text", "json", "dot"), default="json")

    args = parser.parse_args(argv)
    try:
        _, config, graph = _load(args.path, args.config)
    except (OSError, ValueError) as exc:
        print(f"taskgraph: {exc}", file=sys.stderr)
        return 2

    report = _render(graph, args.format)
    _write(report, args.output)
    if args.command == "check" and _has_failure(graph, _threshold(config, args.severity)):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
