"""Middleware to track token usage in LangGraph state using OpenLIT spans."""

from typing import Any, NotRequired, Annotated, Callable, Awaitable
from langchain.agents.middleware.types import AgentMiddleware, AgentState, ModelRequest, ModelResponse
from langgraph.runtime import Runtime
from langgraph.types import Command, Overwrite
from langchain_core.messages import AIMessage
import threading
import json


# Thread-local storage for token usage updates from OpenLIT spans
_local = threading.local()

# Global cumulative token usage (thread-safe with locks)
_cumulative_usage_lock = threading.Lock()
_cumulative_usage: dict[str, Any] = {
    "input": 0,
    "output": 0,
    "completion": 0,
    "reasoning": 0,
    "total": 0,
    "cost": 0.0,
}



# Current model being used (thread-safe with locks)
_current_model_lock = threading.Lock()
_current_model: str = "unknown"


def _get_usage_list() -> list[dict[str, Any]]:
    """Get thread-local list of token usage updates."""
    if not hasattr(_local, "usage_list"):
        _local.usage_list = []
    return _local.usage_list


def _get_cumulative_usage() -> dict[str, Any]:
    """Get current cumulative token usage (thread-safe)."""
    with _cumulative_usage_lock:
        return _cumulative_usage.copy()


def _update_cumulative_usage(update: dict[str, Any]) -> dict[str, Any]:
    """Update cumulative token usage (thread-safe)."""
    global _cumulative_usage
    with _cumulative_usage_lock:
        _cumulative_usage["input"] += update.get("input", 0)
        _cumulative_usage["output"] += update.get("output", 0)
        _cumulative_usage["completion"] += update.get("completion", 0)
        _cumulative_usage["reasoning"] += update.get("reasoning", 0)
        _cumulative_usage["total"] += update.get("total", 0)
        _cumulative_usage["cost"] += update.get("cost", 0.0)
        return _cumulative_usage.copy()


