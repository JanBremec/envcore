"""
Configuration management for envcore.

Reads per-project settings from ``pyproject.toml`` under ``[tool.envcore]``,
with fallback to sensible defaults.

Example configuration::

    # pyproject.toml
    [tool.envcore]
    manifest = "env_manifest.json"
    exclude = ["setuptools", "pip", "wheel"]
    entry_points = ["src/main.py", "src/api.py"]
    auto_export = "requirements.txt"
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class EnvcoreConfig:
    """Project-level envcore configuration."""

    manifest: str = "env_manifest.json"
    """Default manifest file path."""

    exclude: list[str] = field(default_factory=lambda: [
        "setuptools", "pip", "wheel", "distribute", "pkg-resources",
    ])
    """Packages to always exclude from tracing."""

    entry_points: list[str] = field(default_factory=list)
    """Default scripts to trace."""

    auto_export: Optional[str] = None
    """If set, automatically export to this format after tracing."""

    watch_dirs: list[str] = field(default_factory=list)
    """Directories to watch in watch mode."""


def load_config(project_dir: str | Path = ".") -> EnvcoreConfig:
    """Load envcore config from ``pyproject.toml`` in *project_dir*.

    Returns default config if no ``[tool.envcore]`` section exists.
    """
    pyproject = Path(project_dir) / "pyproject.toml"

    if not pyproject.exists():
        return EnvcoreConfig()

    try:
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
    except Exception:  # noqa: BLE001
        return EnvcoreConfig()

    envcore_data = data.get("tool", {}).get("envcore", {})
    if not envcore_data:
        return EnvcoreConfig()

    config = EnvcoreConfig()

    if "manifest" in envcore_data:
        config.manifest = envcore_data["manifest"]
    if "exclude" in envcore_data:
        config.exclude = list(envcore_data["exclude"])
    if "entry_points" in envcore_data:
        config.entry_points = list(envcore_data["entry_points"])
    if "auto_export" in envcore_data:
        config.auto_export = envcore_data["auto_export"]
    if "watch_dirs" in envcore_data:
        config.watch_dirs = list(envcore_data["watch_dirs"])

    return config
