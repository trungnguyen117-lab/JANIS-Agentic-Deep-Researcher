"""Middleware to track token usage in LangGraph state by reading from messages (stream_usage=True).

With stream_usage=True, each AI message has usage_metadata with token usage.
We aggregate all usage from messages in state and update state.token_usage.
This is thread-isolated because state is thread-isolated.
"""

from typing import Any, NotRequired, Annotated, Callable, Awaitable, Optional
from langchain.agents.middleware.types import AgentMiddleware, AgentState, ModelRequest, ModelResponse
from langgraph.runtime import Runtime
from langgraph.types import Command, Overwrite
from langchain_core.messages import AIMessage
import threading
import json
import os


# Thread-isolated usage lists (keyed by LangGraph thread_id)
# Key: thread_id (str), Value: list of incremental usage updates
# This dictionary is thread-safe and scales to thousands of users
# Old entries are automatically cleaned up when lists are cleared
_usage_lists_by_thread: dict[str, list[dict[str, Any]]] = {}
_usage_lists_lock = threading.Lock()

# Thread-isolated cumulative token usage (keyed by LangGraph thread_id)
# This is updated in real-time during model calls (awrap_model_call)
# and read by abefore_agent to update LangGraph state
# Key: thread_id (str), Value: cumulative token usage dict
_cumulative_usage_by_thread: dict[str, dict[str, Any]] = {}
_cumulative_usage_lock = threading.Lock()


def _get_usage_list(thread_id: str) -> list[dict[str, Any]]:
    """Get thread-isolated list of token usage updates.
    
    These are incremental updates that will be aggregated with state.token_usage
    in abefore_agent/aafter_agent.
    
    Args:
        thread_id: LangGraph thread_id (required).
    
    Returns:
        List of incremental usage updates for the specified thread.
    """
    with _usage_lists_lock:
        if thread_id not in _usage_lists_by_thread:
            _usage_lists_by_thread[thread_id] = []
        return _usage_lists_by_thread[thread_id]


def _clear_usage_list(thread_id: str):
    """Clear the thread-isolated usage list after processing.
    
    Args:
        thread_id: LangGraph thread_id (required).
    """
    with _usage_lists_lock:
        if thread_id in _usage_lists_by_thread:
            _usage_lists_by_thread[thread_id].clear()
            # Optionally remove empty entries to prevent memory growth
            # (but keeping them is fine since they're just empty lists)


def _get_cumulative_usage(thread_id: str) -> dict[str, Any] | None:
    """Get thread-isolated cumulative token usage.
    
    Args:
        thread_id: LangGraph thread_id (required).
    
    Returns:
        Cumulative token usage dict or None if not set.
    """
    with _cumulative_usage_lock:
        return _cumulative_usage_by_thread.get(thread_id)


def _set_cumulative_usage(thread_id: str, usage: dict[str, Any]):
    """Set thread-isolated cumulative token usage.
    
    Args:
        thread_id: LangGraph thread_id (required).
        usage: Cumulative token usage dict.
    """
    with _cumulative_usage_lock:
        _cumulative_usage_by_thread[thread_id] = usage.copy()


def _clear_cumulative_usage(thread_id: str):
    """Clear the thread-isolated cumulative usage.
    
    Args:
        thread_id: LangGraph thread_id (required).
    """
    with _cumulative_usage_lock:
        if thread_id in _cumulative_usage_by_thread:
            del _cumulative_usage_by_thread[thread_id]


