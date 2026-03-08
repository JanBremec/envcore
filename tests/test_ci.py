"""Tests for ``envcore.ci``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from envcore.ci import check


@pytest.fixture()
def matching_manifest(tmp_path: Path) -> Path:
    """Manifest where click matches the installed version."""
    import importlib.metadata
    click_version = importlib.metadata.version("click")
    path = tmp_path / "env_manifest.json"
    path.write_text(json.dumps({
        "envcore_version": "0.1.0",
        "python_version": "3.11.5",
        "platform": "test",
        "created_at": "2026-03-07T00:00:00+00:00",
        "packages": {"click": click_version},
    }))
    return path


@pytest.fixture()
def mismatched_manifest(tmp_path: Path) -> Path:
    path = tmp_path / "env_manifest.json"
    path.write_text(json.dumps({
        "envcore_version": "0.1.0",
        "python_version": "3.11.5",
        "platform": "test",
        "created_at": "2026-03-07T00:00:00+00:00",
        "packages": {"click": "0.0.1", "nonexistent_xyz_123": "1.0.0"},
    }))
    return path


class TestCI:
    def test_happy_path(self, matching_manifest: Path) -> None:
        result = check(matching_manifest)
        assert result.ok is True
        assert result.missing == []
        assert result.mismatched == []

    def test_missing_and_mismatched(self, mismatched_manifest: Path) -> None:
        result = check(mismatched_manifest)
        assert result.ok is False
        assert "nonexistent_xyz_123" in result.missing
        assert any(m[0] == "click" for m in result.mismatched)

    def test_summary(self, mismatched_manifest: Path) -> None:
        result = check(mismatched_manifest)
        assert "missing" in result.summary
        assert "mismatched" in result.summary

    def test_empty_manifest(self, tmp_path: Path) -> None:
        path = tmp_path / "env_manifest.json"
        path.write_text(json.dumps({
            "envcore_version": "0.1.0",
            "python_version": "3.11.5",
            "platform": "test",
            "created_at": "2026-03-07T00:00:00+00:00",
            "packages": {},
        }))
        result = check(path)
        assert result.ok is True
