"""Parser for Makefile targets and prerequisites."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

from ..models import Edge, Location, Target, TaskGraph


_TARGET_RE = re.compile(r"^([^\t:#][^:#]*?):\s*(.*)$")
_PHONY_RE = re.compile(r"^\.PHONY\s*:\s*(.*)$", re.IGNORECASE)
_NPM_RUN_RE = re.compile(r"\bnpm\s+run\s+([A-Za-z0-9:_.-]+)")
_MAKE_RE = re.compile(r"\bmake\s+([A-Za-z0-9:_.-]+)")


class MakefileParser:
    """Parse a Makefile into taskgraph targets and edges."""

    name = "makefile"

    def can_parse(self, path: Path) -> bool:
        name = path.name
        return name in {"Makefile", "makefile", "GNUmakefile"} or path.suffix in {".mk", ".make"}

    def parse(self, path: Path, graph: TaskGraph) -> None:
        """Parse the Makefile at path and populate graph."""
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"Cannot read Makefile {path}: {exc}") from exc

        lines = text.splitlines()
        phony: set[str] = set()
        for raw in lines:
            match = _PHONY_RE.match(raw.strip())
            if match:
                for token in match.group(1).split():
                    phony.add(token)

        current_target: str | None = None
        for line_number, raw in enumerate(lines, start=1):
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue

            if raw.startswith("\t") or raw.startswith("    "):
                if current_target is None:
                    continue
                command = stripped
                target = graph.targets.get(current_target)
                if target is not None:
                    target.commands.append(command)
                location = Location(path=path, line=line_number)
                for match in _NPM_RUN_RE.finditer(command):
                    graph.add_edge(
                        Edge(
                            source=current_target,
                            target=match.group(1),
                            kind="npm-run",
                            location=location,
                        )
                    )
                for match in _MAKE_RE.finditer(command):
                    graph.add_edge(
                        Edge(
                            source=current_target,
                            target=match.group(1),
                            kind="make-invocation",
                            location=location,
                        )
                    )
                continue

            # Skip variable assignments without a colon.
            code_part = stripped.split("#", 1)[0].strip()
            if "=" in code_part and ":" not in code_part:
                continue

            match = _TARGET_RE.match(raw)
            if not match:
                continue

            left = match.group(1).strip()
            prereqs_raw = match.group(2).strip()
            if "#" in prereqs_raw:
                prereqs_raw = prereqs_raw.split("#", 1)[0].strip()
            prerequisites = prereqs_raw.split() if prereqs_raw else []

            target_names = left.split()
            for target_name in target_names:
                location = Location(path=path, line=line_number)
                target = Target(
                    name=target_name,
                    location=location,
                    prerequisites=list(prerequisites),
                    phony=target_name in phony,
                    source="makefile",
                )
                graph.add_target(target)
                for prereq in prerequisites:
                    graph.add_edge(
                        Edge(
                            source=target_name,
                            target=prereq,
                            kind="prerequisite",
                            location=location,
                        )
                    )
            current_target = target_names[-1] if target_names else current_target
