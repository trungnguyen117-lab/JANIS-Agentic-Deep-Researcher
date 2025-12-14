# Functions & SRP

- Keep functions short (roughly one screen ~40–50 lines); extract helpers when they grow.
- Each function/class should do one thing well; if it has multiple responsibilities, split it.
- Avoid `utils.py`; organize by domain or responsibility.

### Example: split responsibilities
```python
# Before: fetch, validate, log, and save all together
def process_order(req: Request) -> Order:
    log.info("processing order")
    data = req.json()
    validate(data)
    order = Order.from_dict(data)
    db.save(order)
    notify(order)
    return order

# After: smaller helpers, clearer tests
def parse_order(req: Request) -> dict: ...
def build_order(data: dict) -> Order: ...
def save_order(order: Order) -> None: ...
def notify_order(order: Order) -> None: ...
```

### Smell: “mega” files
If a file covers many concerns, split by domain (e.g., `orders/parser.py`, `orders/service.py`, `orders/validators.py`) instead of piling into `utils.py`.

