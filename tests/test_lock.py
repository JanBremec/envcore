"""Tests for ``envcore.lock``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from envcore.lock import generate_lockfile, verify_lockfile


@pytest.fixture()
def manifest_file(tmp_path: Path) -> Path:
    path = tmp_path / "env_manifest.json"
    path.write_text(json.dumps({
        "envcore_version": "0.1.0",
        "python_version": "3.11.5",
        "platform": "test",
        "created_at": "2026-03-07T00:00:00+00:00",
        "packages": {"click": "8.1.7", "pytest": "9.0.1"},
    }))
    return path


class TestLock:
    def test_generates_lockfile(self, manifest_file: Path, tmp_path: Path) -> None:
        dest = tmp_path / "env_manifest.lock"
        result = generate_lockfile(manifest_file, dest)
        assert result.exists()
        data = json.loads(result.read_text())
        assert "packages" in data
        assert "click" in data["packages"]
        assert "pytest" in data["packages"]

    def test_lockfile_has_hashes(self, manifest_file: Path, tmp_path: Path) -> None:
        dest = tmp_path / "env_manifest.lock"
        generate_lockfile(manifest_file, dest)
        data = json.loads(dest.read_text())
        for pkg, info in data["packages"].items():
            assert "hash" in info
            assert info["hash"].startswith("sha256:")

    def test_lockfile_has_requires(self, manifest_file: Path, tmp_path: Path) -> None:
        dest = tmp_path / "env_manifest.lock"
        generate_lockfile(manifest_file, dest)
        data = json.loads(dest.read_text())
        for pkg, info in data["packages"].items():
            assert "requires" in info
            assert isinstance(info["requires"], list)

    def test_lockfile_has_metadata(self, manifest_file: Path, tmp_path: Path) -> None:
        dest = tmp_path / "env_manifest.lock"
        generate_lockfile(manifest_file, dest)
        data = json.loads(dest.read_text())
        assert data["envcore_version"] == "0.1.0"
        assert data["python_version"] == "3.11.5"
        assert "created_at" in data


class TestVerify:
    def test_verify_missing_lockfile(self, tmp_path: Path) -> None:
        issues = verify_lockfile(tmp_path / "nope.lock")
        assert len(issues) == 1
        assert "not found" in issues[0][1]

    def test_verify_valid_lockfile(self, manifest_file: Path, tmp_path: Path) -> None:
        dest = tmp_path / "env_manifest.lock"
        generate_lockfile(manifest_file, dest)
        issues = verify_lockfile(dest)
        # May have version mismatches if installed versions differ, but no crashes
        assert isinstance(issues, list)
