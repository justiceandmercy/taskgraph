"""Tests for CLI subcommands, configuration loading, and exit codes."""

import json
from pathlib import Path

from taskgraph.cli import main
from taskgraph.config import load_config


MAKEFILE = "all: build\nbuild:\n\techo hi\nclean:\n\trm -rf x\n"


def test_scan_returns_zero_on_success(tmp_path: Path):
    (tmp_path / "Makefile").write_text(MAKEFILE)
    rc = main(["scan", str(tmp_path)])
    assert rc == 0


def test_check_detects_missing_prereq(tmp_path: Path, capsys):
    (tmp_path / "Makefile").write_text("build: ghost\n\techo hi\n")
    rc = main(["check", str(tmp_path)])
    assert rc != 0
    captured = capsys.readouterr()
    assert "ghost" in (captured.out + captured.err)


def test_check_clean_returns_zero(tmp_path: Path):
    (tmp_path / "Makefile").write_text(MAKEFILE)
    rc = main(["check", str(tmp_path)])
    assert rc == 0


def test_graph_outputs_dot(tmp_path: Path, capsys):
    (tmp_path / "Makefile").write_text(MAKEFILE)
    rc = main(["graph", str(tmp_path), "--format", "dot"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "digraph" in out


def test_export_writes_json(tmp_path: Path):
    (tmp_path / "Makefile").write_text(MAKEFILE)
    out_file = tmp_path / "out.json"
    rc = main(["export", str(tmp_path), "--format", "json", "--output", str(out_file)])
    assert rc == 0
    data = json.loads(out_file.read_text())
    assert "tasks" in data


def test_help_lists_subcommands(capsys):
    try:
        main(["--help"])
    except SystemExit as exc:
        assert exc.code in (0, None)
    out = capsys.readouterr().out
    for cmd in ("scan", "check", "graph", "export"):
        assert cmd in out


def test_load_config_defaults(tmp_path: Path):
    cfg = load_config(tmp_path)
    assert cfg is not None
    assert getattr(cfg, "include", None) is None or isinstance(cfg.include, list)


def test_load_config_from_toml(tmp_path: Path):
    (tmp_path / ".taskgraph.toml").write_text(
        '[scan]\ninclude = ["Makefile"]\nexclude = ["node_modules"]\n'
        '[parsers]\nmakefile = true\nnpm = true\n'
        '[thresholds]\nmax_cycle_severity = "error"\n'
    )
    cfg = load_config(tmp_path)
    assert "Makefile" in (cfg.include or [])
    assert cfg.parsers.get("npm", True) is True


def test_unknown_subcommand_returns_nonzero():
    try:
        rc = main(["frobnicate"])
    except SystemExit as exc:
        rc = exc.code
    assert rc not in (0, None)
