"""Raw OpenTelemetry token usage tracker - intercepts HTTP requests directly."""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import httpx

# Log file path - write to project root
_project_root = Path(__file__).parent.parent.parent
LOG_FILE = _project_root / "token_usage.log"

def _write_to_log(message: str):
    """Write message to log file."""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            timestamp = datetime.now().isoformat()
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        print(f"[OpenTelemetryTracker] Failed to write to log file: {e}")


# Track original httpx client methods
_original_httpx_request = None
_original_httpx_stream = None


def setup_httpx_interception():
    """Intercept httpx requests to capture token usage from raw HTTP responses.
    
    This intercepts at the HTTP level, so we get the actual API response
    with token usage before any OpenLIT or LangChain processing.
    """
    global _original_httpx_request, _original_httpx_stream
    
    try:
        import httpx
        
        # Check if already patched
        if hasattr(httpx.Client, '_token_tracker_patched'):
            _write_to_log("httpx already patched, skipping")
            return
        
        # Store original methods
        _original_httpx_request = httpx.Client.request
        _original_httpx_stream = httpx.Client.stream
        
        def patched_request(self, method, url, **kwargs):
            """Intercept HTTP requests to capture token usage."""
            # Only intercept OpenAI-compatible API calls
            if "api.pinkyne.com" in str(url) or "api.openai.com" in str(url) or "/v1/chat/completions" in str(url):
                # Make the original request
                response = _original_httpx_request(self, method, url, **kwargs)
                
                # Try to extract token usage from response
                try:
                    # Read response body
                    response_body = response.content
                    if response_body:
                        response_json = json.loads(response_body)
                        
                        # Extract usage from response
                        usage = response_json.get("usage", {})
                        if usage:
                            prompt_tokens = usage.get("prompt_tokens", 0)
                            completion_tokens = usage.get("completion_tokens", 0)
                            total_tokens = usage.get("total_tokens", 0)
                            
                            # Check for reasoning tokens
                            completion_tokens_details = usage.get("completion_tokens_details", {})
                            reasoning_tokens = completion_tokens_details.get("reasoning_tokens", 0) if completion_tokens_details else 0
                            
                            # Calculate completion tokens (output - reasoning)
                            actual_completion = max(0, completion_tokens - reasoning_tokens)
                            
                            if total_tokens > 0:
                                _write_to_log(
                                    f"HTTP REQUEST - URL: {url} | "
                                    f"Input: {prompt_tokens} | "
                                    f"Output: {completion_tokens} | "
                                    f"Completion: {actual_completion} | "
                                    f"Reasoning: {reasoning_tokens} | "
                                    f"Total: {total_tokens}"
                                )
                                
                                # Also log full response for debugging
                                _write_to_log(f"FULL HTTP RESPONSE: {json.dumps(response_json, indent=2, default=str)}")
                except Exception as e:
                    _write_to_log(f"Error extracting token usage from HTTP response: {e}")
                
                return response
            else:
                # Not an LLM API call, use original method
                return _original_httpx_request(self, method, url, **kwargs)
        
        def patched_stream(self, method, url, **kwargs):
            """Intercept HTTP streaming requests."""
            # For streaming, we need to intercept the response stream
            # This is more complex, so for now just use original
            return _original_httpx_stream(self, method, url, **kwargs)
        
        # Patch the methods
        httpx.Client.request = patched_request
        httpx.Client.stream = patched_stream
        httpx.Client._token_tracker_patched = True
        
        _write_to_log("httpx Client.request patched for token tracking")
        
    except Exception as e:
        _write_to_log(f"Failed to patch httpx: {e}")
        import traceback
        _write_to_log(f"Traceback: {traceback.format_exc()}")


def setup_async_httpx_interception():
    """Intercept async httpx requests."""
    global _original_httpx_request, _original_httpx_stream
    
    try:
        import httpx
        
        # Check if already patched
        if hasattr(httpx.AsyncClient, '_token_tracker_patched'):
            _write_to_log("httpx AsyncClient already patched, skipping")
            return
        
        # Store original methods
        _original_async_request = httpx.AsyncClient.request
        _original_async_stream = httpx.AsyncClient.stream
        
        async def patched_async_request(self, method, url, **kwargs):
            """Intercept async HTTP requests to capture token usage."""
            # Only intercept OpenAI-compatible API calls
            if "api.pinkyne.com" in str(url) or "api.openai.com" in str(url) or "/v1/chat/completions" in str(url):
                # Make the original request
                response = await _original_async_request(self, method, url, **kwargs)
                
                # Try to extract token usage from response
                try:
                    # Read response body
                    response_body = response.content
                    if response_body:
                        response_json = json.loads(response_body)
                        
                        # Extract usage from response
                        usage = response_json.get("usage", {})
                        if usage:
                            prompt_tokens = usage.get("prompt_tokens", 0)
                            completion_tokens = usage.get("completion_tokens", 0)
                            total_tokens = usage.get("total_tokens", 0)
                            
                            # Check for reasoning tokens
                            completion_tokens_details = usage.get("completion_tokens_details", {})
                            reasoning_tokens = completion_tokens_details.get("reasoning_tokens", 0) if completion_tokens_details else 0
                            
                            # Calculate completion tokens (output - reasoning)
                            actual_completion = max(0, completion_tokens - reasoning_tokens)
                            
                            if total_tokens > 0:
                                _write_to_log(
                                    f"HTTP REQUEST (ASYNC) - URL: {url} | "
                                    f"Input: {prompt_tokens} | "
                                    f"Output: {completion_tokens} | "
                                    f"Completion: {actual_completion} | "
                                    f"Reasoning: {reasoning_tokens} | "
                                    f"Total: {total_tokens}"
                                )
                                
                                # Also log full response for debugging
                                _write_to_log(f"FULL HTTP RESPONSE (ASYNC): {json.dumps(response_json, indent=2, default=str)}")
                except Exception as e:
                    _write_to_log(f"Error extracting token usage from async HTTP response: {e}")
                
                return response
            else:
                # Not an LLM API call, use original method
                return await _original_async_request(self, method, url, **kwargs)
        
        async def patched_async_stream(self, method, url, **kwargs):
            """Intercept async HTTP streaming requests."""
            # For streaming, we need to intercept the response stream
            # This is more complex, so for now just use original
            return await _original_async_stream(self, method, url, **kwargs)
        
        # Patch the methods
        httpx.AsyncClient.request = patched_async_request
        httpx.AsyncClient.stream = patched_async_stream
        httpx.AsyncClient._token_tracker_patched = True
        
        _write_to_log("httpx AsyncClient.request patched for token tracking")
        
    except Exception as e:
        _write_to_log(f"Failed to patch async httpx: {e}")
        import traceback
        _write_to_log(f"Traceback: {traceback.format_exc()}")


def setup_opentelemetry_tracking():
    """Set up OpenTelemetry tracking by intercepting HTTP requests.
    
    This is more accurate than OpenLIT because it captures the raw HTTP response
    directly from the API, before any aggregation or parent span processing.
    """
    _write_to_log("Setting up OpenTelemetry HTTP interception for token tracking")
    
    # Intercept both sync and async httpx clients
    setup_httpx_interception()
    setup_async_httpx_interception()
    
    _write_to_log("OpenTelemetry HTTP interception set up successfully")
    _write_to_log("This will capture token usage directly from API responses")