def add_token_usage_from_openlit(
    input_tokens: int,
    output_tokens: int,
    completion_tokens: int,
    reasoning_tokens: int,
    total_tokens: int,
    cost: float,
    model: str = "unknown",
):
    """Add token usage from OpenLIT span exporter.
    
    This is called by OpenLIT's span exporter when it detects an LLM call.
    Updates both thread-local list (for middleware) and global cumulative usage.
    Also updates the current model being used.
    """
    usage_update = {
        "input": input_tokens,
        "output": output_tokens,
        "completion": completion_tokens,
        "reasoning": reasoning_tokens,
        "total": total_tokens,
        "cost": cost,
    }
    # Add to thread-local list for middleware
    usage_list = _get_usage_list()
    usage_list.append(usage_update)
    
    # Update global cumulative usage (thread-safe)
    _update_cumulative_usage(usage_update)
    
    # Update current model (thread-safe)
    global _current_model
    with _current_model_lock:
        _current_model = model


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
    
    def before_agent(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Initialize token usage in state before agent runs.
        
        This runs before each agent invocation. Since OpenLIT updates cumulative usage
        synchronously when model calls complete, we can get the latest values here.
        This will be called frequently enough to keep the state updated.
        """
        # Get the latest cumulative usage (OpenLIT updates it synchronously after each model call)
        latest_cumulative = _get_cumulative_usage()
        
        # Get current model
        with _current_model_lock:
            current_model = _current_model
        
        # Always return token_usage and current_model in state to ensure it's updated with latest values
        # This will be streamed to the frontend in real-time
        return {"token_usage": latest_cumulative, "current_model": current_model}
    
    def after_agent(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Update token usage in state after agent completes.
        
        This runs after each agent invocation, so after model calls complete.
        OpenLIT updates cumulative usage synchronously, so we can get the latest values here.
        """
        # Get the absolute latest cumulative usage after agent invocation
        # OpenLIT updates synchronously, so if model calls just completed, this will have the latest value
        latest_cumulative = _get_cumulative_usage()
        
        # Get current model
        with _current_model_lock:
            current_model = _current_model
        
        # Update state with latest cumulative usage and current model
        return {"token_usage": latest_cumulative, "current_model": current_model}
    
    async def aafter_agent(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Update token usage in state after agent completes (async version).
        
        This runs after each agent invocation, so after model calls complete.
        OpenLIT updates cumulative usage synchronously, so we can get the latest values here.
        """
        # Get the absolute latest cumulative usage after agent invocation
        # OpenLIT updates synchronously, so if model calls just completed, this will have the latest value
        latest_cumulative = _get_cumulative_usage()
        
        # Get current model
        with _current_model_lock:
            current_model = _current_model
        
        # Update state with latest cumulative usage and current model
        return {"token_usage": latest_cumulative, "current_model": current_model}
    
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Intercept model calls and add token usage to response_metadata.
        
        After the model call completes, OpenLIT updates the cumulative usage synchronously.
        We store the cumulative usage in response_metadata so the frontend can read it immediately.
        The state will also be updated when before_agent runs next (which happens frequently).
        """
        # Call the handler to get the response
        response = await handler(request)
        
        # OpenLIT updates cumulative usage synchronously (SimpleSpanProcessor), so it's already updated
        # Get the latest cumulative usage after the model call
        cumulative_usage = _get_cumulative_usage()
        
        # Note: We can't update state directly from here, but:
        # 1. We store cumulative usage in response_metadata (frontend reads this immediately)
        # 2. before_agent will run again soon and update the state (which streams to frontend)
        
        if not response.result:
            return response
        
        # Try to extract usage from response messages first (from LangChain's usage_metadata)
        total_update = None
        for msg in response.result:
            if isinstance(msg, AIMessage):
                # Check usage_metadata first (LangChain's native field)
                if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                    usage_meta = msg.usage_metadata
                    total_update = {
                        "input": getattr(usage_meta, "input_tokens", 0) or 0,
                        "output": getattr(usage_meta, "output_tokens", 0) or 0,
                        "completion": getattr(usage_meta, "completion_tokens", 0) or 0,
                        "reasoning": getattr(usage_meta, "reasoning_tokens", 0) or 0,
                        "total": getattr(usage_meta, "total_tokens", 0) or 0,
                        "cost": 0.0,  # Will be calculated from OpenLIT if available
                    }
                    break
                
                # Check response_metadata.token_usage as fallback
                if hasattr(msg, "response_metadata") and msg.response_metadata:
                    token_usage = msg.response_metadata.get("token_usage")
                    if token_usage:
                        total_update = {
                            "input": token_usage.get("input_tokens", token_usage.get("input", 0)) or 0,
                            "output": token_usage.get("output_tokens", token_usage.get("output", 0)) or 0,
                            "completion": token_usage.get("completion_tokens", token_usage.get("completion", 0)) or 0,
                            "reasoning": token_usage.get("reasoning_tokens", token_usage.get("reasoning", 0)) or 0,
                            "total": token_usage.get("total_tokens", token_usage.get("total", 0)) or 0,
                            "cost": token_usage.get("cost", 0.0) or 0.0,
                        }
                        break
        
        # If not found in messages, use cumulative usage from OpenLIT (which should have been updated)
        if total_update is None:
            usage_updates = _get_usage_list()
            if usage_updates:
                # Sum all updates (should be from this call)
                total_update = {
                    "input": sum(u.get("input", 0) for u in usage_updates),
                    "output": sum(u.get("output", 0) for u in usage_updates),
                    "completion": sum(u.get("completion", 0) for u in usage_updates),
                    "reasoning": sum(u.get("reasoning", 0) for u in usage_updates),
                    "total": sum(u.get("total", 0) for u in usage_updates),
                    "cost": sum(u.get("cost", 0.0) for u in usage_updates),
                }
                # Clear after using
                usage_updates.clear()
            else:
                # Fallback: use cumulative usage (should have been updated by OpenLIT)
                # This is the total cumulative usage, not just this call
                total_update = cumulative_usage
        
        # Add token usage to each AI message in the response
        # Store the CUMULATIVE usage (not incremental) so frontend can use the latest value
        updated_messages = []
        for msg in response.result:
            if isinstance(msg, AIMessage) or (hasattr(msg, "type") and msg.type == "ai"):
                # Add token usage to response_metadata
                if not hasattr(msg, "response_metadata") or msg.response_metadata is None:
                    msg.response_metadata = {}
                
                # Store the CUMULATIVE usage (from OpenLIT) so frontend can use it
                # The frontend will sum from all messages, but since we're storing cumulative,
                # it should just use the latest value, not sum them
                msg.response_metadata["token_usage"] = cumulative_usage
            
            updated_messages.append(msg)
        
        # Return response with updated messages
        # Note: We can't update state directly from ModelResponse, but before_agent will run
        # on the next agent invocation and will pick up the updated cumulative usage
        return ModelResponse(result=updated_messages)
    
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Intercept model calls (sync version) and add token usage to response_metadata."""
        # Call the handler to get the response
        response = handler(request)
        
        if not response.result:
            return response
        
        # Try to extract usage from response messages first (from LangChain's usage_metadata)
        total_update = None
        for msg in response.result:
            if isinstance(msg, AIMessage):
                # Check usage_metadata first (LangChain's native field)
                if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                    usage_meta = msg.usage_metadata
                    total_update = {
                        "input": getattr(usage_meta, "input_tokens", 0) or 0,
                        "output": getattr(usage_meta, "output_tokens", 0) or 0,
                        "completion": getattr(usage_meta, "completion_tokens", 0) or 0,
                        "reasoning": getattr(usage_meta, "reasoning_tokens", 0) or 0,
                        "total": getattr(usage_meta, "total_tokens", 0) or 0,
                        "cost": 0.0,  # Will be calculated from OpenLIT if available
                    }
                    break
                
                # Check response_metadata.token_usage as fallback
                if hasattr(msg, "response_metadata") and msg.response_metadata:
                    token_usage = msg.response_metadata.get("token_usage")
                    if token_usage:
                        total_update = {
                            "input": token_usage.get("input_tokens", token_usage.get("input", 0)) or 0,
                            "output": token_usage.get("output_tokens", token_usage.get("output", 0)) or 0,
                            "completion": token_usage.get("completion_tokens", token_usage.get("completion", 0)) or 0,
                            "reasoning": token_usage.get("reasoning_tokens", token_usage.get("reasoning", 0)) or 0,
                            "total": token_usage.get("total_tokens", token_usage.get("total", 0)) or 0,
                            "cost": token_usage.get("cost", 0.0) or 0.0,
                        }
                        break
        
        # If not found in messages, check OpenLIT thread-local storage
        if total_update is None:
            usage_updates = _get_usage_list()
            if usage_updates:
                # Sum all updates (should be from this call)
                total_update = {
                    "input": sum(u.get("input", 0) for u in usage_updates),
                    "output": sum(u.get("output", 0) for u in usage_updates),
                    "completion": sum(u.get("completion", 0) for u in usage_updates),
                    "reasoning": sum(u.get("reasoning", 0) for u in usage_updates),
                    "total": sum(u.get("total", 0) for u in usage_updates),
                    "cost": sum(u.get("cost", 0.0) for u in usage_updates),
                }
                # Clear after using
                usage_updates.clear()
        
        # Add token usage to each AI message in the response
        if total_update:
            updated_messages = []
            for msg in response.result:
                if isinstance(msg, AIMessage) or (hasattr(msg, "type") and msg.type == "ai"):
                    # Add token usage to response_metadata
                    if not hasattr(msg, "response_metadata") or msg.response_metadata is None:
                        msg.response_metadata = {}
                    
                    # Store the incremental usage for this call
                    msg.response_metadata["token_usage"] = total_update
                
                updated_messages.append(msg)
            
            # Return response with updated messages
            return ModelResponse(result=updated_messages)
        
        return response
