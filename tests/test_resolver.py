"""Tests for ``envcore.resolver``."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from envcore.resolver import _build_dist_cache, is_stdlib, resolve, resolve_many


class TestStdlib:
    """Tests for stdlib detection."""

    def test_stdlib_modules(self) -> None:
        for name in ("os", "sys", "json", "io", "re", "builtins"):
            assert is_stdlib(name), f"{name} should be stdlib"

    def test_non_stdlib(self) -> None:
        # These are either third-party or don't exist:
        for name in ("numpy", "pandas", "flask"):
            assert not is_stdlib(name), f"{name} should not be stdlib"

    def test_dotted_stdlib(self) -> None:
        assert is_stdlib("os.path")
        assert is_stdlib("json.decoder")


class TestResolve:
    """Tests for package resolution."""

    def test_stdlib_returns_none(self) -> None:
        assert resolve("os") is None
        assert resolve("sys") is None
        assert resolve("json") is None

    def test_resolve_click(self) -> None:
        """Click is a real dependency of envcore, so it must be installed."""
        result = resolve("click")
        assert result is not None
        assert result.import_name == "click"
        assert result.package_name.lower() == "click"
        assert result.version  # Version string should be non-empty

    def test_resolve_nonexistent(self) -> None:
        result = resolve("this_package_definitely_does_not_exist_xyz_123")
        assert result is None


class TestResolveMany:
    """Tests for batch resolution."""

    def test_filters_stdlib(self) -> None:
        results = resolve_many(["os", "sys", "json"])
        assert results == {}

    def test_mixed(self) -> None:
        results = resolve_many(["os", "click", "nonexistent_pkg_abc_999"])
        assert "click" in results
        assert "os" not in results
        assert "nonexistent_pkg_abc_999" not in results


class TestBuildDistCacheRecordFallback:
    """
    Unit tests for the RECORD-based fallback in ``_build_dist_cache``.

    These tests mock ``importlib.metadata.distributions()`` so they run
    without needing any specific third-party package to be installed.
    """

    def _make_dist(self, name: str, version: str, top_level_txt=None, files=None):
        """Return a mock distribution object."""
        dist = MagicMock()
        dist.metadata = {"Name": name}
        dist.version = version
        dist.read_text.return_value = top_level_txt
        dist.files = files
        return dist

    def _make_path(self, *parts: str):
        """Return a mock PackagePath with .parts, .suffix, [-1] etc."""
        from pathlib import PurePosixPath
        p = PurePosixPath(*parts)
        mock = MagicMock()
        mock.parts = p.parts
        mock.suffix = p.suffix
        return mock

    def test_top_level_txt_takes_priority(self):
        """When top_level.txt is present its contents are used and RECORD is skipped."""
        dist = self._make_dist(
            "SomePackage", "1.0",
            top_level_txt="somepackage\n",
            files=[self._make_path("other_name", "__init__.py")],
        )
        with patch("importlib.metadata.distributions", return_value=[dist]):
            from envcore import resolver
            resolver._DIST_CACHE = None  # reset cache
            cache = _build_dist_cache()

        assert "somepackage" in cache
        assert cache["somepackage"] == ("SomePackage", "1.0")
        # RECORD-derived name should NOT override top_level.txt
        assert "other_name" not in cache

    def test_record_package_init_discovered(self):
        """
        A package that ships ``pywt/__init__.py`` but no ``top_level.txt``
        should be indexed under ``pywt``.

        This is the exact scenario that caused PyWavelets to be missed.
        """
        dist = self._make_dist(
            "PyWavelets", "1.9.0",
            top_level_txt=None,
            files=[
                self._make_path("pywt", "__init__.py"),
                self._make_path("pywt", "_extensions", "__init__.py"),
                self._make_path("PyWavelets-1.9.0.dist-info", "RECORD"),
            ],
        )
        with patch("importlib.metadata.distributions", return_value=[dist]):
            from envcore import resolver
            resolver._DIST_CACHE = None
            cache = _build_dist_cache()

        assert "pywt" in cache, "pywt should be discovered via RECORD fallback"
        assert cache["pywt"] == ("PyWavelets", "1.9.0")

    def test_record_single_module_discovered(self):
        """A single-file module (``foo.py``) without top_level.txt is indexed."""
        dist = self._make_dist(
            "mypkg", "2.0",
            top_level_txt=None,
            files=[
                self._make_path("mypkg.py"),
                self._make_path("mypkg-2.0.dist-info", "RECORD"),
            ],
        )
        with patch("importlib.metadata.distributions", return_value=[dist]):
            from envcore import resolver
            resolver._DIST_CACHE = None
            cache = _build_dist_cache()

        assert "mypkg" in cache
        assert cache["mypkg"] == ("mypkg", "2.0")

    def test_dist_info_entries_are_skipped(self):
        """
        Entries inside ``.dist-info`` and ``.data`` directories must not be
        indexed as importable modules.
        """
        dist = self._make_dist(
            "SomePkg", "3.0",
            top_level_txt=None,
            files=[
                self._make_path("SomePkg-3.0.dist-info", "WHEEL"),
                self._make_path("SomePkg-3.0.dist-info", "RECORD"),
                self._make_path("SomePkg-3.0.data", "scripts", "somescript"),
                self._make_path("somepkg", "__init__.py"),
            ],
        )
        with patch("importlib.metadata.distributions", return_value=[dist]):
            from envcore import resolver
            resolver._DIST_CACHE = None
            cache = _build_dist_cache()

        assert "somepkg" in cache
        # dist-info / data names must not appear
        assert "SomePkg-3.0" not in cache
        for key in cache:
            assert not key.endswith(".dist-info")
            assert not key.endswith(".data")

    def test_private_modules_are_skipped(self):
        """Names starting with ``_`` (e.g. ``_vendor``) should not be indexed."""
        dist = self._make_dist(
            "SomePkg", "1.0",
            top_level_txt=None,
            files=[
                self._make_path("_internal", "__init__.py"),
                self._make_path("realpkg", "__init__.py"),
            ],
        )
        with patch("importlib.metadata.distributions", return_value=[dist]):
            from envcore import resolver
            resolver._DIST_CACHE = None
            cache = _build_dist_cache()

        assert "realpkg" in cache
        assert "_internal" not in cache

    def test_normalized_name_fallback_always_present(self):
        """The normalized package name is always added as a last-resort key."""
        dist = self._make_dist(
            "My-Package", "0.5",
            top_level_txt=None,
            files=[],  # empty — nothing to discover from RECORD either
        )
        with patch("importlib.metadata.distributions", return_value=[dist]):
            from envcore import resolver
            resolver._DIST_CACHE = None
            cache = _build_dist_cache()

        assert "my_package" in cache
        assert cache["my_package"] == ("My-Package", "0.5")


class TestKnownAliases:
    """Verify that well-known import-name → PyPI-name aliases resolve correctly
    when the alias key is present in ``_KNOWN_ALIASES``."""

    def test_pywt_in_aliases(self):
        from envcore.resolver import _KNOWN_ALIASES
        assert "pywt" in _KNOWN_ALIASES, (
            "pywt must be in _KNOWN_ALIASES so PyWavelets is resolved "
            "even if RECORD-based discovery somehow fails"
        )
        assert _KNOWN_ALIASES["pywt"] == "PyWavelets"

    def test_all_original_aliases_present(self):
        """Ensure we didn't accidentally drop any of the original aliases."""
        from envcore.resolver import _KNOWN_ALIASES
        expected = {
            "cv2": "opencv-python",
            "PIL": "Pillow",
            "sklearn": "scikit-learn",
            "skimage": "scikit-image",
            "yaml": "PyYAML",
            "bs4": "beautifulsoup4",
            "attr": "attrs",
            "gi": "PyGObject",
            "wx": "wxPython",
            "Crypto": "pycryptodome",
            "serial": "pyserial",
            "usb": "pyusb",
            "git": "GitPython",
            "dotenv": "python-dotenv",
            "jose": "python-jose",
            "magic": "python-magic",
            "dateutil": "python-dateutil",
            "docx": "python-docx",
            "pptx": "python-pptx",
            "lxml": "lxml",
            "google.cloud": "google-cloud-core",
        }
        for key, value in expected.items():
            assert key in _KNOWN_ALIASES, f"alias '{key}' was removed"
            assert _KNOWN_ALIASES[key] == value, (
                f"alias '{key}' changed: expected {value!r}, got {_KNOWN_ALIASES[key]!r}"
            )
