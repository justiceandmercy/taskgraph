"""Task graph construction, cycle detection, and topological analysis."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple


@dataclass
class Task:
    """A single task node in a dependency graph."""

    name: str
    source: str = ""
    deps: List[str] = field(default_factory=list)
    command: str = ""
    phony: bool = False
    metadata: dict = field(default_factory=dict)


class TaskGraph:
    """Directed dependency graph where edges point from task to prerequisite."""

    def __init__(self, tasks: Optional[Iterable[Task]] = None) -> None:
        self.tasks: Dict[str, Task] = {}
        self._insertion: List[str] = []
        self.duplicates: List[str] = []
        if tasks is not None:
            for task in tasks:
                self.add(task)

    def add(self, task: Task) -> None:
        """Add a task, merging duplicate names and recording duplicates."""
        if task.name in self.tasks:
            self.duplicates.append(task.name)
            existing = self.tasks[task.name]
            for dep in task.deps:
                if dep not in existing.deps:
                    existing.deps.append(dep)
            if task.source and not existing.source:
                existing.source = task.source
            if task.command and not existing.command:
                existing.command = task.command
            if task.phony:
                existing.phony = True
            existing.metadata.update(task.metadata)
        else:
            self.tasks[task.name] = task
            self._insertion.append(task.name)

    def __len__(self) -> int:
        return len(self.tasks)

    def __contains__(self, name: object) -> bool:
        return name in self.tasks

    def names(self) -> List[str]:
        """Return task names in insertion order."""
        return list(self._insertion)

    def get(self, name: str) -> Optional[Task]:
        return self.tasks.get(name)

    def prerequisites(self, name: str) -> List[str]:
        task = self.tasks.get(name)
        return list(task.deps) if task else []

    def dependents(self, name: str) -> List[str]:
        """Tasks that directly depend on ``name``."""
        return [n for n, task in self.tasks.items() if name in task.deps]

    def roots(self) -> List[str]:
        """Tasks that nothing depends on (top-level entry points)."""
        dependents = {n for n, task in self.tasks.items() for dep in task.deps}
        return [n for n in self._insertion if n not in dependents]

    def missing_prerequisites(self) -> List[Tuple[str, str]]:
        """Return (task, prerequisite) pairs for unknown prerequisites."""
        result: List[Tuple[str, str]] = []
        for name in self._insertion:
            for dep in self.tasks[name].deps:
                if dep not in self.tasks:
                    result.append((name, dep))
        return result

    def cycles(self) -> List[List[str]]:
        """Return strongly connected components with more than one node or a self-loop."""
        index = 0
        indices: Dict[str, int] = {}
        lowlink: Dict[str, int] = {}
        on_stack: Dict[str, bool] = {}
        stack: List[str] = []
        result: List[List[str]] = []

        import sys

        sys.setrecursionlimit(max(1000, len(self.tasks) + 100))

        def strongconnect(node: str) -> None:
            nonlocal index
            indices[node] = index
            lowlink[node] = index
            index += 1
            stack.append(node)
            on_stack[node] = True

            for dep in self.tasks[node].deps:
                if dep not in self.tasks:
                    continue
                if dep not in indices:
                    strongconnect(dep)
                    lowlink[node] = min(lowlink[node], lowlink[dep])
                elif on_stack.get(dep, False):
                    lowlink[node] = min(lowlink[node], indices[dep])

            if lowlink[node] == indices[node]:
                component: List[str] = []
                while True:
                    member = stack.pop()
                    on_stack[member] = False
                    component.append(member)
                    if member == node:
                        break
                if len(component) > 1 or (len(component) == 1 and component[0] in self.tasks[component[0]].deps):
                    result.append(sorted(component))

        for node in self._insertion:
            if node not in indices:
                strongconnect(node)
        return result

    def cycle_nodes(self) -> Set[str]:
        nodes: Set[str] = set()
        for cycle in self.cycles():
            nodes.update(cycle)
        return nodes

    def topological_levels(self) -> List[List[str]]:
        """Return parallel-safe execution levels for the acyclic portion."""
        cycle_nodes = self.cycle_nodes()
        in_degree: Dict[str, int] = {name: 0 for name in self._insertion if name not in cycle_nodes}
        dependents_map: Dict[str, List[str]] = defaultdict(list)
        for name in in_degree:
            for dep in self.tasks[name].deps:
                if dep in in_degree:
                    in_degree[name] += 1
                    dependents_map[dep].append(name)

        queue: deque[str] = deque(n for n in self._insertion if n in in_degree and in_degree[n] == 0)
        levels: List[List[str]] = []
        placed: Set[str] = set()
        while queue:
            level = sorted(queue)
            queue.clear()
            levels.append(level)
            for node in level:
                placed.add(node)
                for dependent in dependents_map[node]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)
        return levels

    def reachable_from(self, roots: Iterable[str]) -> Set[str]:
        """Return nodes reachable by following prerequisites from roots."""
        seen: Set[str] = set()
        stack: List[str] = [r for r in roots if r in self.tasks]
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            task = self.tasks.get(node)
            if not task:
                continue
            for dep in task.deps:
                if dep in self.tasks and dep not in seen:
                    stack.append(dep)
        return seen

    def unreachable(self, roots: Optional[Iterable[str]] = None) -> List[str]:
        """Return task names not reachable from the given or default roots."""
        if roots is None:
            roots = self.roots()
        reachable = self.reachable_from(roots)
        return [name for name in self._insertion if name not in reachable]
