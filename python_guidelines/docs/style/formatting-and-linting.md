# Formatting & Linting

- Use `ruff` for lint + format (or `black` for formatting if preferred). Enforce via pre-commit and CI.
- Keep line length reasonable (PEP8 baseline); let the formatter decide layout to avoid churn.
- Avoid disabling lint rules unless you must; justify `# noqa`/`# type: ignore`.

### PEP8 basics
- Indent with 4 spaces; avoid tabs.
- Keep lines ≤ 79–99 chars (pick and enforce consistently).
- Surround operators and commas with spaces; no trailing whitespace.

