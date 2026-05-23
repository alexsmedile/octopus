"""Octopus TUI — Textual-based daily-driver interface.

Public entry point: `octopus.tui.app.OctopusApp`.

Heavy imports (Textual) live in submodules so importing this package alone is cheap.
The Typer command in `octopus.cli` only imports `OctopusApp` inside its function body.
"""
