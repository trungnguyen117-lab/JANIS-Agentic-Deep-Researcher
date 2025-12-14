# Data Practices

- Prefer immutable data where possible (frozen dataclasses, tuples).
- Avoid magic numbers/strings; use named constants.
- Prefer comprehensions over manual loops for clarity.
- Use generators for large iterables to save memory.
- Lean on stdlib helpers (`itertools`, `collections`, `pathlib`) instead of reinventing helpers.

