# Testing Guidelines

- Test one behavior per test; keep tests small and readable.
- Use pytest fixtures to share setup; avoid excessive mocking.
- Prefer asserting observable outcomes over internal calls.
- Name tests by behavior (`test_total_price_includes_all_items`).

### Example
```python
@pytest.fixture
def cart():
    return Cart(items=[Item(price=10), Item(price=15)])

def test_total_price(cart):
    assert cart.total() == 25
```

### Avoid over-mocking
- Mock only external boundaries (HTTP calls, DB, time); keep business logic under real code.
- If you must mock, assert behavior/results, not the exact call ordering unless critical.

