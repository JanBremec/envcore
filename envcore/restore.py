"""
Restore an environment from an ``env_manifest.json`` file.

Runs ``pip install package==version`` for each entry in the manifest,
with support for dry-run previews and per-package success/failure reporting.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from envcore.manifest import DEFAULT_MANIFEST_PATH, Manifest, load

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InstallResult:
    """Outcome of a single ``pip install`` invocation."""

    package: str
    version: str
    success: bool
    message: str = ""


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------


def restore(
    path: str | Path = DEFAULT_MANIFEST_PATH,
    *,
    dry_run: bool = False,
    quiet: bool = False,
) -> list[InstallResult]:
    """Install every package listed in the manifest at *path*.

    Parameters
    ----------
    path:
        Path to the ``env_manifest.json`` file.
    dry_run:
        If ``True``, print what would be installed without actually
        running ``pip install``.
    quiet:
        If ``True``, suppress ``pip`` output.

    Returns
    -------
    list[InstallResult]
        One entry per package with success/failure status.
    """
    manifest = load(path)
    return restore_from_manifest(manifest, dry_run=dry_run, quiet=quiet)


def restore_from_manifest(
    manifest: Manifest,
    *,
    dry_run: bool = False,
    quiet: bool = False,
) -> list[InstallResult]:
    """Install every package in *manifest*.

    Uses a single ``pip install`` command for speed (10–50× faster
    than sequential installs).  Falls back to per-package install
    if the batch command fails.

    See :func:`restore` for parameter descriptions.
    """
    results: list[InstallResult] = []
    specs = [f"{pkg}=={ver}" for pkg, ver in sorted(manifest.packages.items())]

    if not specs:
        return results

    if dry_run:
        for package, version in sorted(manifest.packages.items()):
            results.append(InstallResult(
                package=package, version=version, success=True,
                message=f"pip install {package}=={version}",
            ))
        return results

    # Batch install: single pip command
    cmd = [sys.executable, "-m", "pip", "install"] + specs
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if proc.returncode == 0:
            for package, version in sorted(manifest.packages.items()):
                results.append(InstallResult(
                    package=package, version=version, success=True,
                ))
            return results
    except (subprocess.TimeoutExpired, Exception):
        pass  # Fall through to sequential

    # Fallback: per-package install (if batch failed)
    for package, version in sorted(manifest.packages.items()):
        spec = f"{package}=={version}"
        cmd = [sys.executable, "-m", "pip", "install", spec]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if proc.returncode == 0:
                results.append(InstallResult(
                    package=package, version=version, success=True,
                ))
            else:
                results.append(InstallResult(
                    package=package, version=version, success=False,
                    message=proc.stderr.strip(),
                ))
        except subprocess.TimeoutExpired:
            results.append(InstallResult(
                package=package, version=version, success=False,
                message="Installation timed out (300s)",
            ))
        except Exception as exc:  # noqa: BLE001
            results.append(InstallResult(
                package=package, version=version, success=False,
                message=str(exc),
            ))

    return results

