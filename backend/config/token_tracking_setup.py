"""Unified token tracking setup - supports OpenLIT, OpenTelemetry, and Langfuse.

Environment variable: TOKEN_TRACKING_LIBRARY
- "openlit" (default): Use OpenLIT for automatic instrumentation
- "opentelemetry": Use OpenTelemetry directly with manual instrumentation
- "langfuse": Use Langfuse API to query token usage from traces
"""

import os
from typing import Literal

# Determine which library to use
TOKEN_TRACKING_LIBRARY: Literal["openlit", "opentelemetry", "langfuse"] = os.getenv(
    "TOKEN_TRACKING_LIBRARY", "openlit"
).lower()


def setup_token_tracking():
    """Setup token tracking based on TOKEN_TRACKING_LIBRARY environment variable.
    
    This must be called before importing LangChain models.
    
    Note: Langfuse doesn't require setup here - it uses the CallbackHandler
    which is configured in main.py. The token usage is queried from the API.
    """
    if TOKEN_TRACKING_LIBRARY == "opentelemetry":
        from backend.config.opentelemetry_tracker import setup_opentelemetry_tracking
        setup_opentelemetry_tracking()
    elif TOKEN_TRACKING_LIBRARY == "langfuse":
        # Langfuse uses CallbackHandler (configured in main.py)
        # No setup needed here - token usage is queried from API
        pass
    else:  # default to openlit
        from backend.config.openlit_setup import setup_openlit
        setup_openlit()


def get_tracking_library() -> str:
    """Get the current token tracking library being used."""
    return TOKEN_TRACKING_LIBRARY

