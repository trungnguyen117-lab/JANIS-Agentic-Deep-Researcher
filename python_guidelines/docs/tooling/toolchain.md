# Toolchain

- Linters/Formatters: `ruff` (lint+fmt) or `ruff` + `black`.
- Types: `pyright` (recommended) or `mypy`; enforce in CI.
- Tests: `pytest`, `pytest-asyncio` when needed.
- Packaging/environments: `uv` or `hatch` for fast, isolated envs.
- Enforce via pre-commit and CI; pin versions to keep reproducibility.

### Example pre-commit snippet
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.8
    hooks:
      - id: ruff
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.2
    hooks:
      - id: mypy
```

