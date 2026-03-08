"""Tests for ``envcore.resolver``."""

from __future__ import annotations

from envcore.resolver import is_stdlib, resolve, resolve_many


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
        # Click's package name is "click"
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
        # os is stdlib -> filtered, nonexistent -> filtered, click -> present
        assert "click" in results
        assert "os" not in results
        assert "nonexistent_pkg_abc_999" not in results
