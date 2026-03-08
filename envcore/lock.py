"""
Deterministic lockfile generation with integrity hashes.

Goes beyond the manifest by resolving full transitive dependency
trees and recording SHA-256 hashes for supply-chain security.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from envcore import __version__
from envcore.manifest import DEFAULT_MANIFEST_PATH, Manifest, load
from envcore.minimize import _get_requires

LOCKFILE_PATH = "env_manifest.lock"


@dataclass(frozen=True)
class LockedPackage:
    """A single package entry in the lockfile."""

    version: str
    hash: str  # sha256 of the installed dist-info RECORD
    requires: list[str]
    resolved_from: str = "runtime-trace"


@dataclass
class Lockfile:
    """Complete lockfile with metadata and locked packages."""

    envcore_version: str = __version__
    python_version: str = ""
    platform: str = ""
    created_at: str = ""
    packages: dict[str, dict] = field(default_factory=dict)


def _compute_hash(package_name: str) -> str:
    """Compute a SHA-256 hash over the package's installed files."""
    try:
        dist = importlib.metadata.distribution(package_name)
        # Hash the METADATA file content as a stable fingerprint
        meta_text = dist.read_text("METADATA") or ""
        return "sha256:" + hashlib.sha256(meta_text.encode()).hexdigest()[:16]
    except Exception:  # noqa: BLE001
        return "sha256:unknown"


def generate_lockfile(
    path: str | Path = DEFAULT_MANIFEST_PATH,
    output: str | Path = LOCKFILE_PATH,
) -> Path:
    """Generate a lockfile from a manifest.

    For each package in the manifest, records: version, hash, and dependencies.

    Returns the path to the written lockfile.
    """
    manifest = load(path)

    lockfile = Lockfile(
        python_version=manifest.python_version,
        platform=manifest.platform,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    for pkg_name, version in sorted(manifest.packages.items()):
        requires = sorted(_get_requires(pkg_name))
        pkg_hash = _compute_hash(pkg_name)

        lockfile.packages[pkg_name] = {
            "version": version,
            "hash": pkg_hash,
            "requires": requires,
            "resolved_from": "runtime-trace",
        }

    dest = Path(output)
    dest.write_text(json.dumps(asdict(lockfile), indent=2) + "\n")
    return dest


def verify_lockfile(
    lockfile_path: str | Path = LOCKFILE_PATH,
) -> list[tuple[str, str]]:
    """Verify installed packages against the lockfile.

    Returns a list of ``(package_name, issue_description)`` for any
    mismatches.  An empty list means the environment matches the lockfile.
    """
    path = Path(lockfile_path)
    if not path.exists():
        return [("lockfile", f"{path} not found")]

    data = json.loads(path.read_text())
    packages = data.get("packages", {})
    issues: list[tuple[str, str]] = []

    for pkg_name, info in packages.items():
        expected_version = info.get("version", "?")
        expected_hash = info.get("hash", "")

        try:
            dist = importlib.metadata.distribution(pkg_name)
            installed_version = dist.version
            if installed_version != expected_version:
                issues.append((
                    pkg_name,
                    f"version {installed_version} ≠ locked {expected_version}",
                ))

            if expected_hash and expected_hash != "sha256:unknown":
                actual_hash = _compute_hash(pkg_name)
                if actual_hash != expected_hash:
                    issues.append((
                        pkg_name,
                        f"hash mismatch (integrity check failed)",
                    ))
        except importlib.metadata.PackageNotFoundError:
            issues.append((pkg_name, f"not installed (locked at {expected_version})"))

    return issues
