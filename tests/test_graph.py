"""Tests for cycle detection, topological ordering, and reachability."""

import pytest

from taskgraph.graph import CycleError, TaskGraph


def _graph(edges):
    graph = TaskGraph()
    for name, deps in edges.items():
        graph.add_task(name, dependencies=deps)
    # ensure dependency-only nodes exist
    for deps in edges.values():
        for dep in deps:
            if dep not in edges:
                graph.add_task(dep, dependencies=[])
    return graph


def test_topological_levels_linear():
    graph = _graph({"a": [], "b": ["a"], "c": ["b"]})
    levels = graph.topological_levels()
    assert levels == [["a"], ["b"], ["c"]]


def test_topological_levels_parallel():
    graph = _graph({"build": [], "lint": [], "test": ["build", "lint"]})
    levels = graph.topological_levels()
    assert levels[0] == sorted(["build", "lint"])
    assert levels[1] == ["test"]


def test_cycle_detection_raises():
    graph = _graph({"a": ["b"], "b": ["a"]})
    with pytest.raises(CycleError):
        graph.topological_levels()


def test_find_cycles_returns_list():
    graph = _graph({"a": ["b"], "b": ["c"], "c": ["a"]})
    cycles = graph.find_cycles()
    assert len(cycles) >= 1
    assert {"a", "b", "c"}.issubset(set(cycles[0]))


def test_no_cycles_empty():
    graph = _graph({"a": [], "b": []})
    assert graph.find_cycles() == []


def test_missing_prerequisites():
    graph = TaskGraph()
    graph.add_task("build", dependencies=["ghost"])
    assert graph.missing_prerequisites() == {"build": ["ghost"]}


def test_reachable_from():
    graph = _graph({"a": [], "b": ["a"], "c": ["b"], "d": []})
    assert graph.reachable_from("c") == {"c", "b", "a"}
    assert graph.reachable_from("d") == {"d"}


def test_dead_tasks():
    graph = _graph({"entry": ["used"], "used": [], "orphan": []})
    dead = graph.dead_tasks(roots=["entry"])
    assert "orphan" in dead
    assert "entry" not in dead
    assert "used" not in dead


def test_dead_tasks_no_roots_marks_all():
    graph = _graph({"a": [], "b": []})
    # without roots, nothing is reachable; treat all as dead only if no edges
    dead = graph.dead_tasks(roots=[])
    assert set(dead) == {"a", "b"}


def test_duplicate_target_name():
    graph = TaskGraph()
    graph.add_task("build", dependencies=[])
    with pytest.raises(ValueError):
        graph.add_task("build", dependencies=[])


def test_topological_order_flat():
    graph = _graph({"x": [], "y": [], "z": []})
    order = graph.topological_order()
    assert set(order) == {"x", "y", "z"}
    assert len(order) == 3


def test_self_loop_is_cycle():
    graph = _graph({"a": ["a"]})
    assert len(graph.find_cycles()) >= 1
