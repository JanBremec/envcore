"""
Environment cleanup — remove installed packages not in the manifest.

The inverse of ``envcore restore``: instead of installing what's missing,
it removes what's not needed.
"""

from __future__ import annotations

import importlib.metadata
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from envcore.manifest import DEFAULT_MANIFEST_PATH, Manifest, load

# Packages that must NEVER be uninstalled.
_PROTECTED: frozenset[str] = frozenset({
    "pip", "setuptools", "wheel", "pkg-resources", "pkg_resources",
    "envcore", "distribute", "python", "wsgiref",
})


@dataclass(frozen=True)
class CleanResult:
    """Outcome of a single uninstall."""

    package: str
    version: str
    success: bool
    message: str = ""


def find_orphans(
    path: str | Path = DEFAULT_MANIFEST_PATH,
) -> list[tuple[str, str]]:
    """Return ``(name, version)`` pairs for packages installed but not in manifest."""
    manifest = load(path)
    manifest_names = {n.lower() for n in manifest.packages}

    # Build dynamic ignore set: protected + envcore's own runtime deps
    ignore: set[str] = set(_PROTECTED)
    try:
        envcore_dist = importlib.metadata.distribution("envcore")
        for req_str in (envcore_dist.requires or []):
            dep_name = req_str.split(";")[0].split(">")[0].split("<")[0].split("=")[0].split("!")[0].split("[")[0].strip()
            if dep_name:
                ignore.add(dep_name.lower())
    except importlib.metadata.PackageNotFoundError:
        pass

    orphans: list[tuple[str, str]] = []
    seen: set[str] = set()

    for dist in importlib.metadata.distributions():
        name = dist.metadata["Name"]
        lower = name.lower()
        if lower in seen or lower in manifest_names or lower in ignore:
            continue
        seen.add(lower)
        orphans.append((name, dist.version))

    return sorted(orphans, key=lambda x: x[0].lower())


def clean(
    path: str | Path = DEFAULT_MANIFEST_PATH,
    *,
    dry_run: bool = False,
) -> list[CleanResult]:
    """Uninstall packages not in the manifest.

    Parameters
    ----------
    path:
        Path to the manifest file.
    dry_run:
        If ``True``, just report what would be removed.

    Returns
    -------
    list[CleanResult]
        One entry per orphan package.
    """
    orphans = find_orphans(path)
    results: list[CleanResult] = []

    for name, version in orphans:
        if dry_run:
            results.append(CleanResult(
                package=name,
                version=version,
                success=True,
                message=f"pip uninstall {name}",
            ))
            continue

        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "uninstall", "-y", name],
                capture_output=True,
                text=True,
                timeout=60,
            )
            results.append(CleanResult(
                package=name,
                version=version,
                success=proc.returncode == 0,
                message=proc.stderr.strip() if proc.returncode != 0 else "",
            ))
        except Exception as exc:  # noqa: BLE001
            results.append(CleanResult(
                package=name,
                version=version,
                success=False,
                message=str(exc),
            ))

    return results
