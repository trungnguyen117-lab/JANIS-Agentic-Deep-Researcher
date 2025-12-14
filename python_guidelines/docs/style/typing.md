# Typing

- Use type hints everywhere; prefer precise types over `Any`.
- Run a type checker (`pyright` recommended; `mypy` acceptable) in CI and locally.
- Use TypedDict/Protocol when interfaces matter; avoid leaking `dict[str, Any]` in APIs unless necessary.

