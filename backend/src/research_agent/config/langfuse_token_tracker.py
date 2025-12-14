"""Langfuse-based token usage tracker that queries the Langfuse API for token usage."""

import asyncio
import os
import time
from typing import Any, Optional
from langfuse import Langfuse, get_client


def get_langfuse_client() -> Optional[Langfuse]:
    """Get Langfuse client if configured."""
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    # Support both LANGFUSE_BASE_URL (standard) and LANGFUSE_HOST (for compatibility)
    base_url = os.environ.get("LANGFUSE_BASE_URL") or os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
    
    if not public_key or not secret_key:
        return None
    
    return Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        base_url=base_url,
    )


def _get_token_usage_from_langfuse_sync(
    trace_id: Optional[str] = None,
    session_id: Optional[str] = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Synchronous implementation of Langfuse API query.
    
    This is wrapped in asyncio.to_thread() to prevent blocking the event loop.
    """
    client = get_langfuse_client()
    if not client:
        return {
            "input": 0,
            "output": 0,
            "completion": 0,
            "reasoning": 0,
            "total": 0,
            "cost": 0.0,
        }
    
    usage = {
        "input": 0,
        "output": 0,
        "completion": 0,
        "reasoning": 0,
        "total": 0,
        "cost": 0.0,
    }
    
    try:
        if trace_id:
            # Query specific trace
            trace = client.api.trace.get(trace_id)
            if trace:
                # Get all generation observations from this trace
                observations = client.api.observations.get_many(
                    trace_id=trace_id,
                    type="GENERATION",
                    limit=limit,
                )
                for obs in observations.data:
                    _add_observation_usage(obs, usage)
        else:
            # Query recent traces (filtered by session_id if provided)
            traces = client.api.trace.list(
                limit=limit,
                session_id=session_id,
            )
            
            # For each trace, get generation observations
            for trace in traces.data:
                observations = client.api.observations.get_many(
                    trace_id=trace.id,
                    type="GENERATION",
                    limit=limit,
                )
                for obs in observations.data:
                    _add_observation_usage(obs, usage)
    
    except Exception as e:
        # Silently fail if Langfuse is not available or query fails
        print(f"[Langfuse Token Tracker] Error querying token usage: {e}")
    
    return usage


async def get_token_usage_from_langfuse(
    trace_id: Optional[str] = None,
    session_id: Optional[str] = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Query Langfuse API to get token usage from traces (async wrapper).
    
    Args:
        trace_id: Specific trace ID to query. If None, queries recent traces.
        session_id: Session ID to filter traces. If None, gets all recent traces.
        limit: Maximum number of traces/observations to query.
    
    Returns:
        Dictionary with token usage: {
            "input": int,
            "output": int,
            "completion": int,
            "reasoning": int,
            "total": int,
            "cost": float,
        }
    """
    # Run the synchronous API calls in a thread to prevent blocking
    return await asyncio.to_thread(
        _get_token_usage_from_langfuse_sync,
        trace_id=trace_id,
        session_id=session_id,
        limit=limit,
    )


def _add_observation_usage(observation: Any, usage: dict[str, Any]) -> None:
    """Extract token usage from a Langfuse observation and add to usage dict.
    
    Args:
        observation: Langfuse observation object (from API response).
        usage: Dictionary to accumulate usage into.
    """
    # Extract usage_details from observation (can be dict or object)
    usage_details = None
    if hasattr(observation, "usage"):
        usage_details = observation.usage
    elif hasattr(observation, "usage_details"):
        usage_details = observation.usage_details
    elif isinstance(observation, dict):
        usage_details = observation.get("usage") or observation.get("usage_details")
    
    # Extract cost_details
    cost_details = None
    if hasattr(observation, "cost"):
        cost_details = observation.cost
    elif hasattr(observation, "cost_details"):
        cost_details = observation.cost_details
    elif isinstance(observation, dict):
        cost_details = observation.get("cost") or observation.get("cost_details")
    
    if not usage_details:
        return
    
    # Convert to dict if it's an object
    if not isinstance(usage_details, dict):
        if hasattr(usage_details, "__dict__"):
            usage_details = usage_details.__dict__
        elif hasattr(usage_details, "dict"):
            usage_details = usage_details.dict()
        else:
            # Try to access common attributes
            usage_details = {
                "input": getattr(usage_details, "input", None) or getattr(usage_details, "input_tokens", None) or getattr(usage_details, "prompt_tokens", None),
                "output": getattr(usage_details, "output", None) or getattr(usage_details, "output_tokens", None) or getattr(usage_details, "completion_tokens", None),
                "total": getattr(usage_details, "total", None) or getattr(usage_details, "total_tokens", None),
            }
    
    # Map Langfuse usage keys to our format
    # Langfuse uses: input, output, prompt_tokens, completion_tokens, etc.
    if isinstance(usage_details, dict):
        # Handle OpenAI-style keys
        input_tokens = (
            usage_details.get("input") or
            usage_details.get("prompt_tokens") or
            usage_details.get("input_tokens") or
            0
        )
        output_tokens = (
            usage_details.get("output") or
            usage_details.get("completion_tokens") or
            usage_details.get("output_tokens") or
            0
        )
        total_tokens = (
            usage_details.get("total") or
            usage_details.get("total_tokens") or
            (input_tokens + output_tokens)
        )
        
        # Handle reasoning tokens (from completion_tokens_details)
        completion_details = usage_details.get("completion_tokens_details") or {}
        if not isinstance(completion_details, dict):
            completion_details = {}
        reasoning_tokens = (
            completion_details.get("reasoning_tokens") or
            usage_details.get("reasoning_tokens") or
            0
        )
        completion_tokens = output_tokens - reasoning_tokens
        
        usage["input"] += int(input_tokens)
        usage["output"] += int(output_tokens)
        usage["completion"] += int(completion_tokens)
        usage["reasoning"] += int(reasoning_tokens)
        usage["total"] += int(total_tokens)
    
    # Extract cost
    if cost_details:
        if isinstance(cost_details, dict):
            # Sum all cost values
            total_cost = sum(
                float(v) for v in cost_details.values() if isinstance(v, (int, float))
            )
            usage["cost"] += total_cost
        elif isinstance(cost_details, (int, float)):
            usage["cost"] += float(cost_details)
        elif hasattr(cost_details, "total"):
            usage["cost"] += float(getattr(cost_details, "total", 0))


def get_token_usage_from_metrics_api(
    from_timestamp: Optional[str] = None,
    to_timestamp: Optional[str] = None,
    session_id: Optional[str] = None,
) -> dict[str, Any]:
    """Query Langfuse Metrics API for aggregated token usage.
    
    This is more efficient than querying individual traces/observations.
    
    Args:
        from_timestamp: ISO timestamp for start of query period.
        to_timestamp: ISO timestamp for end of query period.
        session_id: Optional session ID to filter.
    
    Returns:
        Dictionary with aggregated token usage.
    """
    client = get_langfuse_client()
    if not client:
        return {
            "input": 0,
            "output": 0,
            "completion": 0,
            "reasoning": 0,
            "total": 0,
            "cost": 0.0,
        }
    
    # Default to last hour if no timestamps provided
    if not from_timestamp:
        from_timestamp = (time.time() - 3600)  # 1 hour ago
    if not to_timestamp:
        to_timestamp = time.time()
    
    # Convert to ISO format if needed
    if isinstance(from_timestamp, (int, float)):
        from_timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(from_timestamp))
    if isinstance(to_timestamp, (int, float)):
        to_timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(to_timestamp))
    
    try:
        query = {
            "view": "observations",
            "metrics": [
                {"measure": "usage.input", "aggregation": "sum"},
                {"measure": "usage.output", "aggregation": "sum"},
                {"measure": "usage.total", "aggregation": "sum"},
                {"measure": "cost.total", "aggregation": "sum"},
            ],
            "filters": [
                {"column": "type", "operator": "equals", "value": "GENERATION", "type": "string"},
            ],
            "fromTimestamp": from_timestamp,
            "toTimestamp": to_timestamp,
        }
        
        if session_id:
            query["filters"].append({
                "column": "session_id",
                "operator": "equals",
                "value": session_id,
                "type": "string",
            })
        
        import json
        result = client.api.metrics.metrics(query=json.dumps(query))
        
        # Parse result and return usage
        # Note: Metrics API response structure may vary
        # This is a simplified parser - adjust based on actual API response
        usage = {
            "input": 0,
            "output": 0,
            "completion": 0,
            "reasoning": 0,
            "total": 0,
            "cost": 0.0,
        }
        
        # TODO: Parse metrics API response based on actual structure
        # For now, return empty usage
        
    except Exception as e:
        print(f"[Langfuse Token Tracker] Error querying metrics API: {e}")
        return {
            "input": 0,
            "output": 0,
            "completion": 0,
            "reasoning": 0,
            "total": 0,
            "cost": 0.0,
        }
    
    return usage

