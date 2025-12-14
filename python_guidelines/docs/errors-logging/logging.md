# Logging

- Never use `print` in production code; use the `logging` module.
- Configure loggers in the entrypoint (handlers, format, level); avoid ad-hoc config in libraries.
- Use module-level loggers (`logging.getLogger(__name__)`); log at the right levels.

### Example setup
```python
import logging

LOG_FMT = "%(asctime)s %(levelname)s %(name)s %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FMT)
log = logging.getLogger(__name__)
```

### Structured logging
```python
import logging
import logging.config

LOGGING = {
    "version": 1,
    "formatters": {
        "json": {
            "format": '{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}'
        }
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json"}
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}

logging.config.dictConfig(LOGGING)
log = logging.getLogger(__name__)
```

### Level guidance
- DEBUG: verbose internals (disable in prod)
- INFO: high-level events (startup, key actions)
- WARNING: unexpected but handled
- ERROR: request failed, raised or handled
- CRITICAL: system-wide failure

