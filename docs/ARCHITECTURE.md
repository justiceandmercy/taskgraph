# Architecture

taskgraph — Audit and visualize dependency graphs for Makefile, npm, and justfile task targets, catching cycles, missing prerequisites, and dead tasks.

## Overview

The codebase is organized around a small set of focused modules. Each module owns a
single responsibility and the public surface is kept deliberately small so the tool
stays easy to hack on.

## Module map

| Path | Responsibility |
| ---- | -------------- |
| `pyproject.toml` | Package metadata, console script entry point, dependencies, and test configuration. |
| `src/main.py` | Thin executable entry point that invokes the taskgraph CLI application. |
| `src/taskgraph/__init__.py` | Package version and public API exports for library use. |
| `src/taskgraph/cli.py` | Argument parsing and dispatch for scan, check, graph, and export subcommands. |
| `src/taskgraph/config.py` | Load and validate .taskgraph.toml settings, include rules, and baselines. |
| `src/taskgraph/models.py` | Dataclasses for targets, edges, task graphs, findings, and severity levels. |
| `src/taskgraph/parsers/__init__.py` | Parser registry and shared interfaces for task source formats. |
| `src/taskgraph/parsers/makefile.py` | Parse Makefile targets, prerequisites, phony declarations, and command references. |
| `src/taskgraph/parsers/npm.py` | Parse package.json scripts and infer dependencies from npm run invocations. |
| `src/taskgraph/graph.py` | Build the task graph, detect cycles, compute reachability, and topological levels. |
| `src/taskgraph/checks.py` | Implement audit rules for missing prerequisites, cycles, duplicates, and dead tasks. |
| `src/taskgraph/reporters.py` | Format findings and graphs as text, JSON, or Graphviz DOT output. |
| `tests/test_parsers.py` | Test Makefile and npm script parsing against representative fixtures. |
| `tests/test_graph.py` | Test cycle detection, topological ordering, and reachability calculations. |
| `tests/test_cli.py` | Test subcommand behavior, configuration loading, and exit codes. |
| `docs/usage.md` | Document installation, configuration, commands, output formats, and examples. |

## Key design decisions

- **Zero/low runtime dependencies**: the core works from the standard library so
  installs stay fast and supply-chain risk stays low.
- **Configuration before convention**: behavior is tunable through config files and
  documented CLI flags instead of magic environment variables.
- **Structured output modes**: human-readable text by default, machine-readable JSON
  for automation, and DOT/Mermaid exports where a graph applies.
- **Everything is guarded by tests**: the CI matrix runs the suite on every push.

## Data flow

`CLI entrypoint -> config loading -> per-item scanning/processing -> aggregation ->
reporting (text | JSON | graph)`.

## Testing

Unit tests cover Makefile and package.json parsing, graph cycle and topological algorithms, audit rules, configuration loading, and CLI exit codes; integration tests run against fixture repositories with expected findings and baseline handling.

Run them locally with `pytest -q`. CI (`.github/workflows/ci.yml`) executes the
same suite on a version matrix for every push and pull request.
