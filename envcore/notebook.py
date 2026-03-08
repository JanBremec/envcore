"""
Jupyter notebook integration for envcore.

Provides:
- IPython magic commands (%load_ext envcore, %envcore snapshot)
- CLI command to trace a notebook's cell contents
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from envcore.manifest import DEFAULT_MANIFEST_PATH, Manifest, save
from envcore.resolver import resolve_many
from envcore.tracer import ImportTracer


def trace_notebook(
    notebook_path: str | Path,
    output: str | Path = DEFAULT_MANIFEST_PATH,
) -> tuple[dict[str, str], Path]:
    """Trace all imports from a Jupyter notebook's code cells.

    Reads the ``.ipynb`` file, extracts Python code from code cells,
    executes them with import tracing, and saves a manifest.

    Parameters
    ----------
    notebook_path:
        Path to the ``.ipynb`` file.
    output:
        Output manifest path.

    Returns
    -------
    tuple[dict[str, str], Path]
        Packages dict and the path to the saved manifest.
    """
    nb_path = Path(notebook_path)
    if not nb_path.exists():
        raise FileNotFoundError(f"Notebook not found: {nb_path}")

    nb = json.loads(nb_path.read_text())
    cells = nb.get("cells", [])

    # Extract source code from code cells
    code_lines: list[str] = []
    for cell in cells:
        if cell.get("cell_type") != "code":
            continue
        source = cell.get("source", [])
        if isinstance(source, list):
            code_lines.extend(source)
        else:
            code_lines.append(source)

    full_code = "\n".join(code_lines)

    # Remove IPython magics and shell commands that would fail
    clean_lines = []
    for line in full_code.splitlines():
        stripped = line.strip()
        if stripped.startswith(("%", "!", "?")):
            continue
        # Also skip display() and other IPython-specific calls
        clean_lines.append(line)

    clean_code = "\n".join(clean_lines)

    # Trace the combined code
    tracer = ImportTracer()
    tracer.start()

    try:
        exec(compile(clean_code, str(nb_path), "exec"), {"__name__": "__main__"})
    except Exception:
        pass  # We still want partial results
    finally:
        tracer.stop()

    imports = tracer.imports
    resolved = resolve_many(list(imports.keys()))

    packages = {r.package_name: r.version for r in resolved.values()}
    manifest = Manifest(packages=packages)
    dest = save(manifest, output)

    return packages, dest


def _extract_imports_static(notebook_path: str | Path) -> list[str]:
    """Statically extract import names from a notebook (no execution).

    Useful as a fallback when execution isn't possible.
    """
    nb_path = Path(notebook_path)
    nb = json.loads(nb_path.read_text())

    import_names: set[str] = set()
    import_re = re.compile(
        r"^\s*(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_]*)"
    )

    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        source = cell.get("source", [])
        if isinstance(source, list):
            lines = source
        else:
            lines = source.splitlines()

        for line in lines:
            match = import_re.match(line)
            if match:
                import_names.add(match.group(1))

    return sorted(import_names)


# ---------------------------------------------------------------------------
# IPython magic (only loaded when IPython is available)
# ---------------------------------------------------------------------------


def _register_magics() -> None:
    """Register envcore magics with IPython."""
    try:
        from IPython.core.magic import register_line_magic
        from IPython import get_ipython
    except ImportError:
        return

    ip = get_ipython()
    if ip is None:
        return

    _tracer = ImportTracer()

    @register_line_magic
    def envcore(line: str) -> None:
        """Envcore magic: %envcore start | stop | snapshot | status"""
        parts = line.strip().split()
        cmd = parts[0] if parts else "status"

        if cmd == "start":
            if not _tracer.is_active:
                _tracer.start()
                print("✔ envcore tracing started")
            else:
                print("⚠ Already tracing")

        elif cmd == "stop":
            if _tracer.is_active:
                _tracer.stop()
                print(f"✔ Tracing stopped — {len(_tracer.module_names)} imports captured")
            else:
                print("⚠ Not currently tracing")

        elif cmd == "snapshot":
            if _tracer.is_active:
                _tracer.stop()
            imports = _tracer.imports
            resolved = resolve_many(list(imports.keys()))
            packages = {r.package_name: r.version for r in resolved.values()}
            manifest = Manifest(packages=packages)
            out = parts[1] if len(parts) > 1 else DEFAULT_MANIFEST_PATH
            dest = save(manifest, out)
            print(f"✔ {len(packages)} packages saved to {dest}")

        elif cmd == "status":
            if _tracer.is_active:
                print(f"Tracing: {len(_tracer.module_names)} imports so far")
                for name in _tracer.module_names[:10]:
                    print(f"  → {name}")
                if len(_tracer.module_names) > 10:
                    print(f"  ... and {len(_tracer.module_names) - 10} more")
            else:
                print("Not currently tracing. Use %envcore start")

        else:
            print("Usage: %envcore start | stop | snapshot [path] | status")


def load_ipython_extension(ip: Any) -> None:
    """Called by IPython when user runs ``%load_ext envcore``."""
    _register_magics()
    print("✔ envcore extension loaded. Use %envcore start to begin tracing.")
