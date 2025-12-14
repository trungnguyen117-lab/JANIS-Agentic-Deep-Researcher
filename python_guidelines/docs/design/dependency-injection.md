# Dependency Injection

- Don’t instantiate dependencies inside functions; accept them as parameters or inject via factories/DI.
- This improves testability and modularity; makes mocking/replacement trivial.
- Avoid singletons where possible; pass scoped resources (db sessions, clients) explicitly.

### Example: injectable db and clients
```python
# Bad
def send_report(user_id: str):
    db = Database()
    client = EmailClient()
    user = db.get_user(user_id)
    client.send(user.email, "hello")

# Better
def send_report(user_id: str, db: Database, mailer: EmailClient):
    user = db.get_user(user_id)
    mailer.send(user.email, "hello")
```
In tests, pass fakes/stubs for `db` and `mailer` without touching global state.

