"""
Minimize dependencies — find the smallest top-level install set.

Given a traced manifest with both direct and transitive dependencies,
determines which packages are top-level (explicitly imported) vs
transitive (installed automatically as dependencies of top-level packages).

This answers: "What's the minimal ``pip install`` command to reproduce
this environment?"
"""

from __future__ import annotations

import importlib.metadata
from dataclasses import dataclass, field
from pathlib import Path

from envcore.manifest import DEFAULT_MANIFEST_PATH, Manifest, load


@dataclass
class MinimizeResult:
    """Result of dependency minimisation."""

    top_level: dict[str, str]
    """Packages that should be explicitly installed."""

    transitive: dict[str, str]
    """Packages that will be automatically installed as dependencies."""

    @property
    def total(self) -> int:
        return len(self.top_level) + len(self.transitive)

    @property
    def install_command(self) -> str:
        """Generate the minimal pip install command."""
        specs = " ".join(
            f"{name}=={version}"
            for name, version in sorted(self.top_level.items())
        )
        return f"pip install {specs}"


def _get_requires(package_name: str) -> set[str]:
    """Get the set of packages that *package_name* depends on."""
    try:
        dist = importlib.metadata.distribution(package_name)
    except importlib.metadata.PackageNotFoundError:
        return set()

    requires = dist.requires
    if not requires:
        return set()

    deps: set[str] = set()
    for req_str in requires:
        # Requirement strings look like: "numpy>=1.20", "foo ; extra == 'test'"
        # We want only non-extra dependencies.
        if "extra ==" in req_str or "extra==" in req_str:
            continue
        # Extract the package name (before any version specifier)
        name = req_str.split(";")[0].strip()
        for sep in (">=", "<=", "==", "!=", "~=", ">", "<", "["):
            name = name.split(sep)[0].strip()
        if name:
            deps.add(name.lower())

    return deps


def minimize(
    path: str | Path = DEFAULT_MANIFEST_PATH,
) -> MinimizeResult:
    """Analyze the manifest and separate top-level from transitive deps.

    A package is considered **transitive** if it appears in another
    manifest package's dependency tree.  Everything else is top-level.

    Parameters
    ----------
    path:
        Path to the manifest file.

    Returns
    -------
    MinimizeResult
        The separated packages with a ready-to-use install command.
    """
    manifest = load(path)
    all_packages = set(manifest.packages.keys())
    all_lower = {n.lower() for n in all_packages}

    # Build a map of package → its requirements (that are also in our manifest)
    required_by_others: set[str] = set()

    for pkg_name in all_packages:
        deps = _get_requires(pkg_name)
        # Any manifest package that is a dep of another manifest package
        # is transitives.
        for dep in deps:
            # Find the matching manifest entry (case-insensitive)
            for manifest_pkg in all_packages:
                if manifest_pkg.lower() == dep.lower():
                    required_by_others.add(manifest_pkg)
                    break

    top_level = {
        name: version
        for name, version in manifest.packages.items()
        if name not in required_by_others
    }
    transitive = {
        name: version
        for name, version in manifest.packages.items()
        if name in required_by_others
    }

    return MinimizeResult(top_level=top_level, transitive=transitive)
