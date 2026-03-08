"""
Bidirectional sync between manifest and project dependency files.

Detects existing config files (requirements.txt, pyproject.toml) and
shows what's in the manifest but not in the config (and vice versa).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from envcore.manifest import DEFAULT_MANIFEST_PATH, Manifest, load


SyncTarget = Literal["requirements", "pyproject"]


@dataclass
class SyncDiff:
    """Difference between manifest and a project file."""

    target_file: str
    target_format: SyncTarget

    # packages in manifest but not in target
    missing_in_target: dict[str, str] = field(default_factory=dict)

    # packages in target but not in manifest
    missing_in_manifest: dict[str, str] = field(default_factory=dict)

    # packages where versions differ
    version_mismatch: dict[str, tuple[str, str]] = field(
        default_factory=dict,
    )  # name: (manifest_version, target_version)

    @property
    def in_sync(self) -> bool:
        return (
            not self.missing_in_target
            and not self.missing_in_manifest
            and not self.version_mismatch
        )


def _parse_requirements(path: Path) -> dict[str, str]:
    """Parse a requirements.txt file into {name: version}."""
    packages: dict[str, str] = {}
    if not path.exists():
        return packages

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Match: package==version or package>=version or just package
        match = re.match(r"^([a-zA-Z0-9._-]+)\s*(?:==|>=|~=|!=)\s*([^\s;#]+)", line)
        if match:
            packages[match.group(1)] = match.group(2)
        elif re.match(r"^[a-zA-Z0-9._-]+$", line):
            packages[line] = "*"
    return packages


def _parse_pyproject_deps(path: Path) -> dict[str, str]:
    """Parse dependencies from a pyproject.toml file."""
    packages: dict[str, str] = {}
    if not path.exists():
        return packages

    content = path.read_text()
    # Simple regex to find dependencies = [...] block
    match = re.search(r'dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
    if not match:
        return packages

    deps_block = match.group(1)
    for dep_match in re.finditer(r'"([a-zA-Z0-9._-]+)\s*(?:==|>=|~=)\s*([^"]+)"', deps_block):
        packages[dep_match.group(1)] = dep_match.group(2)

    return packages


def _detect_target(project_dir: str | Path = ".") -> tuple[SyncTarget, Path] | None:
    """Auto-detect the project's dependency file."""
    root = Path(project_dir)

    # Check for requirements.txt first (most common)
    req = root / "requirements.txt"
    if req.exists():
        return "requirements", req

    # Check pyproject.toml
    pyp = root / "pyproject.toml"
    if pyp.exists():
        return "pyproject", pyp

    return None


def diff_sync(
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    target: str | Path | None = None,
    project_dir: str | Path = ".",
) -> SyncDiff | None:
    """Compute the diff between manifest and a dependency file.

    If *target* is ``None``, auto-detects the project format.

    Returns ``None`` if no dependency file is found.
    """
    manifest = load(manifest_path)

    if target is not None:
        target_path = Path(target)
        if target_path.name == "requirements.txt" or target_path.suffix == ".txt":
            fmt: SyncTarget = "requirements"
            target_deps = _parse_requirements(target_path)
        else:
            fmt = "pyproject"
            target_deps = _parse_pyproject_deps(target_path)
    else:
        detected = _detect_target(project_dir)
        if detected is None:
            return None
        fmt, target_path = detected
        if fmt == "requirements":
            target_deps = _parse_requirements(target_path)
        else:
            target_deps = _parse_pyproject_deps(target_path)

    # Build case-insensitive lookup
    manifest_lower = {k.lower(): (k, v) for k, v in manifest.packages.items()}
    target_lower = {k.lower(): (k, v) for k, v in target_deps.items()}

    result = SyncDiff(
        target_file=str(target_path),
        target_format=fmt,
    )

    # In manifest but not in target
    for lower_name, (name, version) in manifest_lower.items():
        if lower_name not in target_lower:
            result.missing_in_target[name] = version

    # In target but not in manifest
    for lower_name, (name, version) in target_lower.items():
        if lower_name not in manifest_lower:
            result.missing_in_manifest[name] = version

    # Version mismatches
    for lower_name in manifest_lower:
        if lower_name in target_lower:
            m_name, m_ver = manifest_lower[lower_name]
            t_name, t_ver = target_lower[lower_name]
            if m_ver != t_ver and t_ver != "*":
                result.version_mismatch[m_name] = (m_ver, t_ver)

    return result


def apply_to_requirements(
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    target: str | Path = "requirements.txt",
) -> Path:
    """Overwrite a requirements.txt with the manifest's packages.

    Returns the path written.
    """
    manifest = load(manifest_path)
    from envcore.export import export
    content = export(manifest, "requirements")
    dest = Path(target)
    dest.write_text(content)
    return dest
