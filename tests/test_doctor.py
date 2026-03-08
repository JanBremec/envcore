"""Tests for ``envcore.doctor``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from envcore.doctor import Severity, diagnose


@pytest.fixture()
def manifest_file(tmp_path: Path) -> Path:
    """Create a manifest with click (which is installed)."""
    path = tmp_path / "env_manifest.json"
    path.write_text(json.dumps({
        "envcore_version": "0.1.0",
        "python_version": "3.11.5",
        "platform": "test",
        "created_at": "2026-03-07T00:00:00+00:00",
        "packages": {"click": "8.1.7"},
    }))
    return path


@pytest.fixture()
def missing_manifest(tmp_path: Path) -> Path:
    """Create a manifest with a package that doesn't exist."""
    path = tmp_path / "env_manifest.json"
    path.write_text(json.dumps({
        "envcore_version": "0.1.0",
        "python_version": "3.11.5",
        "platform": "test",
        "created_at": "2026-03-07T00:00:00+00:00",
        "packages": {"nonexistent_pkg_xyz_999": "1.0.0"},
    }))
    return path


class TestDoctor:
    def test_diagnose_returns_report(self, manifest_file: Path) -> None:
        report = diagnose(manifest_file, check_outdated=False)
        assert report.python_version == "3.11.5"
        assert report.manifest_packages == 1

    def test_missing_package_critical(self, missing_manifest: Path) -> None:
        report = diagnose(missing_manifest, check_outdated=False)
        critical = [i for i in report.items if i.severity == Severity.CRITICAL]
        assert len(critical) >= 1
        assert any("nonexistent_pkg_xyz_999" in i.package for i in critical)
        assert not report.is_healthy

    def test_orphan_detection(self, manifest_file: Path) -> None:
        """Packages installed but not in manifest should be detected."""
        report = diagnose(manifest_file, check_outdated=False)
        orphan_items = [i for i in report.items if i.category == "orphan"]
        # There should be at least some orphans (pytest, coverage, etc.)
        assert len(orphan_items) > 0
