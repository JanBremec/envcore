"""Tests for ``envcore.manifest``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from envcore.manifest import Manifest, ManifestDiff, diff, load, save


@pytest.fixture()
def tmp_manifest(tmp_path: Path) -> Path:
    return tmp_path / "test_manifest.json"


class TestManifest:
    """Tests for manifest data model."""

    def test_default_metadata(self) -> None:
        m = Manifest(packages={"numpy": "1.26.4"})
        assert m.envcore_version
        assert m.python_version
        assert m.platform
        assert m.created_at

    def test_custom_metadata(self) -> None:
        m = Manifest(
            packages={"numpy": "1.26.4"},
            envcore_version="0.0.1",
            python_version="3.11.0",
            platform="test",
            created_at="2026-01-01T00:00:00Z",
        )
        assert m.envcore_version == "0.0.1"
        assert m.python_version == "3.11.0"


class TestSaveLoad:
    """Tests for manifest file I/O."""

    def test_roundtrip(self, tmp_manifest: Path) -> None:
        original = Manifest(packages={"numpy": "1.26.4", "torch": "2.1.0"})
        save(original, tmp_manifest)

        loaded = load(tmp_manifest)
        assert loaded.packages == original.packages
        assert loaded.envcore_version == original.envcore_version
        assert loaded.python_version == original.python_version

    def test_json_format(self, tmp_manifest: Path) -> None:
        m = Manifest(packages={"b_pkg": "2.0", "a_pkg": "1.0"})
        save(m, tmp_manifest)

        data = json.loads(tmp_manifest.read_text())
        # Packages should be sorted alphabetically
        keys = list(data["packages"].keys())
        assert keys == sorted(keys)

    def test_load_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load(tmp_path / "nonexistent.json")

    def test_empty_packages(self, tmp_manifest: Path) -> None:
        m = Manifest(packages={})
        save(m, tmp_manifest)
        loaded = load(tmp_manifest)
        assert loaded.packages == {}


class TestDiff:
    """Tests for manifest diffing."""

    def test_identical(self) -> None:
        a = Manifest(packages={"numpy": "1.26.4"})
        b = Manifest(packages={"numpy": "1.26.4"})
        d = diff(a, b)
        assert d.is_empty

    def test_added(self) -> None:
        a = Manifest(packages={"numpy": "1.26.4"})
        b = Manifest(packages={"numpy": "1.26.4", "torch": "2.1.0"})
        d = diff(a, b)
        assert d.added == {"torch": "2.1.0"}
        assert d.removed == {}
        assert d.changed == {}
        assert not d.is_empty

    def test_removed(self) -> None:
        a = Manifest(packages={"numpy": "1.26.4", "torch": "2.1.0"})
        b = Manifest(packages={"numpy": "1.26.4"})
        d = diff(a, b)
        assert d.added == {}
        assert d.removed == {"torch": "2.1.0"}

    def test_changed(self) -> None:
        a = Manifest(packages={"numpy": "1.25.0"})
        b = Manifest(packages={"numpy": "1.26.4"})
        d = diff(a, b)
        assert d.changed == {"numpy": ("1.25.0", "1.26.4")}

    def test_complex_diff(self) -> None:
        a = Manifest(packages={"numpy": "1.25.0", "pandas": "2.0.0", "flask": "3.0.0"})
        b = Manifest(packages={"numpy": "1.26.4", "pandas": "2.0.0", "torch": "2.1.0"})
        d = diff(a, b)
        assert d.added == {"torch": "2.1.0"}
        assert d.removed == {"flask": "3.0.0"}
        assert d.changed == {"numpy": ("1.25.0", "1.26.4")}
