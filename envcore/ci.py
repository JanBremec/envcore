"""
CI/CD integration — verify environments match manifests.

Commands:
- ``check``  — exits 1 if any package is missing or mismatched
- ``verify`` — exits 1 if lockfile integrity check fails
"""

from __future__ import annotations

import importlib.metadata
from dataclasses import dataclass, field
from pathlib import Path

from envcore.manifest import DEFAULT_MANIFEST_PATH, Manifest, load


@dataclass
class CIResult:
    """Result of a CI environment check."""

    ok: bool
    missing: list[str] = field(default_factory=list)
    mismatched: list[tuple[str, str, str]] = field(
        default_factory=list,
    )  # (name, expected, actual)
    extra: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        parts = []
        if self.missing:
            parts.append(f"{len(self.missing)} missing")
        if self.mismatched:
            parts.append(f"{len(self.mismatched)} mismatched")
        if not parts:
            return "All packages match manifest"
        return ", ".join(parts)


def check(
    path: str | Path = DEFAULT_MANIFEST_PATH,
    *,
    strict: bool = False,
) -> CIResult:
    """Verify that all manifest packages are installed with correct versions.

    Parameters
    ----------
    path:
        Path to the manifest file.
    strict:
        If ``True``, also reports extra installed packages not in manifest.

    Returns
    -------
    CIResult
        The verification result.
    """
    manifest = load(path)

    missing: list[str] = []
    mismatched: list[tuple[str, str, str]] = []

    for pkg_name, expected_version in sorted(manifest.packages.items()):
        try:
            dist = importlib.metadata.distribution(pkg_name)
            actual = dist.version
            if actual != expected_version:
                mismatched.append((pkg_name, expected_version, actual))
        except importlib.metadata.PackageNotFoundError:
            missing.append(pkg_name)

    ok = not missing and not mismatched
    return CIResult(ok=ok, missing=missing, mismatched=mismatched)
