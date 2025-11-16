"""Langfuse integration for token usage tracking and observability."""

import os
from typing import Optional, Any
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


class TokenTrackingCallbackHandler(CallbackHandler):
    """Langfuse callback handler that also tracks token usage directly from callbacks.
    
    This extends Langfuse's CallbackHandler to:
    1. Send data to Langfuse (for observability)
    2. Track token usage directly from callbacks (for real-time state updates)
    
    This eliminates the need for OpenLIT and API queries.
    """
    
    def __init__(self, public_key: Optional[str] = None, **kwargs):
        """Initialize the callback handler."""
        super().__init__(public_key=public_key, **kwargs)
        # Import here to avoid circular imports
        from backend.deepagents.middleware.token_usage_state import add_token_usage_from_langfuse_callback
        self._add_usage = add_token_usage_from_langfuse_callback
    
    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Track token usage when LLM call ends."""
        # Call parent to send to Langfuse
        super().on_llm_end(response, **kwargs)
        
        # Extract token usage from response
        if response.llm_output and "token_usage" in response.llm_output:
            token_usage = response.llm_output["token_usage"]
            
            # Extract thread_id from Langfuse context or callback metadata
            thread_id = None
            
            # Try to get from Langfuse context (session_id)
            try:
                from langfuse import langfuse_context
                if hasattr(langfuse_context, "get_current_trace"):
                    trace = langfuse_context.get_current_trace()
                    if trace and hasattr(trace, "session_id"):
                        thread_id = trace.session_id
            except Exception:
                pass
            
            # Fallback: Try to extract from kwargs metadata
            if not thread_id:
                if "metadata" in kwargs:
                    metadata = kwargs.get("metadata")
                    if isinstance(metadata, dict):
                        thread_id = metadata.get("thread_id") or metadata.get("session_id")
            
            # Fallback: Try to extract from run_id
            if not thread_id and "run_id" in kwargs:
                run_id = kwargs.get("run_id")
                if isinstance(run_id, dict):
                    thread_id = run_id.get("thread_id") or run_id.get("session_id")
                elif hasattr(run_id, "thread_id"):
                    thread_id = run_id.thread_id
                elif hasattr(run_id, "session_id"):
                    thread_id = run_id.session_id
            
            # Extract usage data
            input_tokens = token_usage.get("prompt_tokens", token_usage.get("input_tokens", 0))
            output_tokens = token_usage.get("completion_tokens", token_usage.get("output_tokens", 0))
            total_tokens = token_usage.get("total_tokens", input_tokens + output_tokens)
            
            # Extract reasoning tokens if available
            reasoning_tokens = token_usage.get("reasoning_tokens", 0)
            completion_tokens = token_usage.get("completion_tokens", output_tokens - reasoning_tokens if reasoning_tokens > 0 else output_tokens)
            
            # Extract model from response if available
            model = "unknown"
            if response.llm_output:
                model = response.llm_output.get("model_name", response.llm_output.get("model", "unknown"))
            
            # Calculate cost (will be calculated in the function if model is known)
            cost = 0.0
            
            # Add to thread-isolated usage list (only if we have thread_id)
            if thread_id:
                self._add_usage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    completion_tokens=completion_tokens,
                    reasoning_tokens=reasoning_tokens,
                    total_tokens=total_tokens,
                    cost=cost,
                    model=model,
                    thread_id=thread_id,
                )


def get_langfuse_handler() -> Optional[CallbackHandler]:
    """Get Langfuse callback handler if configured.
    
    Returns:
        TokenTrackingCallbackHandler instance if Langfuse is configured, None otherwise.
        This handler tracks token usage directly from callbacks and sends to Langfuse.
    """
    # Get Langfuse credentials from environment
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    # Support both LANGFUSE_BASE_URL (standard) and LANGFUSE_HOST (for compatibility)
    base_url = os.environ.get("LANGFUSE_BASE_URL") or os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
    
    # If not configured, return None (Langfuse is optional)
    if not public_key or not secret_key:
        return None
    
    # Initialize Langfuse client (optional, but ensures client is configured)
    # The CallbackHandler will use get_client() which reads from environment variables
    langfuse = Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        base_url=base_url,
    )
    
    # Create and return token tracking callback handler
    # This extends Langfuse's CallbackHandler to also track token usage directly
    return TokenTrackingCallbackHandler(
        public_key=public_key,
    )


def flush_langfuse():
    """Flush pending Langfuse events to ensure they're sent."""
    try:
        base_url = os.environ.get("LANGFUSE_BASE_URL") or os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
        langfuse = Langfuse(
            public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
            base_url=base_url,
        )
        langfuse.flush()
    except Exception:
        # Silently fail if Langfuse is not configured
        pass

