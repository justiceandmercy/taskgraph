"""Thin executable entry point for the taskgraph command line application."""

from taskgraph.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