def _aggregate_usage_with_state(
    current_state_usage: dict[str, Any] | None,
    incremental_updates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate incremental updates with current state usage.
    
    Args:
        current_state_usage: Current token usage from state (may be None for new threads)
        incremental_updates: List of incremental token usage updates
    
    Returns:
        Updated cumulative token usage
    """
    # Start with current state usage or zero
    if current_state_usage:
        cumulative = {
            "input": current_state_usage.get("input", 0),
            "output": current_state_usage.get("output", 0),
            "completion": current_state_usage.get("completion", 0),
            "reasoning": current_state_usage.get("reasoning", 0),
            "total": current_state_usage.get("total", 0),
            "cost": current_state_usage.get("cost", 0.0),
        }
    else:
        cumulative = {
    "input": 0,
    "output": 0,
    "completion": 0,
    "reasoning": 0,
    "total": 0,
    "cost": 0.0,
}

    # Add all incremental updates
    for update in incremental_updates:
        cumulative["input"] += update.get("input", 0)
        cumulative["output"] += update.get("output", 0)
        cumulative["completion"] += update.get("completion", 0)
        cumulative["reasoning"] += update.get("reasoning", 0)
        cumulative["total"] += update.get("total", 0)
        cumulative["cost"] += update.get("cost", 0.0)
    
    return cumulative


def add_token_usage_from_langfuse_callback(
    input_tokens: int,
    output_tokens: int,
    completion_tokens: int,
    reasoning_tokens: int,
    total_tokens: int,
    cost: float,
    model: str = "unknown",
    thread_id: str | None = None,
):
    """Add token usage from Langfuse callback handler.
    
    This is called by Langfuse's callback handler when it detects an LLM call.
    Stores incremental usage in thread-isolated list (keyed by LangGraph thread_id),
    which will be aggregated with state.token_usage in abefore_agent/aafter_agent.
    
    Args:
        input_tokens: Input token count
        output_tokens: Output token count
        completion_tokens: Completion token count
        reasoning_tokens: Reasoning token count
        total_tokens: Total token count
        cost: Cost in USD
        model: Model name (stored for reference, but model is tracked in state)
        thread_id: LangGraph thread_id. If None, usage will be dropped (prevents cross-thread contamination).
    """
    if thread_id is None:
        # No thread_id available - can't track usage without thread_id
        # This prevents mixing usage across different threads
        return
    
    usage_update = {
        "input": input_tokens,
        "output": output_tokens,
        "completion": completion_tokens,
        "reasoning": reasoning_tokens,
        "total": total_tokens,
        "cost": cost,
        "model": model,
    }
    # Add to thread-isolated list - will be aggregated with state in middleware
    usage_list = _get_usage_list(thread_id)
    usage_list.append(usage_update)


def add_token_usage_from_openlit(
    input_tokens: int,
    output_tokens: int,
    completion_tokens: int,
    reasoning_tokens: int,
    total_tokens: int,
    cost: float,
    model: str = "unknown",
    thread_id: str | None = None,
):
    """Add token usage from OpenLIT span exporter.
    
    This is called by OpenLIT's span exporter when it detects an LLM call.
    Stores incremental usage in thread-isolated list (keyed by LangGraph thread_id),
    which will be aggregated with state.token_usage in abefore_agent/aafter_agent.
    
    Args:
        input_tokens: Input token count
        output_tokens: Output token count
        completion_tokens: Completion token count
        reasoning_tokens: Reasoning token count
        total_tokens: Total token count
        cost: Cost in USD
        model: Model name (stored for reference, but model is tracked in state)
        thread_id: LangGraph thread_id. If None, usage will be dropped (prevents cross-thread contamination).
    """
    if thread_id is None:
        # No thread_id available - can't track usage without thread_id
        # This prevents mixing usage across different threads
        return
    
    usage_update = {
        "input": input_tokens,
        "output": output_tokens,
        "completion": completion_tokens,
        "reasoning": reasoning_tokens,
        "total": total_tokens,
        "cost": cost,
        "model": model,
    }
    # Add to thread-isolated list - will be aggregated with state in middleware
    usage_list = _get_usage_list(thread_id)
    usage_list.append(usage_update)


async def update_token_usage_from_langfuse(session_id: Optional[str] = None) -> dict[str, Any]:
    """Query Langfuse API to get token usage (async).
    
    This is called by the middleware when using Langfuse for token tracking.
    Queries Langfuse API for traces matching the session_id (thread_id).
    Returns the cumulative usage which will be stored in state.
    
    Args:
        session_id: Session ID (thread_id) to query traces for. If None, queries recent traces.
    
    Returns:
        Cumulative token usage dictionary from Langfuse API.
    """
    # Check if we're using Langfuse
    tracking_library = os.getenv("TOKEN_TRACKING_LIBRARY", "openlit").lower()
    if tracking_library != "langfuse":
        # Not using Langfuse - return zero usage
        return {
            "input": 0,
            "output": 0,
            "completion": 0,
            "reasoning": 0,
            "total": 0,
            "cost": 0.0,
        }
    
    try:
        from backend.config.langfuse_token_tracker import get_token_usage_from_langfuse
        
        # Query Langfuse API for token usage (async)
        # This returns cumulative usage for the session/thread
        usage = await get_token_usage_from_langfuse(session_id=session_id, limit=100)
        
        # Return the usage from Langfuse (this is cumulative for the thread)
        return {
                "input": usage.get("input", 0),
                "output": usage.get("output", 0),
                "completion": usage.get("completion", 0),
                "reasoning": usage.get("reasoning", 0),
                "total": usage.get("total", 0),
                "cost": usage.get("cost", 0.0),
            }
    
    except Exception as e:
        # Silently fail if Langfuse is not available
        print(f"[Token Usage State] Error querying Langfuse: {e}")
        return {
            "input": 0,
            "output": 0,
            "completion": 0,
            "reasoning": 0,
            "total": 0,
            "cost": 0.0,
        }


def _token_usage_reducer(
    current: dict[str, Any] | None,
    update: dict[str, Any] | None,
) -> dict[str, Any]:
    """Reducer function for token usage in state.
    
    Since we track cumulative usage globally and return the full cumulative value
    from before_agent, we simply replace the current value with the update.
    
    Args:
        current: Current token usage in state (may be None)
        update: New cumulative token usage to set
    
    Returns:
        Updated token usage (replaces current with update)
    """
    if update is None:
        if current is None:
            return {
                "input": 0,
                "output": 0,
                "completion": 0,
                "reasoning": 0,
                "cache": 0,
                "prompt": 0,
                "total": 0,
                "cost": 0.0,
            }
        return current
    
    # Replace with the update (which is the full cumulative usage)
    return {
        "input": update.get("input", 0),
        "output": update.get("output", 0),
        "completion": update.get("completion", 0),
        "reasoning": update.get("reasoning", 0),
        "cache": update.get("cache", 0),
        "prompt": update.get("prompt", 0),
        "total": update.get("total", 0),
        "cost": update.get("cost", 0.0),
    }


# Note: The reducer is applied via the middleware's return value
# LangGraph will use the reducer if the state field is annotated with it
# But we need to ensure the state update is properly structured


class TokenUsageState(AgentState):
    """State for token usage tracking."""
    
    token_usage: Annotated[
        NotRequired[dict[str, Any]],
        _token_usage_reducer
    ]
    """Cumulative token usage (input, output, completion, reasoning, total, cost)."""
    
    current_model: NotRequired[str]
    """Current model being used for LLM calls."""


class TokenUsageStateMiddleware(AgentMiddleware):
    """Middleware that tracks token usage in LangGraph state from OpenLIT spans."""
    
    state_schema = TokenUsageState
    
    def __init__(self):
        """Initialize middleware."""
        super().__init__()
        # Set up file logging for token usage tracking
        import logging
        import os
        from pathlib import Path
        
        # Create a file handler for token usage logs
        log_file = Path(__file__).parent.parent.parent.parent / "token_usage_debug.log"
        file_handler = logging.FileHandler(log_file, mode='a')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s'
        ))
        
        # Get or create logger for token usage
        self.logger = logging.getLogger('token_usage_middleware')
        self.logger.setLevel(logging.DEBUG)  # Set to DEBUG to see all messages
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
        self.logger.propagate = False
    
    def before_agent(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Initialize token usage in state before agent starts (synchronous).
        
        This ensures token_usage exists in state from the beginning.
        Real-time updates happen in aafter_model after each model call.
        This is thread-isolated because state is thread-isolated.
        """
        # Initialize token_usage if it doesn't exist in state
        # aafter_model will update it after each model call
        if state and "token_usage" not in state:
            return {
                "token_usage": {
                    "input": 0,
                    "output": 0,
                    "completion": 0,
                    "reasoning": 0,
                    "cache": 0,
                    "prompt": 0,
                    "total": 0,
                    "cost": 0.0,
                },
                "current_model": state.get("current_model", "unknown"),
            }
        return None
    
    async def abefore_agent(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Initialize token usage in state before agent starts.
        
        This ensures token_usage exists in state from the beginning.
        Real-time updates happen in aafter_model after each model call.
        This is thread-isolated because state is thread-isolated.
        """
        # Initialize token_usage if it doesn't exist in state
        # aafter_model will update it after each model call
        if state and "token_usage" not in state:
            return {
                "token_usage": {
                    "input": 0,
                    "output": 0,
                    "completion": 0,
                    "reasoning": 0,
                    "cache": 0,
                    "prompt": 0,
                    "total": 0,
                    "cost": 0.0,
                },
                "current_model": state.get("current_model", "unknown"),
            }
        return None
    
    async def aafter_model(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Update token usage in state after each model call (async).
        
        This runs after EACH model call, providing real-time token usage updates.
        Reads token usage from the latest messages and updates state immediately.
        This is thread-isolated because state is thread-isolated.
        """
        # Recalculate token usage from scratch by reading all AI messages
        # This ensures accuracy and thread isolation (each thread's state has its own messages)
        cumulative = {
            "input": 0,
            "output": 0,
            "completion": 0,
            "reasoning": 0,
            "cache": 0,
            "prompt": 0,
            "total": 0,
            "cost": 0.0,
        }
        
        # Read token usage from all AI messages in state (from stream_usage=True)
        messages = state.get("messages", []) if state else []
        current_model = state.get("current_model", "unknown") if state else "unknown"
        
        self.logger.info(f"aafter_model: Processing {len(messages)} messages")
        
        for idx, msg in enumerate(messages):
            if isinstance(msg, AIMessage):
                msg_id = getattr(msg, "id", f"msg_{idx}")
                has_usage_meta = hasattr(msg, "usage_metadata") and msg.usage_metadata
                
                # Extract usage from usage_metadata (provided by stream_usage=True)
                if has_usage_meta:
                    usage_meta = msg.usage_metadata
                    self.logger.info(
                        f"aafter_model: Message {idx} usage_metadata type={type(usage_meta).__name__}, "
                        f"value={usage_meta}"
                    )
                    # usage_metadata can be either a dict or an object with attributes
                    if isinstance(usage_meta, dict):
                        # Extract tokens - handle None values properly (don't use 'or 0' which converts 0 to 0)
                        input_tokens_raw = usage_meta.get("input_tokens")
                        output_tokens_raw = usage_meta.get("output_tokens")
                        total_tokens_raw = usage_meta.get("total_tokens")
                        
                        input_tokens = input_tokens_raw if input_tokens_raw is not None else 0
                        output_tokens = output_tokens_raw if output_tokens_raw is not None else 0
                        total_tokens = total_tokens_raw if total_tokens_raw is not None else 0
                        completion_tokens = usage_meta.get("completion_tokens") if usage_meta.get("completion_tokens") is not None else 0
                        reasoning_tokens = usage_meta.get("reasoning_tokens") if usage_meta.get("reasoning_tokens") is not None else 0
                        
                        self.logger.info(
                            f"aafter_model: Message {idx} extracted from dict - "
                            f"input_tokens_raw={input_tokens_raw}, input_tokens={input_tokens}, "
                            f"output_tokens_raw={output_tokens_raw}, output_tokens={output_tokens}, "
                            f"total_tokens_raw={total_tokens_raw}, total_tokens={total_tokens}"
                        )
                        
                        # Extract cache_read from input_token_details
                        # API provides input_cache_read (cache tokens) and input (prompt tokens)
                        # Total input = input_cache_read + input
                        input_token_details = usage_meta.get("input_token_details")
                        cache_read = 0
                        prompt_tokens = 0
                        if input_token_details:
                            if isinstance(input_token_details, dict):
                                # Try input_cache_read first (newer API format)
                                cache_read_raw = input_token_details.get("input_cache_read")
                                if cache_read_raw is not None:
                                    cache_read = cache_read_raw
                                    # If we have input_cache_read, prompt is the "input" field in input_token_details
                                    prompt_raw = input_token_details.get("input")
                                    prompt_tokens = prompt_raw if prompt_raw is not None else (input_tokens - cache_read)
                                else:
                                    # Fallback to old format: cache_read
                                    cache_read_raw = input_token_details.get("cache_read")
                                    cache_read = cache_read_raw if cache_read_raw is not None else 0
                                    prompt_tokens = input_tokens - cache_read
                            elif hasattr(input_token_details, "input_cache_read"):
                                # Try input_cache_read first (newer API format)
                                cache_read_raw = getattr(input_token_details, "input_cache_read", None)
                                if cache_read_raw is not None:
                                    cache_read = cache_read_raw
                                    prompt_raw = getattr(input_token_details, "input", None)
                                    prompt_tokens = prompt_raw if prompt_raw is not None else (input_tokens - cache_read)
                                else:
                                    # Fallback to old format: cache_read
                                    cache_read_raw = getattr(input_token_details, "cache_read", None)
                                    cache_read = cache_read_raw if cache_read_raw is not None else 0
                                    prompt_tokens = input_tokens - cache_read
                        else:
                            # No input_token_details - assume all input is prompt (no cache)
                            prompt_tokens = input_tokens
                            cache_read = 0
                        
                        # Extract reasoning from output_token_details if not already set
                        output_token_details = usage_meta.get("output_token_details", {})
                        if reasoning_tokens == 0 and isinstance(output_token_details, dict):
                            reasoning_tokens = output_token_details.get("reasoning", 0) or 0
                        
                        # Calculate completion = output - reasoning
                        if completion_tokens == 0:
                            completion_tokens = output_tokens - reasoning_tokens
                    else:
                        # It's an object with attributes
                        input_tokens = getattr(usage_meta, "input_tokens", 0) or 0
                        output_tokens = getattr(usage_meta, "output_tokens", 0) or 0
                        completion_tokens = getattr(usage_meta, "completion_tokens", 0) or 0
                        reasoning_tokens = getattr(usage_meta, "reasoning_tokens", 0) or 0
                        total_tokens = getattr(usage_meta, "total_tokens", 0) or 0
                        
                        # Try to get cache_read from input_token_details
                        # API provides input_cache_read (cache tokens) and input (prompt tokens)
                        # Total input = input_cache_read + input
                        cache_read = 0
                        prompt_tokens = 0
                        if hasattr(usage_meta, "input_token_details"):
                            input_token_details = getattr(usage_meta, "input_token_details", None)
                            if input_token_details:
                                if isinstance(input_token_details, dict):
                                    # Try input_cache_read first (newer API format)
                                    cache_read_raw = input_token_details.get("input_cache_read")
                                    if cache_read_raw is not None:
                                        cache_read = cache_read_raw
                                        # If we have input_cache_read, prompt is the "input" field in input_token_details
                                        prompt_raw = input_token_details.get("input")
                                        prompt_tokens = prompt_raw if prompt_raw is not None else (input_tokens - cache_read)
                                    else:
                                        # Fallback to old format: cache_read
                                        cache_read_raw = input_token_details.get("cache_read")
                                        cache_read = cache_read_raw if cache_read_raw is not None else 0
                                        prompt_tokens = input_tokens - cache_read
                                elif hasattr(input_token_details, "input_cache_read"):
                                    # Try input_cache_read first (newer API format)
                                    cache_read_raw = getattr(input_token_details, "input_cache_read", None)
                                    if cache_read_raw is not None:
                                        cache_read = cache_read_raw
                                        prompt_raw = getattr(input_token_details, "input", None)
                                        prompt_tokens = prompt_raw if prompt_raw is not None else (input_tokens - cache_read)
                                    else:
                                        # Fallback to old format: cache_read
                                        cache_read_raw = getattr(input_token_details, "cache_read", None)
                                        cache_read = cache_read_raw if cache_read_raw is not None else 0
                                        prompt_tokens = input_tokens - cache_read
                        else:
                            # No input_token_details - assume all input is prompt (no cache)
                            prompt_tokens = input_tokens
                            cache_read = 0
                        
                        # Calculate completion = output - reasoning if not set
                        if completion_tokens == 0:
                            completion_tokens = output_tokens - reasoning_tokens
                    
                    self.logger.info(
                        f"aafter_model: Message {idx} (id={msg_id}) has usage_metadata - "
                        f"input={input_tokens}, output={output_tokens}, total={total_tokens}, "
                        f"cache={cache_read}, prompt={prompt_tokens}, "
                        f"completion={completion_tokens}, reasoning={reasoning_tokens}, "
                        f"usage_meta_type={type(usage_meta).__name__}, "
                        f"has_input_token_details={bool(input_token_details)}, "
                        f"input_token_details_type={type(input_token_details).__name__ if input_token_details else 'None'}, "
                        f"input_token_details_value={input_token_details}"
                    )
                    
                    cumulative["input"] += input_tokens
                    cumulative["output"] += output_tokens
                    cumulative["completion"] += completion_tokens
                    cumulative["reasoning"] += reasoning_tokens
                    cumulative["cache"] += cache_read
                    cumulative["prompt"] += prompt_tokens
                    cumulative["total"] += total_tokens
                else:
                    self.logger.warning(
                        f"aafter_model: Message {idx} (id={msg_id}) has NO usage_metadata - "
                        f"has_usage_metadata_attr={hasattr(msg, 'usage_metadata')}, "
                        f"usage_metadata_value={getattr(msg, 'usage_metadata', None)}"
                    )
                
                # Extract model from response_metadata (use most recent)
                if hasattr(msg, "response_metadata") and msg.response_metadata:
                    model = msg.response_metadata.get("model_name") or msg.response_metadata.get("model")
                    if model and model != "unknown":
                        current_model = model
        
        # Calculate cost based on model pricing
        if current_model != "unknown" and (cumulative["input"] > 0 or cumulative["output"] > 0):
            try:
                from backend.config.openlit_setup import calculate_custom_cost
                cumulative["cost"] = calculate_custom_cost(
                    current_model,
                    cumulative["input"],
                    cumulative["output"]
                ) or 0.0
            except Exception:
                pass
            
        # Log calculated token usage to file
        self.logger.info(
            f"aafter_model: Calculated token usage - "
            f"input={cumulative['input']}, output={cumulative['output']}, "
            f"prompt={cumulative['prompt']}, cache={cumulative['cache']}, "
            f"completion={cumulative['completion']}, reasoning={cumulative['reasoning']}, "
            f"total={cumulative['total']}, cost={cumulative['cost']}, model={current_model}, "
            f"messages_count={len(messages)}"
        )
        
        # Return state update directly - this updates state immediately after each model call
        # According to LangChain docs, @after_model can return a dict to update state
        # This provides real-time updates to the frontend
        return {
            "token_usage": cumulative,
            "current_model": current_model,
        }
    
    def after_model(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Update token usage in state after each model call (synchronous).
        
        This runs after EACH model call, providing real-time token usage updates.
        Reads token usage from the latest messages and updates state immediately.
        This is thread-isolated because state is thread-isolated.
        """
        # Recalculate token usage from scratch by reading all AI messages
        # This ensures accuracy and thread isolation (each thread's state has its own messages)
        cumulative = {
            "input": 0,
            "output": 0,
            "completion": 0,
            "reasoning": 0,
            "cache": 0,
            "prompt": 0,
            "total": 0,
            "cost": 0.0,
        }
        
        # Read token usage from all AI messages in state (from stream_usage=True)
        messages = state.get("messages", []) if state else []
        current_model = state.get("current_model", "unknown") if state else "unknown"
        
        self.logger.info(f"after_model: Processing {len(messages)} messages")
        
        # Extract token usage from all AI messages
        for msg in messages:
            if isinstance(msg, AIMessage):
                # Check usage_metadata first (LangChain's native field - available immediately with stream_usage=True)
                if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                    usage_meta = msg.usage_metadata
                    cumulative["input"] += getattr(usage_meta, "input_tokens", 0) or 0
                    cumulative["output"] += getattr(usage_meta, "output_tokens", 0) or 0
                    cumulative["completion"] += getattr(usage_meta, "completion_tokens", 0) or 0
                    cumulative["reasoning"] += getattr(usage_meta, "reasoning_tokens", 0) or 0
                    cumulative["cache"] += getattr(usage_meta, "cache_read_tokens", 0) or 0
                    cumulative["prompt"] += getattr(usage_meta, "prompt_tokens", 0) or 0
                    cumulative["total"] += getattr(usage_meta, "total_tokens", 0) or 0
        
        # Calculate cost if pricing is available
        try:
            from backend.config.model import get_model_pricing
            pricing = get_model_pricing(current_model)
            cumulative["cost"] = (
                (cumulative["input"] / 1_000_000) * pricing.get("input_price_per_million", 0) +
                (cumulative["output"] / 1_000_000) * pricing.get("output_price_per_million", 0)
            ) or 0.0
        except Exception:
            pass
        
        # Log calculated token usage to file
        self.logger.info(
            f"after_model: Calculated token usage - "
            f"input={cumulative['input']}, output={cumulative['output']}, "
            f"prompt={cumulative['prompt']}, cache={cumulative['cache']}, "
            f"completion={cumulative['completion']}, reasoning={cumulative['reasoning']}, "
            f"total={cumulative['total']}, cost={cumulative['cost']}, model={current_model}, "
            f"messages_count={len(messages)}"
        )
        
        # Return state update directly - this updates state immediately after each model call
        return {
            "token_usage": cumulative,
            "current_model": current_model,
        }
    
    
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Intercept model calls and add cumulative token usage to response_metadata for real-time updates.
        
        With stream_usage=True, LangChain provides usage_metadata immediately after the call.
        We extract it, calculate cumulative usage from state, and add to response_metadata
        so the frontend can see token usage in real-time.
        """
        # Call the handler to get the response
        response = await handler(request)
        
        if not response.result:
            return response
        
        # Extract usage from all messages in response and calculate cumulative
        # Sum all incremental usages from this response
        cumulative_from_response = {
            "input": 0,
            "output": 0,
            "completion": 0,
            "reasoning": 0,
            "cache": 0,
            "prompt": 0,
            "total": 0,
            "cost": 0.0,
        }
        model_name = "unknown"
        
        for idx, msg in enumerate(response.result):
            if isinstance(msg, AIMessage):
                msg_id = getattr(msg, "id", f"msg_{idx}")
                has_usage_meta = hasattr(msg, "usage_metadata") and msg.usage_metadata
                has_response_meta = hasattr(msg, "response_metadata") and msg.response_metadata
                
                self.logger.info(
                    f"awrap_model_call: Processing message {idx} (id={msg_id}) - "
                    f"has_usage_metadata={has_usage_meta}, has_response_metadata={has_response_meta}"
                )
                
                # Extract incremental usage from this message
                incremental = None
                
                # Initialize variables to avoid undefined variable errors
                input_tokens = 0
                output_tokens = 0
                completion_tokens = 0
                reasoning_tokens = 0
                total_tokens = 0
                cache_read = 0
                prompt_tokens = 0
                
                # Check usage_metadata first (LangChain's native field - available immediately with stream_usage=True)
                if has_usage_meta:
                    usage_meta = msg.usage_metadata
                    self.logger.info(
                        f"awrap_model_call: Message {idx} usage_metadata type={type(usage_meta).__name__}, "
                        f"value={usage_meta}"
                    )
                    # usage_metadata can be either a dict or an object with attributes
                    if isinstance(usage_meta, dict):
                        # Extract tokens - handle None values properly
                        input_tokens_raw = usage_meta.get("input_tokens")
                        output_tokens_raw = usage_meta.get("output_tokens")
                        total_tokens_raw = usage_meta.get("total_tokens")
                        
                        input_tokens = input_tokens_raw if input_tokens_raw is not None else 0
                        output_tokens = output_tokens_raw if output_tokens_raw is not None else 0
                        total_tokens = total_tokens_raw if total_tokens_raw is not None else 0
                        completion_tokens = usage_meta.get("completion_tokens") if usage_meta.get("completion_tokens") is not None else 0
                        reasoning_tokens = usage_meta.get("reasoning_tokens") if usage_meta.get("reasoning_tokens") is not None else 0
                        
                        self.logger.info(
                            f"awrap_model_call: Message {idx} extracted from dict - "
                            f"input_tokens_raw={input_tokens_raw}, input_tokens={input_tokens}, "
                            f"output_tokens_raw={output_tokens_raw}, output_tokens={output_tokens}, "
                            f"total_tokens_raw={total_tokens_raw}, total_tokens={total_tokens}"
                        )
                        
                        # Extract cache_read from input_token_details
                        # API provides input_cache_read (cache tokens) and input (prompt tokens)
                        # Total input = input_cache_read + input
                        input_token_details = usage_meta.get("input_token_details")
                        cache_read = 0
                        prompt_tokens = 0
                        if input_token_details:
                            if isinstance(input_token_details, dict):
                                # Try input_cache_read first (newer API format)
                                cache_read_raw = input_token_details.get("input_cache_read")
                                if cache_read_raw is not None:
                                    cache_read = cache_read_raw
                                    # If we have input_cache_read, prompt is the "input" field in input_token_details
                                    prompt_raw = input_token_details.get("input")
                                    prompt_tokens = prompt_raw if prompt_raw is not None else (input_tokens - cache_read)
                                else:
                                    # Fallback to old format: cache_read
                                    cache_read_raw = input_token_details.get("cache_read")
                                    cache_read = cache_read_raw if cache_read_raw is not None else 0
                                    prompt_tokens = input_tokens - cache_read
                            elif hasattr(input_token_details, "input_cache_read"):
                                # Try input_cache_read first (newer API format)
                                cache_read_raw = getattr(input_token_details, "input_cache_read", None)
                                if cache_read_raw is not None:
                                    cache_read = cache_read_raw
                                    prompt_raw = getattr(input_token_details, "input", None)
                                    prompt_tokens = prompt_raw if prompt_raw is not None else (input_tokens - cache_read)
                                else:
                                    # Fallback to old format: cache_read
                                    cache_read_raw = getattr(input_token_details, "cache_read", None)
                                    cache_read = cache_read_raw if cache_read_raw is not None else 0
                                    prompt_tokens = input_tokens - cache_read
                        else:
                            # No input_token_details - assume all input is prompt (no cache)
                            prompt_tokens = input_tokens
                            cache_read = 0  # prompt = input - cache
                        
                        # Extract reasoning from output_token_details if not already set
                        output_token_details = usage_meta.get("output_token_details", {})
                        if reasoning_tokens == 0 and isinstance(output_token_details, dict):
                            reasoning_tokens = output_token_details.get("reasoning", 0) or 0
                        
                        # Calculate completion = output - reasoning
                        if completion_tokens == 0:
                            completion_tokens = output_tokens - reasoning_tokens
                    else:
                        # It's an object with attributes
                        input_tokens = getattr(usage_meta, "input_tokens", 0) or 0
                        output_tokens = getattr(usage_meta, "output_tokens", 0) or 0
                        completion_tokens = getattr(usage_meta, "completion_tokens", 0) or 0
                        reasoning_tokens = getattr(usage_meta, "reasoning_tokens", 0) or 0
                        total_tokens = getattr(usage_meta, "total_tokens", 0) or 0
                        
                        # Try to get cache_read from input_token_details
                        # API provides input_cache_read (cache tokens) and input (prompt tokens)
                        # Total input = input_cache_read + input
                        cache_read = 0
                        prompt_tokens = 0
                        if hasattr(usage_meta, "input_token_details"):
                            input_token_details = getattr(usage_meta, "input_token_details", None)
                            if input_token_details:
                                if isinstance(input_token_details, dict):
                                    # Try input_cache_read first (newer API format)
                                    cache_read_raw = input_token_details.get("input_cache_read")
                                    if cache_read_raw is not None:
                                        cache_read = cache_read_raw
                                        # If we have input_cache_read, prompt is the "input" field in input_token_details
                                        prompt_raw = input_token_details.get("input")
                                        prompt_tokens = prompt_raw if prompt_raw is not None else (input_tokens - cache_read)
                                    else:
                                        # Fallback to old format: cache_read
                                        cache_read_raw = input_token_details.get("cache_read")
                                        cache_read = cache_read_raw if cache_read_raw is not None else 0
                                        prompt_tokens = input_tokens - cache_read
                                elif hasattr(input_token_details, "input_cache_read"):
                                    # Try input_cache_read first (newer API format)
                                    cache_read_raw = getattr(input_token_details, "input_cache_read", None)
                                    if cache_read_raw is not None:
                                        cache_read = cache_read_raw
                                        prompt_raw = getattr(input_token_details, "input", None)
                                        prompt_tokens = prompt_raw if prompt_raw is not None else (input_tokens - cache_read)
                                    else:
                                        # Fallback to old format: cache_read
                                        cache_read_raw = getattr(input_token_details, "cache_read", None)
                                        cache_read = cache_read_raw if cache_read_raw is not None else 0
                                        prompt_tokens = input_tokens - cache_read
                        else:
                            # No input_token_details - assume all input is prompt (no cache)
                            prompt_tokens = input_tokens
                            cache_read = 0
                        
                        # Calculate completion = output - reasoning if not set
                        if completion_tokens == 0:
                            completion_tokens = output_tokens - reasoning_tokens
                    
                    self.logger.info(
                        f"awrap_model_call: Message {idx} has usage_metadata - "
                        f"input={input_tokens}, output={output_tokens}, total={total_tokens}, "
                        f"cache={cache_read}, prompt={prompt_tokens}, "
                        f"completion={completion_tokens}, reasoning={reasoning_tokens}, "
                        f"usage_meta_type={type(usage_meta).__name__}"
                    )
                    
                    incremental = {
                        "input": input_tokens,
                        "output": output_tokens,
                        "completion": completion_tokens,
                        "reasoning": reasoning_tokens,
                        "cache": cache_read,
                        "prompt": prompt_tokens,
                        "total": total_tokens,
                        "cost": 0.0,
                    }
                    # Extract model name if available
                    if has_response_meta:
                        model_name = msg.response_metadata.get("model_name", msg.response_metadata.get("model", "unknown"))
                
                # Check response_metadata.token_usage as fallback
                elif has_response_meta:
                    token_usage = msg.response_metadata.get("token_usage")
                    self.logger.info(
                        f"awrap_model_call: Message {idx} checking response_metadata.token_usage - "
                        f"token_usage={token_usage}"
                    )
                    if token_usage:
                        incremental = {
                            "input": token_usage.get("input_tokens", token_usage.get("input", 0)) or 0,
                            "output": token_usage.get("output_tokens", token_usage.get("output", 0)) or 0,
                            "completion": token_usage.get("completion_tokens", token_usage.get("completion", 0)) or 0,
                            "reasoning": token_usage.get("reasoning_tokens", token_usage.get("reasoning", 0)) or 0,
                            "total": token_usage.get("total_tokens", token_usage.get("total", 0)) or 0,
                            "cost": token_usage.get("cost", 0.0) or 0.0,
                        }
                        model_name = msg.response_metadata.get("model_name", msg.response_metadata.get("model", "unknown"))
                        self.logger.info(
                            f"awrap_model_call: Message {idx} extracted from response_metadata.token_usage - "
                            f"input={incremental['input']}, output={incremental['output']}, total={incremental['total']}"
                        )
                    else:
                        self.logger.warning(
                            f"awrap_model_call: Message {idx} has response_metadata but no token_usage key"
                        )
                else:
                    self.logger.warning(
                        f"awrap_model_call: Message {idx} has NO usage_metadata and NO response_metadata"
                    )
                
                # Add to cumulative from this response
                if incremental:
                    cumulative_from_response["input"] += incremental["input"]
                    cumulative_from_response["output"] += incremental["output"]
                    cumulative_from_response["completion"] += incremental["completion"]
                    cumulative_from_response["reasoning"] += incremental["reasoning"]
                    cumulative_from_response["cache"] += incremental.get("cache", 0)
                    cumulative_from_response["prompt"] += incremental.get("prompt", 0)
                    cumulative_from_response["total"] += incremental["total"]
                    cumulative_from_response["cost"] += incremental["cost"]
                else:
                    self.logger.warning(
                        f"awrap_model_call: Message {idx} - No incremental usage extracted, cumulative remains 0"
                    )
        
        # Try to get current cumulative from state if available
        # This gives us the cumulative up to this point
        current_cumulative = {
            "input": 0,
            "output": 0,
            "completion": 0,
            "reasoning": 0,
            "cache": 0,
            "prompt": 0,
            "total": 0,
            "cost": 0.0,
        }
        
        # Try to get state from request
        try:
            if hasattr(request, "state") and isinstance(request.state, dict):
                current_state_usage = request.state.get("token_usage")
                if current_state_usage and isinstance(current_state_usage, dict):
                    current_cumulative = {
                        "input": current_state_usage.get("input", 0),
                        "output": current_state_usage.get("output", 0),
                        "completion": current_state_usage.get("completion", 0),
                        "reasoning": current_state_usage.get("reasoning", 0),
                        "cache": current_state_usage.get("cache", 0),
                        "prompt": current_state_usage.get("prompt", 0),
                        "total": current_state_usage.get("total", 0),
                        "cost": current_state_usage.get("cost", 0.0),
                    }
        except Exception:
            pass
        
        # Calculate new cumulative (current from state + incremental from this response)
        new_cumulative = {
            "input": current_cumulative["input"] + cumulative_from_response["input"],
            "output": current_cumulative["output"] + cumulative_from_response["output"],
            "completion": current_cumulative["completion"] + cumulative_from_response["completion"],
            "reasoning": current_cumulative["reasoning"] + cumulative_from_response["reasoning"],
            "cache": current_cumulative["cache"] + cumulative_from_response["cache"],
            "prompt": current_cumulative["prompt"] + cumulative_from_response["prompt"],
            "total": current_cumulative["total"] + cumulative_from_response["total"],
            "cost": current_cumulative["cost"] + cumulative_from_response["cost"],
        }
        
        # Calculate cost if model is known
        if model_name != "unknown" and (new_cumulative["input"] > 0 or new_cumulative["output"] > 0):
            try:
                from backend.config.openlit_setup import calculate_custom_cost
                calculated_cost = calculate_custom_cost(
                    model_name,
                    new_cumulative["input"],
                    new_cumulative["output"]
                )
                if calculated_cost:
                    new_cumulative["cost"] = calculated_cost
            except Exception:
                pass
        
        # Add cumulative token usage to each AI message's response_metadata
        # This allows the frontend to see token usage in real-time
        updated_messages = []
        for msg in response.result:
            if isinstance(msg, AIMessage):
                # Ensure response_metadata exists
                if not hasattr(msg, "response_metadata") or msg.response_metadata is None:
                    msg.response_metadata = {}
                
                # Store cumulative usage in response_metadata for real-time frontend updates
                msg.response_metadata["token_usage"] = new_cumulative
                
                # Also store model name if available
                if model_name != "unknown":
                    msg.response_metadata["model_name"] = model_name
            
            updated_messages.append(msg)
        
        # Log calculated token usage to file
        self.logger.info(
            f"awrap_model_call: Calculated token usage - "
            f"input={new_cumulative['input']}, output={new_cumulative['output']}, "
            f"total={new_cumulative['total']}, cost={new_cumulative['cost']}, model={model_name}, "
            f"incremental_input={cumulative_from_response['input']}, incremental_output={cumulative_from_response['output']}"
        )
        
        # Note: We don't update state here - aafter_model handles that
        # aafter_model runs after each model call and returns state updates directly
        # This provides real-time updates to the frontend
        
        return ModelResponse(result=updated_messages)
    
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Intercept model calls (sync version) and add token usage to response_metadata.
        
        With stream_usage=True, LangChain provides usage_metadata immediately after the call.
        We extract it, update cumulative usage, and store it in response_metadata for real-time updates.
        """
        # Call the handler to get the response
        response = handler(request)
        
        if not response.result:
            return response
        
        # Extract usage from response messages (available immediately with stream_usage=True)
        incremental_usage = None
        for msg in response.result:
            if isinstance(msg, AIMessage):
                # Check usage_metadata first (LangChain's native field - available immediately with stream_usage=True)
                if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                    usage_meta = msg.usage_metadata
                    incremental_usage = {
                        "input": getattr(usage_meta, "input_tokens", 0) or 0,
                        "output": getattr(usage_meta, "output_tokens", 0) or 0,
                        "completion": getattr(usage_meta, "completion_tokens", 0) or 0,
                        "reasoning": getattr(usage_meta, "reasoning_tokens", 0) or 0,
                        "total": getattr(usage_meta, "total_tokens", 0) or 0,
                        "cost": 0.0,  # Will be calculated if available
                    }
                    break
                
                # Check response_metadata.token_usage as fallback
                if hasattr(msg, "response_metadata") and msg.response_metadata:
                    token_usage = msg.response_metadata.get("token_usage")
                    if token_usage:
                        incremental_usage = {
                            "input": token_usage.get("input_tokens", token_usage.get("input", 0)) or 0,
                            "output": token_usage.get("output_tokens", token_usage.get("output", 0)) or 0,
                            "completion": token_usage.get("completion_tokens", token_usage.get("completion", 0)) or 0,
                            "reasoning": token_usage.get("reasoning_tokens", token_usage.get("reasoning", 0)) or 0,
                            "total": token_usage.get("total_tokens", token_usage.get("total", 0)) or 0,
                            "cost": token_usage.get("cost", 0.0) or 0.0,
                        }
                        break
        
        # Note: We can't get thread_id here without runtime, so we skip adding to usage list
        # The usage will be captured by OpenLIT (which extracts thread_id from span attributes)
        # abefore_agent/aafter_agent will aggregate from state.token_usage
        
        # For response_metadata, we'll use incremental_usage if available
        # This is just for display - the real cumulative is in state.token_usage
        # Use incremental_usage directly (it's just for this one call, not cumulative)
        cumulative_usage = incremental_usage if incremental_usage else {
            "input": 0,
            "output": 0,
            "completion": 0,
            "reasoning": 0,
            "cache": 0,
            "prompt": 0,
            "total": 0,
            "cost": 0.0,
        }
        
        # Add token usage to each AI message in the response
        # Store the CUMULATIVE usage (not incremental) so frontend can use the latest value
        updated_messages = []
        for msg in response.result:
            if isinstance(msg, AIMessage) or (hasattr(msg, "type") and msg.type == "ai"):
                # Add token usage to response_metadata
                if not hasattr(msg, "response_metadata") or msg.response_metadata is None:
                    msg.response_metadata = {}
                
                # Store the CUMULATIVE usage so frontend can use it immediately
                # The frontend will use the latest value from the most recent message
                msg.response_metadata["token_usage"] = cumulative_usage
            
            updated_messages.append(msg)
        
        # Return response with updated messages
        # The state will be updated in before_agent/after_agent, but response_metadata
        # allows the frontend to read token usage immediately from messages
        return ModelResponse(result=updated_messages)
