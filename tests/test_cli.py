"""Tests for ``envcore.cli``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from envcore.cli import cli


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def sample_manifest(tmp_path: Path) -> Path:
    path = tmp_path / "env_manifest.json"
    path.write_text(json.dumps({
        "envcore_version": "0.1.0",
        "python_version": "3.11.5",
        "platform": "test",
        "created_at": "2026-01-01T00:00:00Z",
        "packages": {
            "click": "8.1.7",
            "numpy": "1.26.4",
        },
    }, indent=2))
    return path


class TestVersion:
    def test_version_flag(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "envcore" in result.output

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "envcore" in result.output


class TestInit:
    def test_creates_manifest(self, runner: CliRunner, tmp_path: Path) -> None:
        output = tmp_path / "env_manifest.json"
        result = runner.invoke(cli, ["init", "-o", str(output)])
        assert result.exit_code == 0
        assert output.exists()

        data = json.loads(output.read_text())
        assert data["packages"] == {}
        assert "envcore_version" in data

    def test_refuses_overwrite(self, runner: CliRunner, tmp_path: Path) -> None:
        output = tmp_path / "env_manifest.json"
        output.write_text("{}")

        result = runner.invoke(cli, ["init", "-o", str(output)])
        assert result.exit_code != 0

    def test_force_overwrite(self, runner: CliRunner, tmp_path: Path) -> None:
        output = tmp_path / "env_manifest.json"
        output.write_text("{}")

        result = runner.invoke(cli, ["init", "-o", str(output), "--force"])
        assert result.exit_code == 0


class TestShow:
    def test_show_manifest(self, runner: CliRunner, sample_manifest: Path) -> None:
        result = runner.invoke(cli, ["show", str(sample_manifest)])
        assert result.exit_code == 0
        assert "click" in result.output
        assert "numpy" in result.output
        assert "2 packages" in result.output


class TestDiff:
    def test_diff_identical(self, runner: CliRunner, sample_manifest: Path) -> None:
        result = runner.invoke(cli, ["diff", str(sample_manifest), str(sample_manifest)])
        assert result.exit_code == 0
        assert "identical" in result.output

    def test_diff_different(self, runner: CliRunner, tmp_path: Path) -> None:
        a = tmp_path / "a.json"
        b = tmp_path / "b.json"
        a.write_text(json.dumps({
            "envcore_version": "0.1.0",
            "python_version": "3.11.5",
            "platform": "test",
            "created_at": "2026-01-01T00:00:00Z",
            "packages": {"numpy": "1.25.0"},
        }))
        b.write_text(json.dumps({
            "envcore_version": "0.1.0",
            "python_version": "3.11.5",
            "platform": "test",
            "created_at": "2026-01-01T00:00:00Z",
            "packages": {"numpy": "1.26.4", "torch": "2.1.0"},
        }))

        result = runner.invoke(cli, ["diff", str(a), str(b)])
        assert result.exit_code == 0
        assert "torch" in result.output  # added
        assert "numpy" in result.output  # changed


class TestRestore:
    def test_dry_run(self, runner: CliRunner, sample_manifest: Path) -> None:
        result = runner.invoke(cli, ["restore", str(sample_manifest), "--dry-run"])
        assert result.exit_code == 0
        assert "pip install" in result.output
        assert "click==8.1.7" in result.output
        assert "numpy==1.26.4" in result.output


class TestTrace:
    def test_trace_demo(self, runner: CliRunner, tmp_path: Path) -> None:
        script = tmp_path / "test_script.py"
        script.write_text("import json\nimport os\nprint('hello')\n")

        output = tmp_path / "out.json"
        result = runner.invoke(cli, ["trace", str(script), "-o", str(output)])
        # Should succeed even if no third-party imports found
        assert result.exit_code == 0
