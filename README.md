# taskgraph

[![CI](https://github.com/justiceandmercy/taskgraph/actions/workflows/ci.yml/badge.svg)](https://github.com/justiceandmercy/taskgraph/actions/workflows/ci.yml)


> Audit and visualize dependency graphs for Makefile, npm, and justfile task targets, catching cycles, missing prerequisites, and dead tasks.

[![CI](https://github.com/justiceandmercy/taskgraph/actions/workflows/ci.yml/badge.svg)](https://github.com/justiceandmercy/taskgraph/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Topics:** task-graph, build-tools, cli, developer-tools, makefile, npm-scripts

## Features

- Parse Makefile targets and prerequisites into a normalized task graph, including .PHONY declarations and command-derived npm run references.
- Parse package.json scripts and infer implicit dependencies from npm run and cross-script invocations.
- Detect dependency cycles, missing prerequisites, duplicate target names, and unreachable tasks before they fail in CI.
- Provide a topological execution plan with parallel-safe levels for task runners and build scripts.
- Render reports as human-readable text, machine-readable JSON, or Graphviz DOT for visualization.
- Configure include and exclude globs, parser enablement, and severity thresholds through .taskgraph.toml.
- Support scan, check, graph, and export subcommands with consistent exit codes for automation.
- Allow baseline and ignore rules for known intentional cycles or legacy targets.

## Install

git clone https://github.com/justiceandmercy/taskgraph.git
cd taskgraph
pip install .

## Quick start

taskgraph --help

Entry point: `src/main.py`.

## Architecture

- `pyproject.toml` — Package metadata, console script entry point, dependencies, and test configuration.
- `src/main.py` — Thin executable entry point that invokes the taskgraph CLI application.
- `src/taskgraph/__init__.py` — Package version and public API exports for library use.
- `src/taskgraph/cli.py` — Argument parsing and dispatch for scan, check, graph, and export subcommands.
- `src/taskgraph/config.py` — Load and validate .taskgraph.toml settings, include rules, and baselines.
- `src/taskgraph/models.py` — Dataclasses for targets, edges, task graphs, findings, and severity levels.
- `src/taskgraph/parsers/__init__.py` — Parser registry and shared interfaces for task source formats.
- `src/taskgraph/parsers/makefile.py` — Parse Makefile targets, prerequisites, phony declarations, and command references.
- `src/taskgraph/parsers/npm.py` — Parse package.json scripts and infer dependencies from npm run invocations.
- `src/taskgraph/graph.py` — Build the task graph, detect cycles, compute reachability, and topological levels.
- `src/taskgraph/checks.py` — Implement audit rules for missing prerequisites, cycles, duplicates, and dead tasks.
- `src/taskgraph/reporters.py` — Format findings and graphs as text, JSON, or Graphviz DOT output.
- `tests/test_parsers.py` — Test Makefile and npm script parsing against representative fixtures.
- `tests/test_graph.py` — Test cycle detection, topological ordering, and reachability calculations.
- `tests/test_cli.py` — Test subcommand behavior, configuration loading, and exit codes.
- `docs/usage.md` — Document installation, configuration, commands, output formats, and examples.

For the full module map and design decisions, read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Testing

pytest -q

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). PRs welcome!

## License

MIT — see [LICENSE](LICENSE).
