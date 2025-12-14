# Catch-All Exceptions

- Avoid `except Exception:` unless you re-raise or wrap it; catch specific exceptions instead.
- If you must have a top-level catch, log with stack info and exit or re-raise; don’t continue silently.

