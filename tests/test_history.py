"""Tests for ``envcore.history``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from envcore.history import list_history, save_snapshot


@pytest.fixture()
def manifest_file(tmp_path: Path) -> Path:
    path = tmp_path / "env_manifest.json"
    path.write_text(json.dumps({
        "envcore_version": "0.1.0",
        "python_version": "3.11.5",
        "platform": "test",
        "created_at": "2026-03-07T12:00:00+00:00",
        "packages": {"click": "8.1.7"},
    }))
    return path


class TestHistory:
    def test_save_creates_snapshot(self, manifest_file: Path, tmp_path: Path) -> None:
        dest = save_snapshot(manifest_file, project_dir=tmp_path)
        assert dest.exists()
        assert "manifest_" in dest.name
        data = json.loads(dest.read_text())
        assert "click" in data["packages"]

    def test_list_returns_entries(self, manifest_file: Path, tmp_path: Path) -> None:
        save_snapshot(manifest_file, project_dir=tmp_path)
        entries = list_history(project_dir=tmp_path)
        assert len(entries) == 1
        assert entries[0].package_count == 1

    def test_list_empty(self, tmp_path: Path) -> None:
        entries = list_history(project_dir=tmp_path)
        assert entries == []

    def test_multiple_snapshots(self, manifest_file: Path, tmp_path: Path) -> None:
        import time
        save_snapshot(manifest_file, project_dir=tmp_path)
        time.sleep(1.1)  # ensure different timestamp
        save_snapshot(manifest_file, project_dir=tmp_path)
        entries = list_history(project_dir=tmp_path)
        assert len(entries) == 2

    def test_save_missing_manifest_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            save_snapshot(tmp_path / "nope.json", project_dir=tmp_path)
