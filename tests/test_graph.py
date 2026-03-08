"""Tests for ``envcore.graph``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from envcore.graph import graph


@pytest.fixture()
def manifest_file(tmp_path: Path) -> Path:
    path = tmp_path / "env_manifest.json"
    path.write_text(json.dumps({
        "envcore_version": "0.1.0",
        "python_version": "3.11.5",
        "platform": "test",
        "created_at": "2026-03-07T00:00:00+00:00",
        "packages": {
            "pytest": "9.0.1",
            "pluggy": "1.6.0",
            "iniconfig": "2.3.0",
        },
    }))
    return path


class TestGraph:
    def test_tree_format(self, manifest_file: Path) -> None:
        out = graph(manifest_file, "tree")
        assert "pytest" in out
        assert "pluggy" in out
        # pytest depends on pluggy, should show tree connector
        assert "├" in out or "└" in out

    def test_mermaid_format(self, manifest_file: Path) -> None:
        out = graph(manifest_file, "mermaid")
        assert "graph TD" in out
        assert "pytest" in out
        assert "-->" in out  # dependency arrow

    def test_dot_format(self, manifest_file: Path) -> None:
        out = graph(manifest_file, "dot")
        assert "digraph" in out
        assert "pytest" in out
        assert "->" in out

    def test_unknown_format_raises(self, manifest_file: Path) -> None:
        with pytest.raises(ValueError, match="Unknown format"):
            graph(manifest_file, "invalid")

    def test_empty_manifest(self, tmp_path: Path) -> None:
        path = tmp_path / "env_manifest.json"
        path.write_text(json.dumps({
            "envcore_version": "0.1.0",
            "python_version": "3.11.5",
            "platform": "test",
            "created_at": "2026-03-07T00:00:00+00:00",
            "packages": {},
        }))
        out = graph(path, "tree")
        assert out == ""  # empty tree
