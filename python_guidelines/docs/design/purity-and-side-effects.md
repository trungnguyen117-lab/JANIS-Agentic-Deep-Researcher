# Purity & Side Effects

- Avoid mutating globals or arguments unless clearly documented.
- Keep hidden dependencies out of functions; pass what you need explicitly.
- Logging/IO belong in dedicated layers; keep core logic pure where practical.

### Example: avoid hidden state
```python
# Bad: hidden dependency on global cache and mutates input
cache = {}
def enrich(user):
    cache[user.id] = user  # side effect
    user.profile = fetch_profile(user.id)  # mutates
    return user

# Better: explicit inputs/outputs
def enrich(user: User, cache: dict[str, User]) -> User:
    profile = fetch_profile(user.id)
    return UserWithProfile(user=user, profile=profile)
```

### Guard against accidental mutation
- Use `frozen=True` dataclasses or tuples where possible.
- If you must mutate (e.g., performance), call it out in docstrings and keep it localized.

