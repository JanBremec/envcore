"""
envcore — Automatic Python environment reconstruction.

Runtime import tracing, deterministic snapshots, and one-command restore.
"""

from __future__ import annotations

__version__ = "0.1.0"

# Public API — re-exported for convenience
from envcore.manifest import Manifest, load as load_manifest, save as save_manifest
from envcore.resolver import resolve, resolve_many
from envcore.tracer import (
    ImportTracer,
    get_default_tracer,
    get_imports,
    reset,
    start_tracking,
    stop_tracking,
)

__all__ = [
    # Version
    "__version__",
    # Tracer
    "ImportTracer",
    "start_tracking",
    "stop_tracking",
    "get_imports",
    "get_default_tracer",
    "reset",
    # Resolver
    "resolve",
    "resolve_many",
    # Manifest
    "Manifest",
    "save_manifest",
    "load_manifest",
]


def snapshot(path: str = "env_manifest.json") -> None:
    """Convenience: resolve traced imports and save a manifest.

    This is the one-liner for programmatic use::

        import envcore
        envcore.start_tracking()
        import numpy, pandas
        envcore.stop_tracking()
        envcore.snapshot()
    """
    from envcore.manifest import Manifest, save
    from envcore.resolver import resolve_many
    from envcore.tracer import get_imports

    imports = get_imports()
    resolved = resolve_many(list(imports.keys()))

    packages = {r.package_name: r.version for r in resolved.values()}
    manifest = Manifest(packages=packages)
    save(manifest, path)
