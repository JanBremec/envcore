"""
``envcore`` command-line interface.

Built with `Click <https://click.palletsprojects.com>`_ for a clean,
composable CLI experience.

Commands
--------
- ``envcore trace <script>``   — run a script with import tracing
- ``envcore snapshot``         — snapshot traced imports to manifest
- ``envcore restore``          — recreate environment from manifest
- ``envcore show``             — pretty-print a manifest
- ``envcore diff``             — compare two manifests
- ``envcore init``             — create a blank manifest
- ``envcore export``           — export manifest to other formats
- ``envcore doctor``           — environment health check
- ``envcore clean``            — remove orphan packages
- ``envcore watch``            — live development monitor
- ``envcore minimize``         — find minimal install set
- ``envcore lock``             — generate lockfile with hashes
- ``envcore graph``            — dependency graph visualisation
- ``envcore ci``               — CI/CD environment verification
- ``envcore hooks``            — git hook management
- ``envcore history``          — manifest version tracking
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

import click

import os

from envcore import __version__

# ---------------------------------------------------------------------------
# Styles — respect NO_COLOR (https://no-color.org)
# ---------------------------------------------------------------------------

_NO_COLOR = "NO_COLOR" in os.environ


def _style(text: str, **kwargs) -> str:
    """Wrapper around click.style that respects NO_COLOR."""
    if _NO_COLOR:
        return text
    return click.style(text, **kwargs)


_BRAND = "envcore"
_TICK = _style("✔", fg="green", bold=True)
_CROSS = _style("✖", fg="red", bold=True)
_ARROW = _style("→", fg="cyan")
_PLUS = _style("+", fg="green")
_MINUS = _style("-", fg="red")
_DELTA = _style("~", fg="yellow")


def _header(text: str) -> str:
    return _style(text, fg="cyan", bold=True)


def _dim(text: str) -> str:
    return _style(text, fg="bright_black")


def _pkg(name: str, version: str) -> str:
    return f"{_style(name, bold=True)} {_dim(version)}"


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(__version__, "-V", "--version", prog_name=_BRAND)
def cli() -> None:
    """envcore — Automatic Python environment reconstruction.

    Runtime import tracing, deterministic snapshots, one-command restore.
    """


# ---------------------------------------------------------------------------
# trace
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("script", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "-o", "--output",
    default="env_manifest.json",
    show_default=True,
    help="Output manifest path.",
)
def trace(script: str, output: str) -> None:
    """Run SCRIPT with import tracing and save a manifest.

    Executes the given Python script in a subprocess-like fashion while
    recording every ``import`` that occurs.  The captured dependencies
    are resolved to their PyPI package names and saved to a JSON manifest.

    \b
    Example:
        envcore trace train.py
        envcore trace train.py -o requirements.json
    """
    from envcore.manifest import Manifest, save
    from envcore.resolver import resolve_many
    from envcore.tracer import ImportTracer

    click.echo(f"\n  {_header('envcore trace')}  {_dim(script)}\n")

    tracer = ImportTracer()
    tracer.start()

    script_error: Exception | None = None
    try:
        # Run the script in its own namespace, similar to `python script.py`.
        sys.argv = [script]
        runpy.run_path(script, run_name="__main__")
    except SystemExit:
        pass  # Scripts may call sys.exit(); that's fine.
    except Exception as exc:
        script_error = exc
        click.echo(f"  {_CROSS}  Script raised {type(exc).__name__}: {exc}\n")
    finally:
        tracer.stop()

    # Always resolve and save — even if the script crashed.
    # Partial results are better than no results for debugging.
    imports = tracer.imports
    resolved = resolve_many(list(imports.keys()))

    packages = {r.package_name: r.version for r in resolved.values()}
    manifest = Manifest(packages=packages)
    dest = save(manifest, output)

    if not packages:
        click.echo(f"  {_dim('No third-party imports detected.')}")
        click.echo(f"  {_TICK}  Empty manifest saved to {click.style(str(dest), underline=True)}\n")
    else:
        click.echo(f"  {_TICK}  Traced {click.style(str(len(packages)), bold=True)} packages:\n")
        for name, version in sorted(packages.items()):
            click.echo(f"    {_ARROW}  {_pkg(name, version)}")
        click.echo(f"\n  {_TICK}  Manifest saved to {click.style(str(dest), underline=True)}\n")

    if script_error is not None:
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# snapshot
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "-o", "--output",
    default="env_manifest.json",
    show_default=True,
    help="Output manifest path.",
)
def snapshot(output: str) -> None:
    """Snapshot the default tracer's imports to a manifest.

    Use this after calling ``envcore.start_tracking()`` and
    ``envcore.stop_tracking()`` from within your own code.

    \b
    Example:
        envcore snapshot
        envcore snapshot -o my_deps.json
    """
    from envcore.manifest import Manifest, save
    from envcore.resolver import resolve_many
    from envcore.tracer import get_imports

    click.echo(f"\n  {_header('envcore snapshot')}\n")

    imports = get_imports()
    if not imports:
        click.echo(f"  {_dim('No imports recorded. Did you call envcore.start_tracking()?')}\n")
        return

    resolved = resolve_many(list(imports.keys()))
    packages = {r.package_name: r.version for r in resolved.values()}
    manifest = Manifest(packages=packages)
    dest = save(manifest, output)

    click.echo(f"  {_TICK}  Snapshot: {click.style(str(len(packages)), bold=True)} packages {_ARROW} {click.style(str(dest), underline=True)}\n")


# ---------------------------------------------------------------------------
# restore
# ---------------------------------------------------------------------------


@cli.command()
@click.argument(
    "manifest_path",
    default="env_manifest.json",
    type=click.Path(exists=True, dir_okay=False),
)
@click.option("--dry-run", is_flag=True, help="Print install commands without executing.")
@click.option("-q", "--quiet", is_flag=True, help="Suppress pip output.")
def restore(manifest_path: str, dry_run: bool, quiet: bool) -> None:
    """Restore an environment from a manifest file.

    Reads MANIFEST_PATH (default: env_manifest.json) and runs
    ``pip install package==version`` for each entry.

    \b
    Example:
        envcore restore
        envcore restore requirements.json --dry-run
    """
    from envcore.restore import restore as do_restore

    click.echo(f"\n  {_header('envcore restore')}  {_dim(manifest_path)}\n")

    if dry_run:
        click.echo(f"  {_dim('Dry run — no packages will be installed.')}\n")

    results = do_restore(manifest_path, dry_run=dry_run, quiet=quiet)

    succeeded = 0
    failed = 0
    for r in results:
        if dry_run:
            click.echo(f"    {_ARROW}  {r.message}")
        elif r.success:
            click.echo(f"    {_TICK}  {_pkg(r.package, r.version)}")
            succeeded += 1
        else:
            click.echo(f"    {_CROSS}  {_pkg(r.package, r.version)}  {_dim(r.message)}")
            failed += 1

    click.echo()
    if not dry_run:
        click.echo(f"  {_TICK}  {succeeded} installed", nl=False)
        if failed:
            click.echo(f"  {_CROSS}  {failed} failed", nl=False)
        click.echo("\n")

    if failed:
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------


@cli.command()
@click.argument(
    "manifest_path",
    default="env_manifest.json",
    type=click.Path(exists=True, dir_okay=False),
)
def show(manifest_path: str) -> None:
    """Pretty-print a manifest file.

    \b
    Example:
        envcore show
        envcore show my_deps.json
    """
    from envcore.manifest import load

    manifest = load(manifest_path)

    click.echo(f"\n  {_header('envcore manifest')}  {_dim(manifest_path)}\n")
    click.echo(f"    envcore   {_dim(manifest.envcore_version)}")
    click.echo(f"    python    {_dim(manifest.python_version)}")
    click.echo(f"    platform  {_dim(manifest.platform)}")
    click.echo(f"    created   {_dim(manifest.created_at)}")
    click.echo()

    if not manifest.packages:
        click.echo(f"    {_dim('(no packages)')}\n")
        return

    click.echo(f"    {click.style(str(len(manifest.packages)), bold=True)} packages:\n")
    for name, version in sorted(manifest.packages.items()):
        click.echo(f"      {_pkg(name, version)}")
    click.echo()


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("file_a", type=click.Path(exists=True, dir_okay=False))
@click.argument("file_b", type=click.Path(exists=True, dir_okay=False))
def diff(file_a: str, file_b: str) -> None:
    """Show differences between two manifest files.

    \b
    Example:
        envcore diff old_manifest.json env_manifest.json
    """
    from envcore.manifest import diff as manifest_diff
    from envcore.manifest import load

    a = load(file_a)
    b = load(file_b)
    d = manifest_diff(a, b)

    click.echo(f"\n  {_header('envcore diff')}  {_dim(file_a)} {_ARROW} {_dim(file_b)}\n")

    if d.is_empty:
        click.echo(f"    {_dim('Manifests are identical.')}\n")
        return

    if d.added:
        for name, version in d.added.items():
            click.echo(f"    {_PLUS}  {_pkg(name, version)}")
    if d.removed:
        for name, version in d.removed.items():
            click.echo(f"    {_MINUS}  {_pkg(name, version)}")
    if d.changed:
        for name, (old, new) in d.changed.items():
            click.echo(f"    {_DELTA}  {click.style(name, bold=True)}  {_dim(old)} {_ARROW} {_dim(new)}")

    click.echo()


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "-o", "--output",
    default="env_manifest.json",
    show_default=True,
    help="Output manifest path.",
)
@click.option("-f", "--force", is_flag=True, help="Overwrite existing manifest.")
def init(output: str, force: bool) -> None:
    """Create a blank manifest file.

    \b
    Example:
        envcore init
        envcore init -o requirements.json
    """
    from envcore.manifest import Manifest, save

    dest = Path(output)
    if dest.exists() and not force:
        click.echo(
            f"\n  {_CROSS}  {click.style(str(dest), underline=True)} already exists."
            f"  Use {click.style('--force', bold=True)} to overwrite.\n"
        )
        raise SystemExit(1)

    manifest = Manifest(packages={})
    save(manifest, dest)
    click.echo(f"\n  {_TICK}  Created {click.style(str(dest), underline=True)}\n")


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------


@cli.command("export")
@click.argument(
    "manifest_path",
    default="env_manifest.json",
    type=click.Path(exists=True, dir_okay=False),
)
@click.option(
    "-f", "--format", "fmt",
    type=click.Choice(
        ["requirements", "pyproject", "conda", "docker", "pipfile", "setup"],
        case_sensitive=False,
    ),
    default="requirements",
    show_default=True,
    help="Output format.",
)
@click.option("-o", "--output", default=None, help="Output file path (default: auto).")
@click.option("--stdout", is_flag=True, help="Print to stdout instead of file.")
def export_cmd(manifest_path: str, fmt: str, output: str | None, stdout: bool) -> None:
    """Export manifest to another dependency format.

    \b
    Supported formats:
        requirements   → requirements.txt
        pyproject      → pyproject.toml dependencies section
        conda          → environment.yml
        docker         → Dockerfile
        pipfile        → Pipfile
        setup          → setup.py

    \b
    Example:
        envcore export
        envcore export -f conda
        envcore export -f docker -o Dockerfile.prod
        envcore export --stdout
    """
    from envcore.export import export, export_to_file
    from envcore.manifest import load

    manifest = load(manifest_path)

    if stdout:
        content = export(manifest, fmt)
        click.echo(content, nl=False)
        return

    click.echo(f"\n  {_header('envcore export')}  {_dim(fmt)}\n")

    dest = export_to_file(manifest, fmt, output)
    click.echo(f"  {_TICK}  Exported {click.style(str(len(manifest.packages)), bold=True)} packages")
    click.echo(f"  {_TICK}  Written to {click.style(str(dest), underline=True)}\n")


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


@cli.command()
@click.argument(
    "manifest_path",
    default="env_manifest.json",
    type=click.Path(exists=True, dir_okay=False),
)
@click.option("--no-outdated", is_flag=True, help="Skip outdated check (faster).")
def doctor(manifest_path: str, no_outdated: bool) -> None:
    """Run environment health checks.

    Checks for: missing packages, version mismatches, orphaned packages,
    outdated dependencies, and manifest staleness.

    \b
    Example:
        envcore doctor
        envcore doctor --no-outdated
    """
    from envcore.doctor import Severity, diagnose

    click.echo(f"\n  {_header('envcore doctor')}  {_dim(manifest_path)}\n")

    report = diagnose(manifest_path, check_outdated=not no_outdated)

    click.echo(f"    Python    {_dim(report.python_version)}")
    click.echo(f"    Packages  {_dim(str(report.manifest_packages))}")
    click.echo()

    _severity_icon = {
        Severity.OK: _TICK,
        Severity.INFO: click.style("ℹ", fg="blue"),
        Severity.WARNING: click.style("⚠", fg="yellow", bold=True),
        Severity.CRITICAL: _CROSS,
    }

    if not report.items:
        click.echo(f"    {_TICK}  {click.style('All clear!', fg='green', bold=True)}\n")
        return

    for item in report.items:
        icon = _severity_icon.get(item.severity, "?")
        cat = _dim(f"[{item.category}]")
        click.echo(f"    {icon}  {_pkg(item.package, '')} {item.message}  {cat}")

    click.echo()

    summary_parts = []
    if report.critical_count:
        summary_parts.append(click.style(f"{report.critical_count} critical", fg="red", bold=True))
    if report.warning_count:
        summary_parts.append(click.style(f"{report.warning_count} warnings", fg="yellow"))

    if summary_parts:
        click.echo(f"    {' · '.join(summary_parts)}\n")

    if not report.is_healthy:
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# clean
# ---------------------------------------------------------------------------


@cli.command()
@click.argument(
    "manifest_path",
    default="env_manifest.json",
    type=click.Path(exists=True, dir_okay=False),
)
@click.option("--dry-run", is_flag=True, help="Preview what would be removed.")
@click.option("--confirm", is_flag=True, help="Actually uninstall orphan packages.")
def clean(manifest_path: str, dry_run: bool, confirm: bool) -> None:
    """Remove installed packages not in the manifest.

    By default, shows what would be removed. Use --confirm to actually
    uninstall, or --dry-run for explicit preview mode.

    \b
    Example:
        envcore clean               # preview
        envcore clean --confirm     # actually uninstall
        envcore clean --dry-run     # explicit preview
    """
    from envcore.clean import clean as do_clean, find_orphans

    click.echo(f"\n  {_header('envcore clean')}  {_dim(manifest_path)}\n")

    orphans = find_orphans(manifest_path)

    if not orphans:
        click.echo(f"    {_TICK}  {click.style('Environment is clean!', fg='green', bold=True)}")
        click.echo(f"    {_dim('No orphan packages found.')}\n")
        return

    click.echo(f"    {click.style(str(len(orphans)), bold=True)} orphan packages:\n")
    for name, version in orphans:
        click.echo(f"      {_MINUS}  {_pkg(name, version)}")
    click.echo()

    if not confirm or dry_run:
        click.echo(f"    {_dim('Run with --confirm to uninstall.')}\n")
        return

    click.echo(f"    Uninstalling...\n")
    results = do_clean(manifest_path)

    succeeded = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)

    for r in results:
        if r.success:
            click.echo(f"      {_TICK}  {_pkg(r.package, r.version)}")
        else:
            click.echo(f"      {_CROSS}  {_pkg(r.package, r.version)}  {_dim(r.message)}")

    click.echo(f"\n    {_TICK}  {succeeded} removed", nl=False)
    if failed:
        click.echo(f"  {_CROSS}  {failed} failed", nl=False)
    click.echo("\n")


# ---------------------------------------------------------------------------
# watch
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("script", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "-o", "--output",
    default="env_manifest.json",
    show_default=True,
    help="Output manifest path.",
)
@click.option(
    "--interval",
    default=2.0,
    show_default=True,
    help="Seconds between manifest updates.",
)
def watch(script: str, output: str, interval: float) -> None:
    """Run SCRIPT with live import tracing.

    Like ``trace``, but updates the manifest continuously while the
    script runs.  Useful for long-running servers and REPL sessions.

    \b
    Example:
        envcore watch server.py
        envcore watch train.py --interval 5
    """
    from envcore.watch import watch as do_watch

    click.echo(f"\n  {_header('envcore watch')}  {_dim(script)}\n")

    def on_update(name: str, version: str) -> None:
        click.echo(f"    {_PLUS}  {_pkg(name, version)}")

    packages = do_watch(script, output, interval=interval, on_update=on_update)

    click.echo()
    if packages:
        click.echo(f"  {_TICK}  Traced {click.style(str(len(packages)), bold=True)} packages")
        click.echo(f"  {_TICK}  Manifest saved to {click.style(output, underline=True)}\n")
    else:
        click.echo(f"  {_dim('No third-party imports detected.')}\n")


# ---------------------------------------------------------------------------
# minimize
# ---------------------------------------------------------------------------


@cli.command()
@click.argument(
    "manifest_path",
    default="env_manifest.json",
    type=click.Path(exists=True, dir_okay=False),
)
def minimize(manifest_path: str) -> None:
    """Find the minimal set of top-level packages to install.

    Analyzes the manifest and separates top-level imports from
    transitive dependencies.  Shows the shortest ``pip install``
    command that would reproduce the full environment.

    \b
    Example:
        envcore minimize
        envcore minimize custom_manifest.json
    """
    from envcore.minimize import minimize as do_minimize

    click.echo(f"\n  {_header('envcore minimize')}  {_dim(manifest_path)}\n")

    result = do_minimize(manifest_path)

    if not result.top_level and not result.transitive:
        click.echo(f"    {_dim('Manifest is empty.')}\n")
        return

    click.echo(f"    {click.style(str(result.total), bold=True)} packages traced {_ARROW} {click.style(str(len(result.top_level)), bold=True, fg='green')} top-level installs\n")

    click.echo(f"    {_header('Top-level')} {_dim('(install these)')}\n")
    for name, version in sorted(result.top_level.items()):
        click.echo(f"      {_ARROW}  {_pkg(name, version)}")

    if result.transitive:
        click.echo(f"\n    {_dim('Transitive')} {_dim('(auto-installed)')}\n")
        for name, version in sorted(result.transitive.items()):
            click.echo(f"      {_dim('·')}  {_pkg(name, version)}")

    click.echo(f"\n    {_header('Minimal install command:')}")
    click.echo(f"    {click.style(result.install_command, fg='green')}\n")


# ---------------------------------------------------------------------------
# lock
# ---------------------------------------------------------------------------


@cli.command()
@click.argument(
    "manifest_path",
    default="env_manifest.json",
    type=click.Path(exists=True, dir_okay=False),
)
@click.option("-o", "--output", default="env_manifest.lock", show_default=True,
              help="Output lockfile path.")
def lock(manifest_path: str, output: str) -> None:
    """Generate a lockfile with dependency hashes.

    Goes beyond the manifest by recording SHA-256 hashes for each
    package, enabling supply-chain integrity verification.

    \b
    Example:
        envcore lock
        envcore lock -o production.lock
    """
    from envcore.lock import generate_lockfile, verify_lockfile
    from envcore.manifest import load

    click.echo(f"\n  {_header('envcore lock')}  {_dim(manifest_path)}\n")

    manifest = load(manifest_path)
    dest = generate_lockfile(manifest_path, output)

    click.echo(f"  {_TICK}  Locked {click.style(str(len(manifest.packages)), bold=True)} packages with integrity hashes")
    click.echo(f"  {_TICK}  Lockfile saved to {click.style(str(dest), underline=True)}\n")


# ---------------------------------------------------------------------------
# graph
# ---------------------------------------------------------------------------


@cli.command("graph")
@click.argument(
    "manifest_path",
    default="env_manifest.json",
    type=click.Path(exists=True, dir_okay=False),
)
@click.option(
    "-f", "--format", "fmt",
    type=click.Choice(["tree", "mermaid", "dot"], case_sensitive=False),
    default="tree",
    show_default=True,
    help="Output format.",
)
def graph_cmd(manifest_path: str, fmt: str) -> None:
    """Visualise the dependency graph.

    \b
    Formats:
        tree     — ASCII tree in terminal
        mermaid  — Mermaid diagram (for docs/GitHub)
        dot      — Graphviz DOT (pipe to dot -Tpng)

    \b
    Example:
        envcore graph
        envcore graph -f mermaid
        envcore graph -f dot | dot -Tpng -o deps.png
    """
    from envcore.graph import graph

    if fmt != "tree":
        # For machine-readable formats, output raw
        click.echo(graph(manifest_path, fmt))
        return

    click.echo(f"\n  {_header('envcore graph')}  {_dim(manifest_path)}\n")
    output = graph(manifest_path, fmt)
    for line in output.split("\n"):
        click.echo(f"    {line}")
    click.echo()


# ---------------------------------------------------------------------------
# ci
# ---------------------------------------------------------------------------


@cli.command()
@click.argument(
    "manifest_path",
    default="env_manifest.json",
    type=click.Path(exists=True, dir_okay=False),
)
def ci(manifest_path: str) -> None:
    """Verify environment matches manifest (for CI/CD).

    Exits with code 0 if all packages match, code 1 if there are
    any missing or mismatched packages.  Designed for CI pipelines.

    \b
    Example:
        envcore ci                    # check env_manifest.json
        envcore ci production.json    # check custom manifest
    """
    from envcore.ci import check

    click.echo(f"\n  {_header('envcore ci')}  {_dim(manifest_path)}\n")

    result = check(manifest_path)

    if result.ok:
        click.echo(f"    {_TICK}  {click.style('All packages match manifest!', fg='green', bold=True)}\n")
        return

    if result.missing:
        click.echo(f"    {click.style('Missing:', fg='red', bold=True)}")
        for name in result.missing:
            click.echo(f"      {_CROSS}  {click.style(name, bold=True)}")

    if result.mismatched:
        click.echo(f"    {click.style('Mismatched:', fg='yellow', bold=True)}")
        for name, expected, actual in result.mismatched:
            click.echo(f"      {_DELTA}  {click.style(name, bold=True)}  {_dim(expected)} {_ARROW} {_dim(actual)}")

    click.echo(f"\n    {_dim(result.summary)}\n")
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# hooks
# ---------------------------------------------------------------------------


@cli.group()
def hooks() -> None:
    """Manage git hooks for envcore."""


@hooks.command("install")
def hooks_install() -> None:
    """Install the envcore pre-commit hook.

    \b
    Example:
        envcore hooks install
    """
    from envcore.hooks import install_hooks

    click.echo(f"\n  {_header('envcore hooks install')}\n")

    try:
        path = install_hooks()
        click.echo(f"  {_TICK}  Pre-commit hook installed at {click.style(str(path), underline=True)}\n")
    except FileNotFoundError as e:
        click.echo(f"  {_CROSS}  {e}\n")
        raise SystemExit(1)


@hooks.command("uninstall")
def hooks_uninstall() -> None:
    """Remove the envcore pre-commit hook.

    \b
    Example:
        envcore hooks uninstall
    """
    from envcore.hooks import uninstall_hooks

    click.echo(f"\n  {_header('envcore hooks uninstall')}\n")

    if uninstall_hooks():
        click.echo(f"  {_TICK}  Pre-commit hook removed.\n")
    else:
        click.echo(f"  {_dim('No envcore hook found.')}\n")


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--since", default=None, help="Filter: only show entries after this ISO date.")
@click.option("--save", is_flag=True, help="Save current manifest to history first.")
def history(since: str | None, save: bool) -> None:
    """Show manifest version history.

    Tracks changes to your manifest over time.  Use --save to record
    the current manifest as a snapshot before viewing history.

    \b
    Example:
        envcore history --save        # snapshot + show history
        envcore history               # show existing history
        envcore history --since 2026-01-01
    """
    from envcore.history import list_history, save_snapshot

    click.echo(f"\n  {_header('envcore history')}\n")

    if save:
        try:
            dest = save_snapshot()
            click.echo(f"  {_TICK}  Snapshot saved to {click.style(str(dest), underline=True)}\n")
        except FileNotFoundError as e:
            click.echo(f"  {_CROSS}  {e}\n")

    entries = list_history(since=since)

    if not entries:
        click.echo(f"    {_dim('No history entries found.')}")
        click.echo(f"    {_dim('Use --save to record a snapshot.')}\n")
        return

    for entry in entries:
        ts_short = entry.timestamp[:10] if len(entry.timestamp) >= 10 else entry.timestamp
        click.echo(f"    {_dim(ts_short)}  {entry.summary}  {_dim(entry.filename)}")

    click.echo()


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------


@cli.command()
@click.argument(
    "manifest_path",
    default="env_manifest.json",
    type=click.Path(exists=True, dir_okay=False),
)
@click.option(
    "-t", "--target", default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="Target file (auto-detects requirements.txt / pyproject.toml).",
)
@click.option("--apply", "do_apply", is_flag=True,
              help="Overwrite the target file with manifest contents.")
def sync(manifest_path: str, target: str | None, do_apply: bool) -> None:
    """Sync manifest with requirements.txt / pyproject.toml.

    Compares the manifest against your project's dependency file
    and shows what's different.  Use --apply to overwrite.

    \\b
    Example:
        envcore sync                 # auto-detect and diff
        envcore sync -t req.txt      # diff against specific file
        envcore sync --apply         # overwrite requirements.txt
    """
    from envcore.sync import diff_sync, apply_to_requirements

    click.echo(f"\n  {_header('envcore sync')}  {_dim(manifest_path)}\n")

    if do_apply:
        from envcore.sync import apply_to_requirements
        dest = apply_to_requirements(manifest_path, target or "requirements.txt")
        click.echo(f"  {_TICK}  Manifest written to {_style(str(dest), underline=True)}\n")
        return

    result = diff_sync(manifest_path, target)

    if result is None:
        click.echo(f"  {_dim('No dependency file found (requirements.txt / pyproject.toml).')}\n")
        return

    click.echo(f"    Comparing: {_dim(result.target_file)}\n")

    if result.in_sync:
        click.echo(f"  {_TICK}  {_style('Fully in sync!', fg='green', bold=True)}\n")
        return

    if result.missing_in_target:
        click.echo(f"    {_style('In manifest, missing in target:', bold=True)}")
        for name, ver in sorted(result.missing_in_target.items()):
            click.echo(f"      {_PLUS}  {_pkg(name, ver)}")

    if result.missing_in_manifest:
        click.echo(f"    {_style('In target, missing in manifest:', bold=True)}")
        for name, ver in sorted(result.missing_in_manifest.items()):
            click.echo(f"      {_MINUS}  {_pkg(name, ver)}")

    if result.version_mismatch:
        click.echo(f"    {_style('Version mismatches:', bold=True)}")
        for name, (m_ver, t_ver) in sorted(result.version_mismatch.items()):
            click.echo(f"      {_DELTA}  {_style(name, bold=True)}  manifest={_dim(m_ver)} target={_dim(t_ver)}")

    click.echo()


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------


@cli.command("audit")
@click.argument(
    "manifest_path",
    default="env_manifest.json",
    type=click.Path(exists=True, dir_okay=False),
)
def audit_cmd(manifest_path: str) -> None:
    """Scan packages for known security vulnerabilities.

    Uses the free OSV.dev database — no API key required.
    Checks each package in the manifest against known CVEs.

    \\b
    Example:
        envcore audit
        envcore audit production.json
    """
    from envcore.audit import audit

    click.echo(f"\n  {_header('envcore audit')}  {_dim(manifest_path)}\n")
    click.echo(f"  {_dim('Scanning packages against OSV.dev...')}\n")

    report = audit(manifest_path)

    click.echo(f"    Checked {_style(str(report.packages_checked), bold=True)} packages\n")

    if report.is_clean:
        click.echo(f"  {_TICK}  {_style('No known vulnerabilities found!', fg='green', bold=True)}\n")
        return

    for vuln in report.vulnerabilities:
        severity_colors = {
            "CRITICAL": "red", "HIGH": "red",
            "MODERATE": "yellow", "LOW": "bright_black",
        }
        color = severity_colors.get(vuln.severity, "yellow")
        click.echo(f"    {_style(vuln.severity, fg=color, bold=True)}  "
                    f"{_style(vuln.package, bold=True)}  {vuln.id}")
        click.echo(f"      {_dim(vuln.summary[:100])}")
        if vuln.url:
            click.echo(f"      {_dim(vuln.url)}")
        click.echo()

    click.echo(f"  {_CROSS}  {_style(str(len(report.vulnerabilities)), bold=True)} "
               f"vulnerabilities found ({report.critical_count} critical/high)\n")
    if report.critical_count > 0:
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# notebook
# ---------------------------------------------------------------------------


@cli.command()
@click.argument(
    "notebook_path",
    type=click.Path(exists=True, dir_okay=False),
)
@click.option("-o", "--output", default="env_manifest.json", show_default=True,
              help="Output manifest path.")
@click.option("--static", is_flag=True,
              help="Static analysis only — don't execute the notebook.")
def notebook(notebook_path: str, output: str, static: bool) -> None:
    """Trace imports from a Jupyter notebook.

    Extracts and executes code cells to capture runtime imports.
    Use --static for import detection without execution.

    \\b
    Example:
        envcore notebook analysis.ipynb
        envcore notebook train.ipynb --static
    """
    from envcore.notebook import trace_notebook, _extract_imports_static

    click.echo(f"\n  {_header('envcore notebook')}  {_dim(notebook_path)}\n")

    if static:
        imports = _extract_imports_static(notebook_path)
        click.echo(f"  {_TICK}  Found {_style(str(len(imports)), bold=True)} import statements (static):\n")
        for name in imports:
            click.echo(f"    {_ARROW}  {_style(name, bold=True)}")
        click.echo()
        return

    packages, dest = trace_notebook(notebook_path, output)

    if not packages:
        click.echo(f"  {_dim('No third-party imports detected.')}")
        click.echo(f"  {_TICK}  Empty manifest saved to {_style(str(dest), underline=True)}\n")
        return

    click.echo(f"  {_TICK}  Traced {_style(str(len(packages)), bold=True)} packages:\n")
    for name, version in sorted(packages.items()):
        click.echo(f"    {_ARROW}  {_pkg(name, version)}")
    click.echo(f"\n  {_TICK}  Manifest saved to {_style(str(dest), underline=True)}\n")
