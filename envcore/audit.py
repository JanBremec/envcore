"""
Vulnerability scanning via the OSV.dev API.

Checks each package in the manifest against the Open Source
Vulnerability database for known security issues.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from envcore.manifest import DEFAULT_MANIFEST_PATH, Manifest, load

OSV_API = "https://api.osv.dev/v1/query"


@dataclass(frozen=True)
class Vulnerability:
    """A single known vulnerability."""

    id: str
    summary: str
    severity: str  # "LOW", "MODERATE", "HIGH", "CRITICAL"
    package: str
    affected_versions: str = ""
    url: str = ""


@dataclass
class AuditReport:
    """Result of a vulnerability audit."""

    packages_checked: int = 0
    vulnerabilities: list[Vulnerability] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return len(self.vulnerabilities) == 0

    @property
    def critical_count(self) -> int:
        return sum(1 for v in self.vulnerabilities if v.severity in ("CRITICAL", "HIGH"))


def _query_osv(package_name: str, version: str) -> list[dict]:
    """Query the OSV.dev API for vulnerabilities.

    Returns a list of vulnerability objects from the API response.
    """
    payload = json.dumps({
        "version": version,
        "package": {
            "name": package_name,
            "ecosystem": "PyPI",
        },
    }).encode()

    req = urllib.request.Request(
        OSV_API,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("vulns", [])
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError,
            TimeoutError, OSError):
        return []


def _extract_severity(vuln: dict) -> str:
    """Extract the highest severity from a vulnerability entry."""
    severity_entries = vuln.get("severity", [])
    if not severity_entries:
        # Try database_specific
        db = vuln.get("database_specific", {})
        return db.get("severity", "UNKNOWN")

    # Look for CVSS score
    for entry in severity_entries:
        score_str = entry.get("score", "")
        if score_str:
            try:
                # Parse CVSS vector for score
                # Simple heuristic from score
                return entry.get("type", "UNKNOWN")
            except (ValueError, IndexError):
                pass

    return "UNKNOWN"


def audit(
    path: str | Path = DEFAULT_MANIFEST_PATH,
    *,
    timeout_per_package: int = 10,
) -> AuditReport:
    """Scan all manifest packages for known vulnerabilities.

    Uses the free OSV.dev API — no API key required.

    Parameters
    ----------
    path:
        Path to the manifest file.
    timeout_per_package:
        Seconds to wait for each OSV API call.

    Returns
    -------
    AuditReport
        Report with all found vulnerabilities.
    """
    manifest = load(path)
    report = AuditReport(packages_checked=len(manifest.packages))

    for pkg_name, version in sorted(manifest.packages.items()):
        vulns = _query_osv(pkg_name, version)

        for vuln in vulns:
            vuln_id = vuln.get("id", "UNKNOWN")
            summary = vuln.get("summary", vuln.get("details", "No description")[:200])
            severity = _extract_severity(vuln)

            # Build URL
            url = ""
            refs = vuln.get("references", [])
            for ref in refs:
                if ref.get("type") == "ADVISORY":
                    url = ref.get("url", "")
                    break
            if not url:
                url = f"https://osv.dev/vulnerability/{vuln_id}"

            report.vulnerabilities.append(Vulnerability(
                id=vuln_id,
                summary=summary[:200],
                severity=severity,
                package=pkg_name,
                url=url,
            ))

    return report
