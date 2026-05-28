"""
Integration test: PyWavelets missing from exported environment (issue reproduction).

Reproduces the exact bug report:
  - PyWavelets is installed
  - envcore traces `import pywt`
  - PyWavelets must appear in env_manifest.json and requirements.txt

This test covers the full pipeline:
  tracer → resolver → manifest → export
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from envcore.export import export
from envcore.manifest import Manifest, save, load
from envcore.resolver import resolve, resolve_many, _KNOWN_ALIASES
from envcore import resolver as resolver_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pywavelets_dist():
    """
    Mock a PyWavelets distribution that ships pywt/__init__.py
    but NO top_level.txt — exactly what the real package does.
    """
    from pathlib import PurePosixPath

    def make_path(*parts):
        p = PurePosixPath(*parts)
        m = MagicMock()
        m.parts = p.parts
        m.suffix = p.suffix
        return m

    dist = MagicMock()
    dist.metadata = {"Name": "PyWavelets"}
    dist.version = "1.9.0"
    dist.read_text.return_value = None          # no top_level.txt
    dist.files = [
        make_path("pywt", "__init__.py"),
        make_path("pywt", "_cwt.py"),
        make_path("pywt", "_extensions", "__init__.py"),
        make_path("PyWavelets-1.9.0.dist-info", "METADATA"),
        make_path("PyWavelets-1.9.0.dist-info", "RECORD"),
    ]
    return dist


# ---------------------------------------------------------------------------
# Stage 1: resolver correctly maps pywt → PyWavelets
# ---------------------------------------------------------------------------

class TestResolverStage:
    """resolver.resolve('pywt') must return PyWavelets."""

    def test_pywt_in_known_aliases(self):
        """Belt-and-suspenders: alias must be present regardless of RECORD."""
        assert "pywt" in _KNOWN_ALIASES
        assert _KNOWN_ALIASES["pywt"] == "PyWavelets"

    def test_resolve_pywt_via_alias(self):
        """resolve('pywt') uses the alias path when PyWavelets is installed."""
        mock_dist = MagicMock()
        mock_dist.metadata = {"Name": "PyWavelets"}
        mock_dist.version = "1.9.0"

        with patch("importlib.metadata.distribution", return_value=mock_dist):
            result = resolve("pywt")

        assert result is not None, "resolve('pywt') returned None — PyWavelets would be missing from manifest"
        assert result.package_name == "PyWavelets"
        assert result.version == "1.9.0"
        assert result.import_name == "pywt"

    def test_resolve_pywt_via_record_fallback(self):
        """
        resolve('pywt') must also work via RECORD when the alias lookup
        somehow fails (belt-and-suspenders for the RECORD fix).
        """
        pywavelets_dist = _make_pywavelets_dist()

        # Alias lookup raises PackageNotFoundError, forcing RECORD path
        import importlib.metadata as ilm
        def fake_distribution(name):
            raise ilm.PackageNotFoundError(name)

        resolver_module._DIST_CACHE = None  # reset cache

        with patch("importlib.metadata.distributions", return_value=[pywavelets_dist]):
            with patch("importlib.metadata.distribution", side_effect=fake_distribution):
                result = resolve("pywt")

        assert result is not None, "RECORD fallback failed — pywt not discovered from pywt/__init__.py"
        assert result.package_name == "PyWavelets"
        assert result.version == "1.9.0"

    def test_resolve_many_includes_pywt(self):
        """resolve_many(['pywt', 'os']) must include pywt and exclude os."""
        mock_dist = MagicMock()
        mock_dist.metadata = {"Name": "PyWavelets"}
        mock_dist.version = "1.9.0"

        with patch("importlib.metadata.distribution", return_value=mock_dist):
            results = resolve_many(["pywt", "os", "sys"])

        assert "pywt" in results
        assert "os" not in results
        assert "sys" not in results


# ---------------------------------------------------------------------------
# Stage 2: manifest contains PyWavelets
# ---------------------------------------------------------------------------

class TestManifestStage:
    """PyWavelets must appear in the Manifest packages dict."""

    def test_pywavelets_in_manifest_packages(self):
        manifest = Manifest(packages={"PyWavelets": "1.9.0", "numpy": "2.2.6"})
        assert "PyWavelets" in manifest.packages
        assert manifest.packages["PyWavelets"] == "1.9.0"

    def test_manifest_save_load_preserves_pywavelets(self, tmp_path):
        """Round-trip save/load must not drop PyWavelets."""
        manifest = Manifest(packages={"PyWavelets": "1.9.0", "numpy": "2.2.6"})
        path = tmp_path / "env_manifest.json"
        save(manifest, path)

        loaded = load(path)
        assert "PyWavelets" in loaded.packages, (
            "PyWavelets missing from env_manifest.json after save/load"
        )
        assert loaded.packages["PyWavelets"] == "1.9.0"

    def test_manifest_json_structure(self, tmp_path):
        """env_manifest.json must have PyWavelets under 'packages'."""
        manifest = Manifest(packages={"PyWavelets": "1.9.0", "numpy": "2.2.6"})
        path = tmp_path / "env_manifest.json"
        save(manifest, path)

        raw = json.loads(path.read_text())
        assert "packages" in raw
        assert "PyWavelets" in raw["packages"], (
            f"PyWavelets not found in packages. Got: {list(raw['packages'].keys())}"
        )


# ---------------------------------------------------------------------------
# Stage 3: export contains PyWavelets
# ---------------------------------------------------------------------------

class TestExportStage:
    """PyWavelets must appear in every export format."""

    @pytest.fixture()
    def manifest(self):
        return Manifest(
            packages={"PyWavelets": "1.9.0", "numpy": "2.2.6", "matplotlib": "3.10.3"},
            envcore_version="0.1.0",
            python_version="3.11.13",
            platform="Windows-10-10.0.19043-SP0",
            created_at="2026-04-27T05:22:54.558642+00:00",
        )

    def test_requirements_txt_contains_pywavelets(self, manifest):
        out = export(manifest, "requirements")
        assert "PyWavelets==1.9.0" in out, (
            f"PyWavelets==1.9.0 missing from requirements.txt output:\n{out}"
        )

    def test_requirements_txt_regression(self, manifest):
        """Exact regression against the bug report output."""
        out = export(manifest, "requirements")
        # These were present in the bug report
        assert "numpy==2.2.6" in out
        assert "matplotlib==3.10.3" in out
        # This was missing — must now be present
        assert "PyWavelets==1.9.0" in out

    def test_pyproject_contains_pywavelets(self, manifest):
        out = export(manifest, "pyproject")
        assert "PyWavelets==1.9.0" in out

    def test_conda_contains_pywavelets(self, manifest):
        out = export(manifest, "conda")
        assert "PyWavelets==1.9.0" in out

    def test_docker_contains_pywavelets(self, manifest):
        out = export(manifest, "docker")
        assert "PyWavelets==1.9.0" in out


# ---------------------------------------------------------------------------
# Stage 4: full end-to-end pipeline
# ---------------------------------------------------------------------------

class TestEndToEndPipeline:
    """
    Simulates the complete flow described in the bug report:
      install PyWavelets → trace `import pywt` → resolve → save manifest
      → export requirements.txt → PyWavelets present.
    """

    def test_full_pipeline_pywavelets(self, tmp_path):
        """
        End-to-end: tracing `pywt` produces a requirements.txt that contains
        PyWavelets==1.9.0.
        """
        mock_dist = MagicMock()
        mock_dist.metadata = {"Name": "PyWavelets"}
        mock_dist.version = "1.9.0"

        # Step 1: simulate resolving traced import names (as envcore does
        # after tracing a script that runs `import pywt`)
        with patch("importlib.metadata.distribution", return_value=mock_dist):
            resolved = resolve_many(["pywt", "numpy"])

        # resolve_many returns import_name → ResolvedPackage;
        # manifest stores package_name → version
        packages = {r.package_name: r.version for r in resolved.values()}

        # Step 2: build manifest
        manifest = Manifest(packages=packages)

        # Step 3: save env_manifest.json
        manifest_path = tmp_path / "env_manifest.json"
        save(manifest, manifest_path)

        # Step 4: load and verify
        loaded = load(manifest_path)
        assert "PyWavelets" in loaded.packages, (
            "BUG REPRODUCED: PyWavelets missing from env_manifest.json"
        )

        # Step 5: export to requirements.txt
        req_txt = export(loaded, "requirements")
        assert "PyWavelets==1.9.0" in req_txt, (
            "BUG REPRODUCED: PyWavelets missing from requirements.txt"
        )
