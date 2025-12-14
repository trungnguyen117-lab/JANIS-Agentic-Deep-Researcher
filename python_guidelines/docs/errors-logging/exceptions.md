# Exceptions

- Raise explicit, meaningful exceptions; don’t return `None` to hide errors.
- Don’t swallow exceptions silently; re-raise or wrap with context.
- Use custom exceptions where it clarifies intent (e.g., `InvalidUserError`).

### Example
```python
class InvalidUserError(Exception):
    pass

def fetch_user(user_id: str) -> User:
    user = repo.get(user_id)
    if not user:
        raise InvalidUserError(f"user {user_id} not found")
    return user
```

### Wrapping with context
```python
try:
    process_payment(order_id)
except PaymentError as exc:
    raise OrderFailedError(order_id) from exc
```

