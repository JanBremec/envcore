"""
Dependency graph visualisation.

Outputs dependency trees in multiple formats:
- ASCII tree (terminal)
- Mermaid diagram
- Graphviz DOT
"""

from __future__ import annotations

import importlib.metadata
from pathlib import Path
from typing import Literal

from envcore.manifest import DEFAULT_MANIFEST_PATH, Manifest, load
from envcore.minimize import _get_requires

GraphFormat = Literal["tree", "mermaid", "dot"]


def _build_tree(manifest: Manifest) -> dict[str, list[str]]:
    """Build adjacency list: package → [dependencies in manifest]."""
    all_names = {n.lower(): n for n in manifest.packages}
    tree: dict[str, list[str]] = {}

    for pkg_name in sorted(manifest.packages):
        deps = _get_requires(pkg_name)
        in_manifest = []
        for dep in sorted(deps):
            actual = all_names.get(dep.lower())
            if actual:
                in_manifest.append(actual)
        tree[pkg_name] = in_manifest

    return tree


def _format_tree(manifest: Manifest, tree: dict[str, list[str]]) -> str:
    """Render as ASCII tree."""
    lines: list[str] = []

    for pkg_name in sorted(tree):
        version = manifest.packages.get(pkg_name, "?")
        deps = tree[pkg_name]
        lines.append(f"{pkg_name} {version}")
        for i, dep in enumerate(deps):
            dep_version = manifest.packages.get(dep, "?")
            is_last = i == len(deps) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{connector}{dep} {dep_version}")

    return "\n".join(lines)


def _format_mermaid(manifest: Manifest, tree: dict[str, list[str]]) -> str:
    """Render as Mermaid flowchart."""
    lines: list[str] = ["graph TD"]

    # Node definitions
    for pkg_name in sorted(tree):
        version = manifest.packages.get(pkg_name, "?")
        safe_id = pkg_name.replace("-", "_").replace(".", "_")
        lines.append(f'    {safe_id}["{pkg_name} {version}"]')

    lines.append("")

    # Edges
    for pkg_name, deps in sorted(tree.items()):
        src_id = pkg_name.replace("-", "_").replace(".", "_")
        for dep in deps:
            dep_id = dep.replace("-", "_").replace(".", "_")
            lines.append(f"    {src_id} --> {dep_id}")

    return "\n".join(lines)


def _format_dot(manifest: Manifest, tree: dict[str, list[str]]) -> str:
    """Render as Graphviz DOT."""
    lines: list[str] = [
        "digraph dependencies {",
        '    rankdir=TB;',
        '    node [shape=box, style="rounded,filled", fillcolor="#e8f0fe", fontname="Inter"];',
        '    edge [color="#666666"];',
        "",
    ]

    for pkg_name in sorted(tree):
        version = manifest.packages.get(pkg_name, "?")
        safe_id = pkg_name.replace("-", "_").replace(".", "_")
        lines.append(f'    {safe_id} [label="{pkg_name}\\n{version}"];')

    lines.append("")

    for pkg_name, deps in sorted(tree.items()):
        src_id = pkg_name.replace("-", "_").replace(".", "_")
        for dep in deps:
            dep_id = dep.replace("-", "_").replace(".", "_")
            lines.append(f"    {src_id} -> {dep_id};")

    lines.append("}")
    return "\n".join(lines)


_FORMATTERS = {
    "tree": _format_tree,
    "mermaid": _format_mermaid,
    "dot": _format_dot,
}


def graph(
    path: str | Path = DEFAULT_MANIFEST_PATH,
    fmt: GraphFormat = "tree",
) -> str:
    """Generate a dependency graph visualisation.

    Parameters
    ----------
    path:
        Path to the manifest file.
    fmt:
        Output format: ``"tree"``, ``"mermaid"``, or ``"dot"``.

    Returns
    -------
    str
        The rendered graph as a string.
    """
    manifest = load(path)
    tree = _build_tree(manifest)
    formatter = _FORMATTERS.get(fmt)
    if formatter is None:
        raise ValueError(f"Unknown format: {fmt!r}. Choose from: {list(_FORMATTERS)}")
    return formatter(manifest, tree)
