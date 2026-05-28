"""
Resolve Python import names to PyPI package names and installed versions.

The canonical problem: ``import cv2`` comes from ``opencv-python``, and
``import PIL`` comes from ``Pillow``.  This module handles those mappings
using ``importlib.metadata`` (the ground truth) with a hand-curated
fallback table for the most common offenders.
"""

from __future__ import annotations

import importlib.metadata
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Well-known import-name → PyPI-name overrides
# ---------------------------------------------------------------------------

_KNOWN_ALIASES: dict[str, str] = {
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
    # FIX: packages whose import name differs from their PyPI distribution name
    # and which do not ship top_level.txt in modern builds.
    "pywt": "PyWavelets",
    "fitz": "PyMuPDF",
    "OpenGL": "PyOpenGL",
    "boto": "boto3",
    "pkg_resources": "setuptools",
    "Levenshtein": "python-Levenshtein",
    "usb1": "libusb1",
}


# ---------------------------------------------------------------------------
# Standard library detection
# ---------------------------------------------------------------------------

def _stdlib_module_names() -> frozenset[str]:
    """Return the set of top-level standard library module names."""
    # Python 3.10+ ships sys.stdlib_module_names
    if hasattr(sys, "stdlib_module_names"):
        return frozenset(sys.stdlib_module_names)  # type: ignore[attr-defined]

    # Fallback for 3.9: walk the stdlib directory
    stdlib_path = Path(sysconfig.get_paths()["stdlib"])
    names: set[str] = set()
    if stdlib_path.is_dir():
        for entry in stdlib_path.iterdir():
            if entry.suffix in (".py", ""):
                names.add(entry.stem)
    # Always include builtins, sys, etc.
    names.update({"builtins", "sys", "os", "io", "abc", "re", "json"})
    return frozenset(names)


_STDLIB_NAMES: frozenset[str] = _stdlib_module_names()


def is_stdlib(module_name: str) -> bool:
    """Return ``True`` if *module_name* is part of the standard library."""
    top = module_name.split(".")[0]
    return top in _STDLIB_NAMES


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResolvedPackage:
    """The result of resolving an import name."""

    import_name: str
    """The name used in the ``import`` statement."""

    package_name: str
    """The canonical PyPI package name."""

    version: str
    """Currently installed version string."""


_DIST_CACHE: dict[str, tuple[str, str]] | None = None


def _build_dist_cache() -> dict[str, tuple[str, str]]:
    """Build a reverse index: import_name → (package_name, version).

    This is O(n) on first call and O(1) on subsequent lookups.

    Resolution strategy (in priority order):

    1. ``top_level.txt`` — explicit and authoritative when present.
    2. ``RECORD``-based discovery — for modern packages that no longer ship
       ``top_level.txt`` (e.g. PyWavelets).  Walks ``dist.files()`` and
       infers top-level names from ``pkg/__init__.py`` and ``module.py``
       entries.
    3. Normalized package name — last-resort fallback.
    """
    cache: dict[str, tuple[str, str]] = {}
    for dist in importlib.metadata.distributions():
        name = dist.metadata["Name"]
        version = dist.version
        found_via_explicit = False

        # 1. Try the explicit top_level.txt first
        top_level = dist.read_text("top_level.txt")
        if top_level is not None:
            for tl_name in top_level.strip().splitlines():
                tl_name = tl_name.strip()
                if tl_name and tl_name not in cache:
                    cache[tl_name] = (name, version)
                    found_via_explicit = True

        # 2. FIX: Fall back to RECORD-based discovery for packages that omit
        #    top_level.txt (common in modern builds, e.g. PyWavelets ships
        #    pywt/__init__.py but no top_level.txt, so "pywt" was never indexed).
        if not found_via_explicit:
            try:
                files = dist.files  # list[PackagePath] | None
            except Exception:
                files = None
            if files:
                for f in files:
                    parts = f.parts
                    # Skip dist-info and data directories entirely
                    if not parts or parts[0].endswith((".dist-info", ".data")):
                        continue
                    # Top-level package: foo/__init__.py  →  index "foo"
                    if len(parts) >= 2 and parts[-1] == "__init__.py":
                        module = parts[0]
                        if module and not module.startswith("_") and module not in cache:
                            cache[module] = (name, version)
                    # Top-level module: foo.py  →  index "foo"
                    elif len(parts) == 1 and f.suffix == ".py":
                        module = parts[0][:-3]  # strip .py
                        if module and not module.startswith("_") and module not in cache:
                            cache[module] = (name, version)

        # 3. Also index by the package name itself (normalized)
        normalized = name.replace("-", "_").lower()
        if normalized not in cache:
            cache[normalized] = (name, version)

    return cache


def _search_distributions(import_name: str) -> Optional[tuple[str, str]]:
    """Search installed distributions for one that provides *import_name*.

    Returns ``(package_name, version)`` or ``None``.
    Uses a cached reverse index for O(1) lookup after first build.
    """
    global _DIST_CACHE

    # Fast path: try direct metadata lookup.
    try:
        dist = importlib.metadata.distribution(import_name)
        return dist.metadata["Name"], dist.version
    except importlib.metadata.PackageNotFoundError:
        pass

    # Build cache once, then O(1) lookup
    if _DIST_CACHE is None:
        _DIST_CACHE = _build_dist_cache()

    result = _DIST_CACHE.get(import_name)
    if result:
        return result

    # Also try normalized form
    normalized = import_name.replace("-", "_").lower()
    return _DIST_CACHE.get(normalized)


def resolve(import_name: str) -> Optional[ResolvedPackage]:
    """Map an import name to its PyPI package and installed version.

    Returns ``None`` for standard-library modules or unresolvable names.

    Parameters
    ----------
    import_name:
        The top-level module name (e.g. ``"numpy"``).

    Examples
    --------
    >>> resolve("numpy")
    ResolvedPackage(import_name='numpy', package_name='numpy', version='...')
    >>> resolve("PIL")
    ResolvedPackage(import_name='PIL', package_name='Pillow', version='...')
    >>> resolve("os")  # stdlib
    """
    top_level = import_name.split(".")[0]

    # 1. Filter stdlib
    if is_stdlib(top_level):
        return None

    # 2. Check known aliases first
    if top_level in _KNOWN_ALIASES:
        pypi_name = _KNOWN_ALIASES[top_level]
        try:
            dist = importlib.metadata.distribution(pypi_name)
            return ResolvedPackage(
                import_name=top_level,
                package_name=dist.metadata["Name"],
                version=dist.version,
            )
        except importlib.metadata.PackageNotFoundError:
            pass  # Alias exists but package not installed — fall through.

    # 3. Search distributions
    result = _search_distributions(top_level)
    if result is not None:
        pkg_name, version = result
        return ResolvedPackage(
            import_name=top_level,
            package_name=pkg_name,
            version=version,
        )

    return None


def resolve_many(import_names: list[str]) -> dict[str, ResolvedPackage]:
    """Resolve a list of import names, filtering out stdlib and unresolvable.

    Returns a dict of ``import_name → ResolvedPackage`` for every name that
    could be resolved to an installed third-party package.
    """
    results: dict[str, ResolvedPackage] = {}
    for name in import_names:
        resolved = resolve(name)
        if resolved is not None:
            results[name] = resolved
    return results
