# envcore

**`pip freeze` done right — only what your code actually uses.**

[![PyPI](https://img.shields.io/pypi/v/envcore?color=blue&style=flat-square)](https://pypi.org/project/envcore/)
[![Python](https://img.shields.io/pypi/pyversions/envcore?style=flat-square)](https://www.python.org/)
[![License](https://img.shields.io/github/license/JanBremec/envcore?style=flat-square)](https://github.com/JanBremec/envcore/blob/main/LICENSE)
[![CI](https://github.com/JanBremec/envcore/actions/workflows/ci.yml/badge.svg)](https://github.com/JanBremec/envcore/actions)

---

`pip freeze` dumps your entire environment — often 200+ packages — most of which your project never touches. `pipreqs` scans source files but misses dynamic imports, conditional imports, and anything loaded at runtime.

Envcore hooks into Python's import system **while your code actually runs**, records only what gets imported, and writes a clean manifest. One command rebuilds that exact environment anywhere.

```
envcore trace train.py   →   env_manifest.json   →   envcore restore
```

No config files to maintain. No guesswork. Ship the manifest with your code.

---

## Install

```bash
pip install envcore
```

Requires Python 3.9+.

---

## Usage

**Trace** your script:

```bash
envcore trace train.py
```

```
  Traced 3 packages:

    numpy       1.26.4
    pandas      2.1.4
    torch       2.1.0

  Manifest saved → env_manifest.json
```

**Restore** anywhere:

```bash
envcore restore
```

That's it. The manifest contains only what was actually imported — nothing more.

---

## Why runtime tracing?

Static tools read your source files. They miss:

- `import torch` inside an `if cuda_available:` block
- imports inside functions, called only at runtime
- dynamic `importlib.import_module(...)` calls
- packages imported by your dependencies on your behalf

Envcore catches all of these because it watches what Python actually loads, not what it might load.

> **Note:** Envcore traces one execution. If your code has branches that aren't hit during tracing (e.g. a `prod`-only import), those won't be captured. Trace against a representative run.

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

with ImportTracer() as tracer:
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

## Jupyter Notebooks

```bash
envcore notebook analysis.ipynb
```

Or inside a running notebook:

```python
%load_ext envcore
%envcore start
import numpy, pandas
%envcore snapshot
```

---

## How it works

```
1. TRACE    builtins.__import__ → ImportTracer hook
            Records module name, filters stdlib and pre-existing packages

2. RESOLVE  import name → PyPI package + pinned version
            "PIL" → Pillow 10.2.0
            "cv2" → opencv-python 4.9.0
            "sklearn" → scikit-learn 1.4.0

3. MANIFEST env_manifest.json
            { "numpy": "1.26.4", "torch": "2.1.0", ... }

4. RESTORE  pip install numpy==1.26.4 torch==2.1.0 ...
```

---

## Other commands

| Command | What it does |
|---|---|
| `envcore trace <script>` | Trace a script, save manifest |
| `envcore restore` | Install packages from manifest |
| `envcore show` | Print manifest contents |
| `envcore diff <a> <b>` | Compare two manifests |
| `envcore export -f <format>` | Export to `requirements.txt`, `pyproject.toml`, `conda`, `docker`, `pipfile`, `setup.py` |
| `envcore sync` | Diff manifest vs existing `requirements.txt` |
| `envcore doctor` | Check for missing, outdated, or orphaned packages |
| `envcore minimize` | Find the minimal top-level install set |
| `envcore lock` | Generate lockfile with SHA-256 hashes |
| `envcore audit` | Scan for vulnerabilities via OSV.dev |
| `envcore ci` | Exit 0/1 based on whether environment matches manifest |

Every command supports `--help`. Set `NO_COLOR=1` to disable colour output.

---

## Configuration

```toml
# pyproject.toml
[tool.envcore]
manifest = "env_manifest.json"
exclude = ["setuptools", "pip", "wheel"]
entry_points = ["src/main.py"]
auto_export = "requirements.txt"
```

---

## Contributing

```bash
git clone https://github.com/JanBremec/envcore.git
cd envcore
pip install -e ".[dev]"
pytest tests/ -v
```

Issues and PRs welcome.

---

## License

[MIT](./LICENSE) — Jan Bremec
