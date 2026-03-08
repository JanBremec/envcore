"""
Git hooks integration — auto-update manifest on commit.

Installs a pre-commit hook that traces the project's entry points
and auto-stages the manifest if it changed.
"""

from __future__ import annotations

import stat
from pathlib import Path

_HOOK_SCRIPT = '''\
#!/usr/bin/env sh
# envcore pre-commit hook — auto-update manifest
# Installed by: envcore hooks install

set -e

# Re-trace to pick up any new imports
if command -v envcore >/dev/null 2>&1; then
    echo "[envcore] Checking manifest..."

    # If manifest exists and is tracked, check for changes
    if [ -f "env_manifest.json" ]; then
        envcore doctor env_manifest.json --no-outdated 2>/dev/null || true
    fi

    # Auto-stage manifest if it changed
    if git diff --name-only --cached | grep -q "env_manifest.json"; then
        echo "[envcore] Manifest staged for commit."
    fi
else
    echo "[envcore] envcore not found, skipping hook."
fi
'''


def _find_git_dir(start: str | Path = ".") -> Path | None:
    """Walk up the directory tree to find ``.git/``."""
    current = Path(start).resolve()
    for parent in [current, *current.parents]:
        git_dir = parent / ".git"
        if git_dir.is_dir():
            return git_dir
    return None


def install_hooks(project_dir: str | Path = ".") -> Path:
    """Install the envcore pre-commit hook.

    Returns the path to the installed hook file.

    Raises
    ------
    FileNotFoundError
        If no ``.git/`` directory is found.
    """
    git_dir = _find_git_dir(project_dir)
    if git_dir is None:
        raise FileNotFoundError(
            "No .git directory found. "
            "Run 'git init' first or run this from inside a git repository."
        )

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    hook_path = hooks_dir / "pre-commit"

    # If a hook already exists, append our script
    if hook_path.exists():
        existing = hook_path.read_text()
        if "envcore" in existing:
            return hook_path  # Already installed
        # Append to existing hook
        with open(hook_path, "a") as f:
            f.write("\n\n# --- envcore hook ---\n")
            f.write(_HOOK_SCRIPT.split("\n", 1)[1])  # Skip shebang
    else:
        hook_path.write_text(_HOOK_SCRIPT)

    # Make executable
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC)
    return hook_path


def uninstall_hooks(project_dir: str | Path = ".") -> bool:
    """Remove the envcore pre-commit hook.

    Returns ``True`` if the hook was removed, ``False`` if not found.
    """
    git_dir = _find_git_dir(project_dir)
    if git_dir is None:
        return False

    hook_path = git_dir / "hooks" / "pre-commit"
    if not hook_path.exists():
        return False

    content = hook_path.read_text()
    if "envcore" not in content:
        return False

    # If the entire hook is ours, remove it
    if content.strip() == _HOOK_SCRIPT.strip():
        hook_path.unlink()
        return True

    # Otherwise, remove just our section
    lines = content.split("\n")
    new_lines = []
    skip = False
    for line in lines:
        if "--- envcore hook ---" in line:
            skip = True
            continue
        if skip and line.startswith("#!/"):
            skip = False
        if not skip:
            new_lines.append(line)

    hook_path.write_text("\n".join(new_lines))
    return True
