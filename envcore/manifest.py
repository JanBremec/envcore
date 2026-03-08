"""
Manifest I/O for ``env_manifest.json``.

A manifest captures a deterministic snapshot of the packages your code
actually imported at runtime, together with metadata needed for
reproducibility (Python version, platform, creation timestamp).
"""

from __future__ import annotations

import json
import platform
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from envcore import __version__

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MANIFEST_PATH = "env_manifest.json"

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class Manifest:
    """In-memory representation of an ``env_manifest.json`` file."""

    packages: dict[str, str]
    """Mapping of PyPI package name → pinned version string."""

    envcore_version: str = ""
    python_version: str = ""
    platform: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.envcore_version:
            self.envcore_version = __version__
        if not self.python_version:
            self.python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        if not self.platform:
            self.platform = platform.platform()
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def _manifest_to_dict(manifest: Manifest) -> dict[str, Any]:
    return {
        "envcore_version": manifest.envcore_version,
        "python_version": manifest.python_version,
        "platform": manifest.platform,
        "created_at": manifest.created_at,
        "packages": dict(sorted(manifest.packages.items())),
    }


def _dict_to_manifest(data: dict[str, Any]) -> Manifest:
    return Manifest(
        packages=data.get("packages", {}),
        envcore_version=data.get("envcore_version", "unknown"),
        python_version=data.get("python_version", "unknown"),
        platform=data.get("platform", "unknown"),
        created_at=data.get("created_at", "unknown"),
    )


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def save(
    manifest: Manifest,
    path: str | Path = DEFAULT_MANIFEST_PATH,
) -> Path:
    """Write *manifest* to disk as JSON.

    Returns the resolved :class:`Path` that was written.
    """
    dest = Path(path)
    dest.write_text(json.dumps(_manifest_to_dict(manifest), indent=2) + "\n")
    return dest


def load(path: str | Path = DEFAULT_MANIFEST_PATH) -> Manifest:
    """Read a manifest from *path*.

    Raises :class:`FileNotFoundError` if the file does not exist.
    """
    src = Path(path)
    data = json.loads(src.read_text())
    return _dict_to_manifest(data)


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ManifestDiff:
    """Difference between two manifests."""

    added: dict[str, str] = field(default_factory=dict)
    """Packages present in *b* but not in *a*."""

    removed: dict[str, str] = field(default_factory=dict)
    """Packages present in *a* but not in *b*."""

    changed: dict[str, tuple[str, str]] = field(default_factory=dict)
    """Packages whose version changed: ``{name: (old_version, new_version)}``."""

    @property
    def is_empty(self) -> bool:
        return not self.added and not self.removed and not self.changed


def diff(a: Manifest, b: Manifest) -> ManifestDiff:
    """Compute the difference *a → b*.

    - ``added``  — in *b* but not *a*
    - ``removed`` — in *a* but not *b*
    - ``changed`` — version differs between *a* and *b*
    """
    keys_a = set(a.packages)
    keys_b = set(b.packages)

    added = {k: b.packages[k] for k in sorted(keys_b - keys_a)}
    removed = {k: a.packages[k] for k in sorted(keys_a - keys_b)}
    changed = {
        k: (a.packages[k], b.packages[k])
        for k in sorted(keys_a & keys_b)
        if a.packages[k] != b.packages[k]
    }

    return ManifestDiff(added=added, removed=removed, changed=changed)
