"""Langfuse integration for token usage tracking and observability."""

import os
from typing import Optional
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler


def get_langfuse_handler() -> Optional[CallbackHandler]:
    """Get Langfuse callback handler if configured.
    
    Returns:
        CallbackHandler instance if Langfuse is configured, None otherwise.
    """
    # Get Langfuse credentials from environment
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
    
    # If not configured, return None (Langfuse is optional)
    if not public_key or not secret_key:
        return None
    
    # Initialize Langfuse client
    langfuse = Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        host=host,
    )
    
    # Create and return callback handler
    return CallbackHandler(
        public_key=public_key,
        secret_key=secret_key,
        host=host,
    )


def flush_langfuse():
    """Flush pending Langfuse events to ensure they're sent."""
    try:
        langfuse = Langfuse(
            public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
            host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )
        langfuse.flush()
    except Exception:
        # Silently fail if Langfuse is not configured
        pass

