# taskgraph usage

`taskgraph` audits and visualizes dependency graphs for Makefile, npm, and justfile
task targets. It catches dependency cycles, missing prerequisites, duplicate target
names, and unreachable (dead) tasks before they fail in CI.

## Installation

```bash
pip install taskgraph
```

Or from source:

```bash
pip install -e .
```

The console entry point is `taskgraph` (defined in `pyproject.toml`).

## Configuration

Create a `.taskgraph.toml` in your project root:

```toml
[scan]
include = ["Makefile", "package.json", "justfile"]
exclude = ["node_modules", "vendor"]

[parsers]
makefile = true
npm = true
justfile = true

[thresholds]
max_cycle_severity = "error"

[baseline]
ignore = ["legacy-build"]
```

Fields:

- `include` / `exclude`: glob patterns for files to scan.
- `parsers.*`: enable or disable individual parsers.
- `thresholds.max_cycle_severity`: severity level that fails `check`.
- `baseline.ignore`: target names to skip during checks.

## Commands

### scan

```bash
taskgraph scan .
```

Discover and parse task files, printing a summary of targets and dependencies.
Exits `0` on success.

### check

```bash
taskgraph check .
```

Validate the graph: cycles, missing prerequisites, duplicates, dead tasks.
Exits non-zero when issues exceed the configured severity threshold. Suitable
for CI gates.

### graph

```bash
taskgraph graph . --format dot
```

Render the dependency graph. Supported formats: `text`, `json`, `dot`.

### export

```bash
taskgraph export . --format json --output graph.json
```

Write a machine-readable report to a file.

## Output formats

- **text**: human-readable summary with levels and issues.
- **json**: machine-readable object with `tasks`, `levels`, `issues`.
- **dot**: Graphviz DOT for visualization (`dot -Tpng graph.dot -o graph.png`).

## Examples

Audit a mixed project:

```bash
taskgraph check .
taskgraph graph . --format dot > graph.dot
dot -Tsvg graph.dot -o graph.svg
```

Baseline a known cycle:

```toml
[baseline]
ignore = ["legacy-self-loop"]
```

## Exit codes

- `0`: success / no issues above threshold.
- `1`: issues found or runtime error.
- `2`: usage error.
