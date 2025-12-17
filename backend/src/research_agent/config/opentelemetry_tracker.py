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
            url_str = str(url)
            # Log all requests to see what URLs we're getting
            _write_to_log(f"HTTP REQUEST INTERCEPTED - Method: {method} | URL: {url_str}")
            
            # Only intercept OpenAI-compatible API calls
            is_llm_call = (
                "api.pinkyne.com" in url_str or 
                "api.openai.com" in url_str or 
                "/v1/chat/completions" in url_str or
                "openai" in url_str.lower() or
                "chat/completions" in url_str.lower()
            )
            
            if is_llm_call:
                _write_to_log(f"LLM API call detected: {url_str}")
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
                                # Extract model name from request or response
                                model = response_json.get("model", "unknown")
                                
                            # Calculate cost (will be done by middleware, but we can log it)
                            from .openlit_setup import calculate_custom_cost
                                cost = calculate_custom_cost(model, prompt_tokens, completion_tokens) or 0.0
                                
                                _write_to_log(
                                    f"HTTP REQUEST - Model: {model} | URL: {url} | "
                                    f"Input: {prompt_tokens} | "
                                    f"Output: {completion_tokens} | "
                                    f"Completion: {actual_completion} | "
                                    f"Reasoning: {reasoning_tokens} | "
                                    f"Total: {total_tokens} | "
                                    f"Cost: ${cost:.6f}"
                                )
                                
                                # Token usage tracking disabled (deepagents removed)
                                # try:
                                #     from backend.deepagents.middleware.token_usage_state import add_token_usage_from_openlit
                                #     add_token_usage_from_openlit(
                                #         input_tokens=prompt_tokens,
                                #         output_tokens=completion_tokens,
                                #         completion_tokens=actual_completion,
                                #         reasoning_tokens=reasoning_tokens,
                                #         total_tokens=total_tokens,
                                #         cost=cost,
                                #         model=model,
                                #     )
                                # except Exception as e:
                                #     logger.warning(f"Failed to add token usage from OpenLIT: {e}")
                                
                                # Also write to debug log (same format as OpenLIT)
                                try:
                                    debug_log_file = _project_root / "token_count_debug.log"
                                    # Determine call type from response
                                    finish_reason = response_json.get("choices", [{}])[0].get("finish_reason", "stop")
                                    call_type = "tool_call" if finish_reason == "tool_calls" else "completion"
                                    tool_name = "N/A"
                                    if call_type == "tool_call":
                                        # Try to get tool name from response
                                        tool_calls = response_json.get("choices", [{}])[0].get("message", {}).get("tool_calls", [])
                                        if tool_calls:
                                            tool_name = tool_calls[0].get("function", {}).get("name", "N/A")
                                    
                                    with open(debug_log_file, "a", encoding="utf-8") as f:
                                        f.write(f"{model},{prompt_tokens},{completion_tokens},{call_type},{tool_name}\n")
                                except Exception:
                                    pass  # Silently fail debug logging
                                except Exception as e:
                                    _write_to_log(f"Failed to add token usage to state: {e}")
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
            url_str = str(url)
            # Log all requests to see what URLs we're getting
            _write_to_log(f"HTTP REQUEST INTERCEPTED (ASYNC) - Method: {method} | URL: {url_str}")
            
            # Only intercept OpenAI-compatible API calls
            is_llm_call = (
                "api.pinkyne.com" in url_str or 
                "api.openai.com" in url_str or 
                "/v1/chat/completions" in url_str or
                "openai" in url_str.lower() or
                "chat/completions" in url_str.lower()
            )
            
            if is_llm_call:
                _write_to_log(f"LLM API call detected (ASYNC): {url_str}")
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
                                # Extract model name from request or response
                                model = response_json.get("model", "unknown")
                                
                                # Calculate cost (will be done by middleware, but we can log it)
                                from .openlit_setup import calculate_custom_cost
                                cost = calculate_custom_cost(model, prompt_tokens, completion_tokens) or 0.0
                                
                                _write_to_log(
                                    f"HTTP REQUEST (ASYNC) - Model: {model} | URL: {url} | "
                                    f"Input: {prompt_tokens} | "
                                    f"Output: {completion_tokens} | "
                                    f"Completion: {actual_completion} | "
                                    f"Reasoning: {reasoning_tokens} | "
                                    f"Total: {total_tokens} | "
                                    f"Cost: ${cost:.6f}"
                                )
                                
                                # Token usage tracking disabled (deepagents removed)
                                # try:
                                #     from backend.deepagents.middleware.token_usage_state import add_token_usage_from_openlit
                                #     add_token_usage_from_openlit(
                                #         input_tokens=prompt_tokens,
                                #         output_tokens=completion_tokens,
                                #         completion_tokens=actual_completion,
                                #         reasoning_tokens=reasoning_tokens,
                                #         total_tokens=total_tokens,
                                #         cost=cost,
                                #         model=model,
                                #     )
                                # except Exception as e:
                                #     logger.warning(f"Failed to add token usage from OpenLIT: {e}")

                                # Also write to debug log (same format as OpenLIT)
                                try:
                                    debug_log_file = _project_root / "token_count_debug.log"
                                    # Determine call type from response
                                    finish_reason = response_json.get("choices", [{}])[0].get("finish_reason", "stop")
                                    call_type = "tool_call" if finish_reason == "tool_calls" else "completion"
                                    tool_name = "N/A"
                                    if call_type == "tool_call":
                                        # Try to get tool name from response
                                        tool_calls = response_json.get("choices", [{}])[0].get("message", {}).get("tool_calls", [])
                                        if tool_calls:
                                            tool_name = tool_calls[0].get("function", {}).get("name", "N/A")
                                    
                                    with open(debug_log_file, "a", encoding="utf-8") as f:
                                        f.write(f"{model},{prompt_tokens},{completion_tokens},{call_type},{tool_name}\n")
                                except Exception:
                                    pass  # Silently fail debug logging
                                except Exception as e:
                                    _write_to_log(f"Failed to add token usage to state: {e}")
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
    
    # Also try to patch OpenAI SDK's HTTP client directly
    # LangChain's ChatOpenAI uses OpenAI SDK, which creates its own httpx clients
    try:
        import openai
        # OpenAI SDK uses httpx internally, but creates clients dynamically
        # We need to patch at the httpx level, which we already did
        # But also try to patch OpenAI's client creation if possible
        _write_to_log("OpenAI SDK detected - httpx patching should intercept its calls")
        
        # Try to patch OpenAI's default httpx client if it exists
        if hasattr(openai, '_client'):
            _write_to_log("OpenAI SDK has _client attribute")
    except ImportError:
        _write_to_log("OpenAI SDK not found - using httpx patching only")
    except Exception as e:
        _write_to_log(f"Note about OpenAI SDK: {e}")
    
    _write_to_log("OpenTelemetry HTTP interception set up successfully")
    _write_to_log("This will capture token usage directly from API responses")
    _write_to_log("All HTTP requests will be logged to help debug if interception is working")
    _write_to_log("If no requests appear in logs, httpx patching may not be intercepting LangChain's calls")

