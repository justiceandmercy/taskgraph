"""Tests for Makefile and npm script parsers."""

import json
import textwrap
from pathlib import Path

import pytest

from taskgraph.parsers.makefile import (
    MakefileTask,
    parse_makefile,
    parse_makefile_text,
)
from taskgraph.parsers.npm import (
    NpmScript,
    parse_package_json,
    parse_package_json_text,
)


MAKEFILE_FIXTURE = textwrap.dedent(
    """\
    .PHONY: all clean test

    all: build test
    \t@echo done

    build: src/main.c
    \tgcc src/main.c -o build

    test: build
    \tpytest

    clean:
    \trm -rf build

    release: build
    \techo releasing
    """
)


PACKAGE_JSON_FIXTURE = {
    "name": "demo",
    "version": "1.0.0",
    "scripts": {
        "build": "tsc -p .",
        "test": "npm run build && jest",
        "lint": "eslint .",
        "start": "node dist/index.js",
        "dev": "npm run build && npm run lint",
    },
}


def test_parse_makefile_text_targets():
    tasks = parse_makefile_text(MAKEFILE_FIXTURE)
    assert set(tasks) == {"all", "build", "test", "clean", "release"}
    assert isinstance(tasks["build"], MakefileTask)


def test_makefile_prerequisites():
    tasks = parse_makefile_text(MAKEFILE_FIXTURE)
    assert tasks["all"].prerequisites == ["build", "test"]
    assert tasks["build"].prerequisites == ["src/main.c"]
    assert tasks["test"].prerequisites == ["build"]
    assert tasks["clean"].prerequisites == []


def test_makefile_phony_detection():
    tasks = parse_makefile_text(MAKEFILE_FIXTURE)
    assert tasks["all"].phony is True
    assert tasks["clean"].phony is True
    assert tasks["test"].phony is True
    assert tasks["build"].phony is False
    assert tasks["release"].phony is False


def test_makefile_commands_captured():
    tasks = parse_makefile_text(MAKEFILE_FIXTURE)
    assert any("gcc" in cmd for cmd in tasks["build"].commands)
    assert any("pytest" in cmd for cmd in tasks["test"].commands)


def test_parse_makefile_file(tmp_path: Path):
    path = tmp_path / "Makefile"
    path.write_text(MAKEFILE_FIXTURE)
    tasks = parse_makefile(path)
    assert "all" in tasks
    assert tasks["all"].prerequisites == ["build", "test"]


def test_parse_makefile_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        parse_makefile(tmp_path / "nope.mk")


def test_parse_package_json_text_scripts():
    text = json.dumps(PACKAGE_JSON_FIXTURE)
    scripts = parse_package_json_text(text)
    assert set(scripts) == {"build", "test", "lint", "start", "dev"}
    assert isinstance(scripts["build"], NpmScript)


def test_npm_implicit_dependencies():
    text = json.dumps(PACKAGE_JSON_FIXTURE)
    scripts = parse_package_json_text(text)
    assert "build" in scripts["test"].dependencies
    assert "build" in scripts["dev"].dependencies
    assert "lint" in scripts["dev"].dependencies
    assert scripts["build"].dependencies == []
    assert scripts["start"].dependencies == []


def test_npm_command_preserved():
    text = json.dumps(PACKAGE_JSON_FIXTURE)
    scripts = parse_package_json_text(text)
    assert scripts["build"].command == "tsc -p ."


def test_parse_package_json_file(tmp_path: Path):
    path = tmp_path / "package.json"
    path.write_text(json.dumps(PACKAGE_JSON_FIXTURE))
    scripts = parse_package_json(path)
    assert "test" in scripts


def test_parse_package_json_invalid(tmp_path: Path):
    path = tmp_path / "package.json"
    path.write_text("{not json")
    with pytest.raises(ValueError):
        parse_package_json(path)


def test_npm_cross_script_invocation_with_args():
    payload = {
        "scripts": {
            "a": "npm run b -- --flag",
            "b": "echo b",
        }
    }
    scripts = parse_package_json_text(json.dumps(payload))
    assert "b" in scripts["a"].dependencies
