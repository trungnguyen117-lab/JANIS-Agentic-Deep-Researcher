# uv & pyproject.toml

## Why uv
- Fast installs and builds; good for CI/CD speed.
- Manages virtual environments automatically.
- Works directly with `pyproject.toml` for dependencies/metadata.

## pyproject.toml usage
- Declare project metadata and dependencies in one place.
```toml
[project]
name = "my-app"
version = "0.1.0"
description = "My app"
requires-python = ">=3.11"
dependencies = [
  "fastapi",
  "uvicorn[standard]",
]

[tool.uv]
dev-dependencies = [
  "pytest",
  "ruff",
  "pyright",
]
```
- Prefer `dev-dependencies` (or equivalent) to separate runtime vs dev tools.
- Avoid `requirements.txt` duplication; let `uv` export if needed (`uv pip compile` or `uv export`).

## Common commands
- Sync env + deps from `pyproject.toml`: `uv sync` (creates venv if missing)
- Add a dep: `uv add requests`
- Add a dev dep: `uv add --dev pytest`
- Run with managed env: `uv run python -m app` or `uv run pytest`

## Best practices
- Pin Python version in `requires-python`; pin critical libs when needed.
- Commit `pyproject.toml` and `uv.lock` (if generated) for reproducibility.
- In CI, use `uv sync` for deterministic installs (no manual venv setup needed).
- Keep scripts in `[tool.uv.scripts]` or use `make`/`just` to wrap common tasks.
- For containers, use `uv` to build wheels in a builder stage, then copy into a slim runtime.

## Exporting
- If consumers need `requirements.txt`: `uv export --format requirements > requirements.txt`

