<p align="center">
  <h1 align="center">Envcore</h1>
  <p align="center">
    <strong>Runtime import tracing for Python. Know exactly what your code needs.</strong><br>
    Trace &middot; Snapshot &middot; Restore &middot; Audit
  </p>
  <p align="center">
    <a href="https://pypi.org/project/envcore/"><img alt="PyPI" src="https://img.shields.io/pypi/v/envcore?color=blue&style=flat-square"></a>
    <a href="https://github.com/JanBremec/envcore/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/JanBremec/envcore?style=flat-square"></a>
    <a href="https://www.python.org/"><img alt="Python" src="https://img.shields.io/pypi/pyversions/envcore?style=flat-square"></a>
    <a href="https://github.com/JanBremec/envcore/actions"><img alt="CI" src="https://github.com/JanBremec/envcore/actions/workflows/ci.yml/badge.svg"></a>
  </p>
</p>

---

## Why Envcore

`pip freeze` dumps your entire environment — 200+ packages, most of which your code never touches. Static analysers like `pipreqs` scan source files but miss dynamic imports, conditional imports, and anything loaded at runtime.

Envcore takes a different approach: it **hooks into Python's import system while your code runs**, records only the packages that are actually imported, resolves them to their PyPI names and pinned versions, and writes a deterministic manifest. One command rebuilds that exact environment anywhere.

```
Trace  →  env_manifest.json  →  Restore
```

No configuration files to maintain. No guesswork.

---

## Install

```bash
pip install envcore
```

Development setup:

```bash
git clone https://github.com/JanBremec/envcore.git
cd envcore
pip install -e ".[dev]"
```

Requires Python 3.9+.

---

## Quick Start

**Trace** your script to capture its runtime dependencies:

```bash
envcore trace train.py
```

```
  envcore trace  train.py

    Traced 3 packages:

      numpy 1.26.4
      pandas 2.1.4
      torch 2.1.0

    Manifest saved to env_manifest.json
```

**Restore** the environment on any machine:

```bash
envcore restore
```

That is all you need. The manifest ships with your code, and `envcore restore` installs exactly what was traced — nothing more.

---

## Commands

| Command | What it does |
|---|---|
| `envcore trace <script>` | Run a script with import tracing, save manifest |
| `envcore watch <script>` | Live import tracing with real-time manifest updates |
| `envcore notebook <.ipynb>` | Trace imports from a Jupyter notebook |
| `envcore snapshot` | Save imports from programmatic tracking to manifest |
| `envcore restore` | Install all packages from manifest |
| `envcore show` | Pretty-print manifest contents |
| `envcore diff <a> <b>` | Compare two manifests |
| `envcore export` | Export to requirements.txt, conda, Docker, and more |
| `envcore sync` | Diff manifest against requirements.txt or pyproject.toml |
| `envcore doctor` | Environment health check: missing, outdated, orphans |
| `envcore clean` | Remove packages not tracked in manifest |
| `envcore minimize` | Find the minimal top-level install set |
| `envcore lock` | Generate lockfile with SHA-256 hashes |
| `envcore graph` | Dependency graph (ASCII tree, Mermaid, Graphviz DOT) |
| `envcore audit` | Scan for known vulnerabilities via OSV.dev |
| `envcore ci` | Verify environment matches manifest (exit 0 or 1) |
| `envcore hooks install` | Install git pre-commit hook |
| `envcore history` | Manifest version history and snapshots |
| `envcore init` | Create a blank manifest |

Every command supports `--help`. Set `NO_COLOR=1` to disable coloured output.

---

## Export Formats

```bash
envcore export -f requirements   # requirements.txt
envcore export -f pyproject      # pyproject.toml [project.dependencies]
envcore export -f conda          # environment.yml
envcore export -f docker         # Dockerfile with pinned installs
envcore export -f pipfile        # Pipfile
envcore export -f setup          # setup.py
```

---

## Health Check

```bash
envcore doctor
```

```
  Python    3.11.5
  Packages  18

    torch       required 2.1.0, not installed       [missing]
    numpy       manifest 1.25.0 != installed 1.26.4 [mismatch]
    flask       3.0.0 -> 3.1.0 available            [outdated]
    requests    installed 2.31.0, not in manifest    [orphan]

  1 critical, 2 warnings
```

Detects missing packages, version mismatches, orphaned installs, outdated dependencies, and stale manifests.

---

## Minimize

Reduce a traced environment to its minimal top-level install set:

```bash
envcore minimize
```

