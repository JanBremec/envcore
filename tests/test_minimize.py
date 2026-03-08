"""Tests for ``envcore.minimize``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from envcore.minimize import minimize


@pytest.fixture()
def manifest_with_deps(tmp_path: Path) -> Path:
    """Create a manifest with click (top-level) and its known dep colorama."""
    path = tmp_path / "env_manifest.json"
    # click depends on colorama on Windows, but we include it to test
    # the top-level vs transitive logic.
    path.write_text(json.dumps({
        "envcore_version": "0.1.0",
        "python_version": "3.11.5",
        "platform": "test",
        "created_at": "2026-03-07T00:00:00+00:00",
        "packages": {
            "click": "8.1.7",
            "pytest": "9.0.1",
            "pluggy": "1.6.0",  # transitive dep of pytest
            "iniconfig": "2.3.0",  # transitive dep of pytest
        },
    }))
    return path


class TestMinimize:
    def test_separates_top_level_and_transitive(self, manifest_with_deps: Path) -> None:
        result = minimize(manifest_with_deps)
        # pluggy and iniconfig are deps of pytest -> transitive
        assert "pluggy" in result.transitive
        assert "iniconfig" in result.transitive
        # pytest should be top-level (not a dep of others in the manifest)
        assert "pytest" in result.top_level
        assert result.total == 4

    def test_install_command(self, manifest_with_deps: Path) -> None:
        result = minimize(manifest_with_deps)
        cmd = result.install_command
        assert "pip install" in cmd
        # Top-level packages should be in the command
        for name in result.top_level:
            assert name in cmd

    def test_empty_manifest(self, tmp_path: Path) -> None:
        path = tmp_path / "env_manifest.json"
        path.write_text(json.dumps({
            "envcore_version": "0.1.0",
            "python_version": "3.11.5",
            "platform": "test",
            "created_at": "2026-03-07T00:00:00+00:00",
            "packages": {},
        }))
        result = minimize(path)
        assert result.total == 0
        assert result.top_level == {}
        assert result.transitive == {}
