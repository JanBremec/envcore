"""Tests for ``envcore.hooks``."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from envcore.hooks import install_hooks, uninstall_hooks


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    """Create a fake git repo."""
    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    return tmp_path


class TestHooks:
    def test_install_creates_hook(self, git_repo: Path) -> None:
        path = install_hooks(git_repo)
        assert path.exists()
        assert "envcore" in path.read_text()
        # Should be executable
        assert path.stat().st_mode & stat.S_IEXEC

    def test_install_idempotent(self, git_repo: Path) -> None:
        install_hooks(git_repo)
        install_hooks(git_repo)
        hook = git_repo / ".git" / "hooks" / "pre-commit"
        # Should not duplicate the envcore section
        content = hook.read_text()
        assert content.count("envcore pre-commit hook") == 1

    def test_install_no_git_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="No .git"):
            install_hooks(tmp_path)

    def test_uninstall_removes_hook(self, git_repo: Path) -> None:
        install_hooks(git_repo)
        assert uninstall_hooks(git_repo) is True
        hook = git_repo / ".git" / "hooks" / "pre-commit"
        assert not hook.exists()

    def test_uninstall_no_hook(self, git_repo: Path) -> None:
        assert uninstall_hooks(git_repo) is False

    def test_install_alongside_existing_hook(self, git_repo: Path) -> None:
        hook = git_repo / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\necho 'existing hook'\n")
        hook.chmod(hook.stat().st_mode | stat.S_IEXEC)
        install_hooks(git_repo)
        content = hook.read_text()
        assert "existing hook" in content
        assert "envcore" in content
