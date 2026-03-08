# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-03-07

### Added

**Core**
- Runtime import tracer with `builtins.__import__` hook
- PyPI package resolver with alias table (PIL→Pillow, cv2→opencv-python, etc.)
- JSON manifest format (`env_manifest.json`) with metadata
- Manifest diff engine

**CLI Commands (16 total)**
- `envcore trace <script>` — run a script with import tracing
- `envcore watch <script>` — live import tracing with real-time updates
- `envcore snapshot` — save programmatic tracking to manifest
- `envcore restore` — reinstall environment from manifest
- `envcore show` — pretty-print manifest
- `envcore diff` — compare two manifests
- `envcore init` — create blank manifest
- `envcore export` — export to 6 formats (requirements.txt, pyproject.toml, conda, Docker, Pipfile, setup.py)
- `envcore doctor` — environment health check (missing, mismatched, orphan, outdated, staleness)
- `envcore clean` — remove packages not in manifest
- `envcore minimize` — find minimal top-level install set
- `envcore lock` — generate lockfile with SHA-256 hashes
- `envcore graph` — dependency tree visualisation (ASCII, Mermaid, Graphviz DOT)
- `envcore ci` — CI/CD environment verification gate
- `envcore hooks install/uninstall` — git pre-commit hooks
- `envcore history` — manifest version tracking

**Infrastructure**
- `NO_COLOR` environment variable support
- `[tool.envcore]` configuration in pyproject.toml
- GitHub Actions CI with Python 3.9–3.13 test matrix
- 70+ test cases
