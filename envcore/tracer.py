"""
Runtime import tracer for Python.

Hooks into ``builtins.__import__`` to record every module imported while
tracing is active.  Designed to be **thread-safe**, reentrant, and usable
as a context manager, decorator, or via explicit start/stop calls.
"""

from __future__ import annotations

import builtins
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar, cast

F = TypeVar("F", bound=Callable[..., Any])

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ImportRecord:
    """A single recorded import event."""

    module_name: str
    """Top-level module name (e.g. ``numpy``, not ``numpy.linalg``)."""

    timestamp: float
    """``time.monotonic()`` value when the import occurred."""

    order: int
    """Sequence number (0-based) relative to tracing start."""


# ---------------------------------------------------------------------------
# Tracer
# ---------------------------------------------------------------------------

class ImportTracer:
    """Record every *new* import that occurs while the tracer is active.

    Usage — context manager::

        tracer = ImportTracer()
        with tracer:
            import numpy
            import pandas
        print(tracer.imports)   # {ImportRecord(...), ...}

    Usage — explicit::

        tracer = ImportTracer()
        tracer.start()
        import numpy
        tracer.stop()

    Usage — decorator::

        tracer = ImportTracer()

        @tracer
        def train():
            import torch
            ...

    The tracer records only **top-level** module names (``numpy``, not
    ``numpy.linalg``) and automatically ignores the standard library.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active = False
        self._original_import: Callable[..., Any] | None = None
        self._imports: dict[str, ImportRecord] = {}
        self._counter = 0
        self._pre_existing: frozenset[str] = frozenset()

    # -- Properties ---------------------------------------------------------

    @property
    def is_active(self) -> bool:
        """Whether the tracer is currently recording imports."""
        return self._active

    @property
    def imports(self) -> dict[str, ImportRecord]:
        """Mapping of top-level module name → :class:`ImportRecord`."""
        return dict(self._imports)

    @property
    def module_names(self) -> list[str]:
        """Sorted list of traced module names."""
        return sorted(self._imports)

    # -- Start / Stop -------------------------------------------------------

    def start(self) -> None:
        """Begin tracing imports.

        Raises :class:`RuntimeError` if the tracer is already active or
        if another tracer is currently hooked into ``builtins.__import__``.
        """
        with self._lock:
            if self._active:
                raise RuntimeError("ImportTracer is already active")

            # Prevent nesting: detect if another ImportTracer has hooked
            # __import__.  Without this guard, stop() would restore the
            # wrong function and silently break the outer tracer.
            current = builtins.__import__
            if (
                hasattr(current, "__self__")
                and isinstance(current.__self__, ImportTracer)
            ):
                raise RuntimeError(
                    "Another ImportTracer is already active. "
                    "Nested tracers are not supported — the inner tracer's "
                    "stop() would corrupt the outer tracer's hook."
                )

            self._pre_existing = frozenset(sys.modules)
            self._original_import = builtins.__import__
            builtins.__import__ = self._traced_import  # type: ignore[assignment]
            self._active = True

    def stop(self) -> None:
        """Stop tracing and restore the original import machinery.

        Raises :class:`RuntimeError` if the tracer is not active.
        """
        with self._lock:
            if not self._active:
                raise RuntimeError("ImportTracer is not active")
            builtins.__import__ = self._original_import  # type: ignore[assignment]
            self._original_import = None
            self._active = False

    def reset(self) -> None:
        """Clear all recorded imports and reset the counter."""
        with self._lock:
            self._imports.clear()
            self._counter = 0

    # -- Context manager ----------------------------------------------------

    def __enter__(self) -> "ImportTracer":
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()

    # -- Decorator ----------------------------------------------------------

    def __call__(self, func: F) -> F:
        """Use the tracer as a decorator around a function."""
        import functools

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with self:
                return func(*args, **kwargs)

        return cast(F, wrapper)

    # -- Internal -----------------------------------------------------------

    def _traced_import(
        self,
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        """Drop-in replacement for ``builtins.__import__``."""
        assert self._original_import is not None

        # Perform the real import first so the module is available.
        module = self._original_import(name, globals, locals, fromlist, level)

        # Only record top-level, absolute imports.
        if level != 0:
            return module

        top_level = name.split(".")[0]

        # Skip if already tracked or was pre-existing before tracing.
        if top_level in self._imports or top_level in self._pre_existing:
            return module

        with self._lock:
            # Double-check under lock.
            if top_level not in self._imports:
                self._imports[top_level] = ImportRecord(
                    module_name=top_level,
                    timestamp=time.monotonic(),
                    order=self._counter,
                )
                self._counter += 1

        return module


# ---------------------------------------------------------------------------
# Module-level singleton for convenience
# ---------------------------------------------------------------------------

_default_tracer = ImportTracer()


def start_tracking() -> None:
    """Start the default global tracer."""
    _default_tracer.start()


def stop_tracking() -> None:
    """Stop the default global tracer."""
    _default_tracer.stop()


def get_imports() -> dict[str, ImportRecord]:
    """Return imports recorded by the default tracer."""
    return _default_tracer.imports


def reset() -> None:
    """Reset the default tracer."""
    _default_tracer.reset()


def get_default_tracer() -> ImportTracer:
    """Return the module-level default :class:`ImportTracer` instance."""
    return _default_tracer
