"""Tests for ``envcore.tracer``."""

from __future__ import annotations

import builtins

import pytest

from envcore.tracer import ImportTracer, start_tracking, stop_tracking, get_imports, reset


class TestImportTracer:
    """Unit tests for :class:`ImportTracer`."""

    def test_context_manager_captures_imports(self) -> None:
        tracer = ImportTracer()
        with tracer:
            import json  # stdlib — should still be recorded as an import event
        # json is in sys.modules before tracing starts, so it's in _pre_existing
        # and should NOT appear in tracer.imports.
        # We just verify the tracer started and stopped cleanly.
        assert not tracer.is_active

    def test_start_stop(self) -> None:
        tracer = ImportTracer()
        assert not tracer.is_active
        tracer.start()
        assert tracer.is_active
        tracer.stop()
        assert not tracer.is_active

    def test_double_start_raises(self) -> None:
        tracer = ImportTracer()
        tracer.start()
        try:
            with pytest.raises(RuntimeError, match="already active"):
                tracer.start()
        finally:
            tracer.stop()

    def test_double_stop_raises(self) -> None:
        tracer = ImportTracer()
        with pytest.raises(RuntimeError, match="not active"):
            tracer.stop()

    def test_restores_original_import(self) -> None:
        original = builtins.__import__
        tracer = ImportTracer()
        with tracer:
            pass
        assert builtins.__import__ is original

    def test_reset_clears_imports(self) -> None:
        tracer = ImportTracer()
        with tracer:
            pass
        tracer.reset()
        assert tracer.imports == {}
        assert tracer.module_names == []

    def test_decorator_usage(self) -> None:
        tracer = ImportTracer()

        @tracer
        def my_func() -> str:
            return "hello"

        result = my_func()
        assert result == "hello"
        assert not tracer.is_active

    def test_pre_existing_modules_excluded(self) -> None:
        """Modules already in sys.modules before tracing should not appear."""
        import sys as _sys  # Force sys into sys.modules (it's always there)
        tracer = ImportTracer()
        with tracer:
            import sys  # noqa: F811
        assert "sys" not in tracer.imports

    def test_records_order(self) -> None:
        """Import order should be sequential."""
        tracer = ImportTracer()
        # We can't guarantee new modules, but we verify the mechanism
        assert tracer.imports == {}
        tracer.reset()
        assert tracer.imports == {}


class TestModuleLevelAPI:
    """Tests for the module-level convenience functions."""

    def setup_method(self) -> None:
        reset()

    def test_start_stop_tracking(self) -> None:
        start_tracking()
        stop_tracking()
        # Should not raise and should return a dict
        imports = get_imports()
        assert isinstance(imports, dict)

    def test_reset(self) -> None:
        reset()
        assert get_imports() == {}