```
  18 packages traced -> 3 top-level installs

  Top-level
    numpy 1.26.4
    pandas 2.1.3
    scikit-learn 1.3.2

  Transitive (auto-installed)
    scipy 1.11.3
    joblib 1.2.0
    threadpoolctl 3.2.0

  Minimal install command:
  pip install numpy==1.26.4 pandas==2.1.3 scikit-learn==1.3.2
```

---

## Security

```bash
envcore lock    # Lockfile with SHA-256 integrity hashes
envcore audit   # Scan packages against OSV.dev vulnerability database
```

---

## Dependency Graph

```bash
envcore graph              # ASCII tree
envcore graph -f mermaid   # Mermaid (renders in GitHub READMEs)
envcore graph -f dot       # Graphviz DOT
```

```
  pandas 2.1.3
  +-- numpy 1.26.4
  +-- python-dateutil 2.8.2
  scikit-learn 1.3.2
  +-- joblib 1.2.0
  +-- numpy 1.26.4
  +-- scipy 1.11.3
  +-- threadpoolctl 3.2.0
```

---

## CI/CD and Git Hooks

```bash
envcore ci              # Exit 0 if environment matches, 1 otherwise
envcore hooks install   # Pre-commit hook: auto-check manifest on commit
envcore sync            # Diff manifest vs requirements.txt
envcore sync --apply    # Overwrite requirements.txt from manifest
```

---

## Jupyter Notebooks

```bash
envcore notebook analysis.ipynb            # Trace imports at runtime
envcore notebook analysis.ipynb --static   # Static analysis only
```

Inside IPython or Jupyter:

```python
%load_ext envcore
%envcore start
import numpy, pandas
%envcore snapshot
```

---

## Programmatic API

```python
import envcore

envcore.start_tracking()

import numpy
import pandas
from sklearn.model_selection import train_test_split

envcore.stop_tracking()
envcore.snapshot("env_manifest.json")
```

Context manager:

```python
from envcore import ImportTracer

tracer = ImportTracer()
with tracer:
    import numpy
    import pandas

print(tracer.module_names)  # ['numpy', 'pandas']
```

Decorator:

```python
from envcore import ImportTracer

tracer = ImportTracer()

@tracer
def train():
    import torch
    import wandb

train()
print(tracer.module_names)  # ['torch', 'wandb']
```

---

## How It Works

```
1. TRACE
   builtins.__import__  -->  ImportTracer hook
   Records: module name, timestamp, order
   Filters: stdlib, pre-existing modules

2. RESOLVE
   import name  -->  PyPI package + version
   "PIL"        -->  Pillow 10.2.0
   "cv2"        -->  opencv-python 4.9.0
   "sklearn"    -->  scikit-learn 1.4.0

3. SNAPSHOT
   env_manifest.json
   { "numpy": "1.26.4", "torch": "2.1.0", ... }

4. RESTORE
   pip install numpy==1.26.4 torch==2.1.0 ...
```

By tracing at runtime, Envcore captures dynamic imports, conditional imports, and imports inside functions — things static analysis tools miss entirely.

---

## Configuration

Project-level settings in `pyproject.toml`:

```toml
[tool.envcore]
manifest = "env_manifest.json"
exclude = ["setuptools", "pip", "wheel"]
entry_points = ["src/main.py", "src/api.py"]
auto_export = "requirements.txt"
```

---

## Comparison

| Feature | Envcore | pipreqs | pip freeze |
|---|---|---|---|
| Detection method | **Runtime tracing** | Static analysis | Environment dump |
| Dynamic imports | Yes | No | N/A |
| Conditional imports | Yes | No | N/A |
| Filters stdlib | Yes | Yes | No |
| Filters unused packages | Yes | Yes | No |
| Import alias handling | Yes | Partial | Yes |
| One-command restore | Yes | No | No |
| Export (6 formats) | Yes | No | No |
| Health check | Yes | No | No |
| Dependency minimization | Yes | No | No |
| Lockfile with hashes | Yes | No | No |
| Dependency graph | Yes | No | No |
| Vulnerability scanning | Yes | No | No |
| Jupyter support | Yes | No | No |
| CI/CD integration | Yes | No | No |
| Git hooks | Yes | No | No |

---

## Contributing

Contributions welcome. Please open an issue or pull request.

```bash
git clone https://github.com/JanBremec/envcore.git
cd envcore
pip install -e ".[dev]"
pytest tests/ -v
```

---

## License

[MIT](LICENSE) — Jan Bremec
