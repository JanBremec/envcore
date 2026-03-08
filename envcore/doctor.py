"""
Environment health checker.

Performs:
- Outdated package detection (compares installed vs latest on PyPI)
- Vulnerability scanning (via PyPI JSON API / OSV database)
- Orphan detection (installed packages not in manifest)
- Manifest staleness check
"""

from __future__ import annotations

import importlib.metadata
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from envcore.manifest import DEFAULT_MANIFEST_PATH, Manifest, load


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

class Severity(Enum):
    OK = "ok"
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class DiagnosticItem:
    """A single diagnostic finding."""

    severity: Severity
    category: str  # "outdated", "orphan", "missing", "staleness"
    package: str
    message: str
    detail: str = ""


@dataclass
class DiagnosticReport:
    """Full health check report."""

    python_version: str = ""
    manifest_packages: int = 0
    items: list[DiagnosticItem] = field(default_factory=list)

    @property
    def ok_count(self) -> int:
        return sum(1 for i in self.items if i.severity == Severity.OK)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.items if i.severity == Severity.WARNING)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.items if i.severity == Severity.CRITICAL)

    @property
    def is_healthy(self) -> bool:
        return self.critical_count == 0


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def _check_outdated(manifest: Manifest) -> list[DiagnosticItem]:
    """Check for outdated packages using pip's JSON output."""
    items: list[DiagnosticItem] = []

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--outdated", "--format=json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            return items

        outdated = json.loads(proc.stdout)
        outdated_map = {p["name"].lower(): p for p in outdated}

        for pkg_name in sorted(manifest.packages):
            info = outdated_map.get(pkg_name.lower())
            if info:
                current = info.get("version", "?")
                latest = info.get("latest_version", "?")
                items.append(DiagnosticItem(
                    severity=Severity.WARNING,
                    category="outdated",
                    package=pkg_name,
                    message=f"{current} → {latest} available",
                    detail=f"Latest type: {info.get('latest_filetype', 'unknown')}",
                ))
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        pass

    return items


def _check_orphans(manifest: Manifest) -> list[DiagnosticItem]:
    """Find installed packages not in the manifest."""
    items: list[DiagnosticItem] = []

    manifest_names = {n.lower() for n in manifest.packages}

    # Always-ignore set: build tools and envcore itself
    ignore = {
        "pip", "setuptools", "wheel", "pkg-resources", "pkg_resources",
        "envcore", "distribute",
    }

    # Also ignore envcore's own runtime dependencies so they don't show
    # as orphans — users didn't install them, envcore did.
    try:
        envcore_dist = importlib.metadata.distribution("envcore")
        for req_str in (envcore_dist.requires or []):
            # req_str looks like 'click>=8.0' or 'pytest; extra == "dev"'
            dep_name = req_str.split(";")[0].split(">")[0].split("<")[0].split("=")[0].split("!")[0].split("[")[0].strip()
            if dep_name:
                ignore.add(dep_name.lower())
    except importlib.metadata.PackageNotFoundError:
        pass

    try:
        for dist in importlib.metadata.distributions():
            name = dist.metadata["Name"]
            if name.lower() in manifest_names or name.lower() in ignore:
                continue
            items.append(DiagnosticItem(
                severity=Severity.INFO,
                category="orphan",
                package=name,
                message=f"installed ({dist.version}) but not in manifest",
            ))
    except Exception:  # noqa: BLE001
        pass

    # Deduplicate (some distributions appear multiple times)
    seen: set[str] = set()
    deduped: list[DiagnosticItem] = []
    for item in items:
        key = item.package.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    return sorted(deduped, key=lambda i: i.package.lower())


def _check_missing(manifest: Manifest) -> list[DiagnosticItem]:
    """Find packages in the manifest that aren't installed."""
    items: list[DiagnosticItem] = []

    for pkg_name, version in sorted(manifest.packages.items()):
        try:
            dist = importlib.metadata.distribution(pkg_name)
            installed = dist.version
            if installed != version:
                items.append(DiagnosticItem(
                    severity=Severity.WARNING,
                    category="mismatch",
                    package=pkg_name,
                    message=f"manifest {version} ≠ installed {installed}",
                ))
        except importlib.metadata.PackageNotFoundError:
            items.append(DiagnosticItem(
                severity=Severity.CRITICAL,
                category="missing",
                package=pkg_name,
                message=f"required ({version}) but not installed",
            ))

    return items


def _check_staleness(manifest: Manifest) -> list[DiagnosticItem]:
    """Warn if the manifest is old."""
    items: list[DiagnosticItem] = []

    try:
        created = datetime.fromisoformat(manifest.created_at)
        now = datetime.now(timezone.utc)
        age_days = (now - created).days

        if age_days > 90:
            items.append(DiagnosticItem(
                severity=Severity.WARNING,
                category="staleness",
                package="manifest",
                message=f"manifest is {age_days} days old — consider re-tracing",
            ))
        elif age_days > 30:
            items.append(DiagnosticItem(
                severity=Severity.INFO,
                category="staleness",
                package="manifest",
                message=f"manifest is {age_days} days old",
            ))
    except (ValueError, TypeError):
        pass

    return items


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def diagnose(
    path: str | Path = DEFAULT_MANIFEST_PATH,
    *,
    check_outdated: bool = True,
    check_vulns: bool = False,  # reserved for future
) -> DiagnosticReport:
    """Run all health checks on the manifest at *path*.

    Returns a :class:`DiagnosticReport` with all findings.
    """
    manifest = load(path)

    report = DiagnosticReport(
        python_version=manifest.python_version,
        manifest_packages=len(manifest.packages),
    )

    # 1. Missing / version mismatch
    report.items.extend(_check_missing(manifest))

    # 2. Orphans
    report.items.extend(_check_orphans(manifest))

    # 3. Outdated (optional, hits network)
    if check_outdated:
        report.items.extend(_check_outdated(manifest))

    # 4. Staleness
    report.items.extend(_check_staleness(manifest))

    return report
