"""
Live development monitor — continuous import tracing.

Runs a Python script with the tracer active and watches for new imports,
updating the manifest in real-time.
"""

from __future__ import annotations

import runpy
import sys
import threading
import time
from pathlib import Path
from typing import Callable

from envcore.manifest import Manifest, save
from envcore.resolver import resolve_many
from envcore.tracer import ImportTracer


def watch(
    script: str,
    output: str = "env_manifest.json",
    *,
    interval: float = 2.0,
    on_update: Callable[[str, str], None] | None = None,
) -> dict[str, str]:
    """Run *script* with continuous import tracing.

    Every *interval* seconds, the manifest is updated with any newly
    detected imports.  If *on_update* is provided, it is called with
    ``(package_name, version)`` for each new detection.

    Parameters
    ----------
    script:
        Path to the Python script to run.
    output:
        Path for the manifest file.
    interval:
        Seconds between manifest refresh checks.
    on_update:
        Optional callback ``(name, version) -> None`` on new detection.

    Returns
    -------
    dict[str, str]
        Final mapping of package_name → version.
    """
    tracer = ImportTracer()
    packages: dict[str, str] = {}
    stop_event = threading.Event()

    def _monitor() -> None:
        """Background thread that periodically resolves and saves."""
        while not stop_event.is_set():
            stop_event.wait(interval)
            if stop_event.is_set():
                break

            current = tracer.imports
            resolved = resolve_many(list(current.keys()))
            new_pkgs = {
                r.package_name: r.version
                for r in resolved.values()
                if r.package_name not in packages
            }

            if new_pkgs:
                packages.update(new_pkgs)
                manifest = Manifest(packages=dict(packages))
                save(manifest, output)

                if on_update:
                    for name, version in new_pkgs.items():
                        on_update(name, version)

    monitor_thread = threading.Thread(target=_monitor, daemon=True)
    monitor_thread.start()

    tracer.start()
    try:
        sys.argv = [script]
        runpy.run_path(script, run_name="__main__")
    except SystemExit:
        pass
    finally:
        tracer.stop()
        stop_event.set()
        monitor_thread.join(timeout=5)

    # Final resolve after script completes
    resolved = resolve_many(list(tracer.imports.keys()))
    packages.update({r.package_name: r.version for r in resolved.values()})

    if packages:
        manifest = Manifest(packages=packages)
        save(manifest, output)

    return packages
