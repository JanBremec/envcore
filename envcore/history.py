"""
Manifest version tracking — history of changes over time.

Stores manifest snapshots in ``.envcore/history/`` with timestamps.
Shows what changed between versions.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from envcore.manifest import DEFAULT_MANIFEST_PATH, Manifest, diff, load

HISTORY_DIR = ".envcore/history"


@dataclass(frozen=True)
class HistoryEntry:
    """A single history snapshot."""

    timestamp: str
    filename: str
    package_count: int
    summary: str = ""


def _history_dir(project_dir: str | Path = ".") -> Path:
    """Get or create the history directory."""
    d = Path(project_dir) / HISTORY_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_snapshot(
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    project_dir: str | Path = ".",
) -> Path:
    """Save a timestamped copy of the current manifest to history.

    Returns the path to the saved snapshot.
    """
    manifest_path = Path(manifest_path)
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    history = _history_dir(project_dir)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest = history / f"manifest_{ts}.json"
    shutil.copy2(manifest_path, dest)
    return dest


def list_history(
    project_dir: str | Path = ".",
    since: str | None = None,
) -> list[HistoryEntry]:
    """List all history snapshots.

    Parameters
    ----------
    project_dir:
        Project root directory.
    since:
        Optional ISO date string; only show entries after this date.

    Returns
    -------
    list[HistoryEntry]
        Sorted newest-first.
    """
    history = _history_dir(project_dir)
    entries: list[HistoryEntry] = []

    for f in sorted(history.glob("manifest_*.json"), reverse=True):
        try:
            manifest = load(f)
        except Exception:  # noqa: BLE001
            continue

        ts = manifest.created_at
        if since:
            try:
                since_dt = datetime.fromisoformat(since)
                created_dt = datetime.fromisoformat(ts)
                if created_dt < since_dt:
                    continue
            except (ValueError, TypeError):
                pass

        # Generate summary by comparing with previous entry
        summary = f"{len(manifest.packages)} packages"

        entries.append(HistoryEntry(
            timestamp=ts,
            filename=f.name,
            package_count=len(manifest.packages),
            summary=summary,
        ))

    return entries


def diff_history(
    project_dir: str | Path = ".",
    index_a: int = 0,
    index_b: int = 1,
):
    """Diff two history entries by index (0 = latest, 1 = previous, etc).

    Returns the diff result, or None if not enough history.
    """
    history = _history_dir(project_dir)
    files = sorted(history.glob("manifest_*.json"), reverse=True)

    if len(files) < max(index_a, index_b) + 1:
        return None

    a = load(files[index_a])
    b = load(files[index_b])
    return diff(b, a)  # b → a (old to new)
