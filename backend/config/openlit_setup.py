"""OpenLIT setup for automatic token usage tracking."""

import os
import json
from typing import Dict, Optional

# Custom pricing configuration
# Can be set via environment variables or models.json file
# Format: USD per million tokens
# Example: INPUT_TOKEN_PRICE_PER_MILLION=1.25 means $1.25 per million input tokens
CUSTOM_PRICING: Dict[str, Dict[str, float]] = {}


def load_custom_pricing():
    """Load custom pricing from models.json file.
    
    Pricing is loaded from models.json (in project root) which contains both
    model definitions and pricing information.
    
    Environment variables (optional override):
    - INPUT_TOKEN_PRICE_PER_MILLION: Price per million input tokens (default: use models.json)
    - OUTPUT_TOKEN_PRICE_PER_MILLION: Price per million output tokens (default: use models.json)
    """
    global CUSTOM_PRICING
    
    # Try to load from models.json file (in project root)
    try:
        from backend.config.model import load_models_config
        
        config = load_models_config()
        models = config.get("models", {})
        default = config.get("default", {})
        
        # Convert models.json format to CUSTOM_PRICING format
        CUSTOM_PRICING = {}
        for model_name, model_config in models.items():
            CUSTOM_PRICING[model_name] = {
                "input": model_config.get("input_price_per_million", default.get("input_price_per_million", 1.0)),
                "output": model_config.get("output_price_per_million", default.get("output_price_per_million", 3.0)),
            }
        
        # Add default pricing
        CUSTOM_PRICING["default"] = {
            "input": default.get("input_price_per_million", 1.0),
            "output": default.get("output_price_per_million", 3.0),
        }
        
        # Pricing loaded silently
        pass
        return
    except Exception as e:
        # Pricing load failed silently
        pass
    
    # Fallback: Try to load from environment variables
    default_input = os.environ.get("INPUT_TOKEN_PRICE_PER_MILLION")
    default_output = os.environ.get("OUTPUT_TOKEN_PRICE_PER_MILLION")
    
    if default_input or default_output:
        CUSTOM_PRICING["default"] = {}
        if default_input:
            CUSTOM_PRICING["default"]["input"] = float(default_input)
        if default_output:
            CUSTOM_PRICING["default"]["output"] = float(default_output)
        # Pricing loaded from environment variables silently
        pass


def calculate_custom_cost(model: str, input_tokens: int, output_tokens: int) -> Optional[float]:
    """Calculate cost using custom pricing.
    
    Args:
        model: Model name (e.g., "gpt-4o")
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
    
    Returns:
        Cost in USD, or None if no custom pricing is configured
    """
    if not CUSTOM_PRICING:
        return None
    
    # Try to get model-specific pricing
    model_pricing = CUSTOM_PRICING.get(model) or CUSTOM_PRICING.get("default")
    
    if not model_pricing:
        return None
    
    input_price_per_million = model_pricing.get("input", 0)
    output_price_per_million = model_pricing.get("output", 0)
    
    if input_price_per_million == 0 and output_price_per_million == 0:
        return None
    
    # Calculate cost: (tokens / 1,000,000) * price_per_million
    input_cost = (input_tokens / 1_000_000) * input_price_per_million if input_price_per_million > 0 else 0
    output_cost = (output_tokens / 1_000_000) * output_price_per_million if output_price_per_million > 0 else 0
    
    return input_cost + output_cost


def setup_openlit():
    """Initialize OpenLIT for automatic token tracking.
    
    OpenLIT automatically instruments LangChain and tracks token usage.
    We use a custom span exporter to extract token usage and store it in
    thread-local storage for the middleware to update LangGraph state.
    
    Custom pricing can be configured via:
    1. models.json file in project root
    2. Environment variables: INPUT_TOKEN_PRICE_PER_MILLION, OUTPUT_TOKEN_PRICE_PER_MILLION
    """
    # Load custom pricing first
    load_custom_pricing()
    
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
        from backend.deepagents.middleware.token_usage_state import add_token_usage_from_openlit
        
        class OpenLITSpanExporter(SpanExporter):
            """Custom span exporter that extracts token usage from OpenLIT spans and stores it."""
            
            def export(self, spans):
                """Export spans and extract token usage."""
                # Process spans silently - no JSON logging
                # CRITICAL: Suppress any stdout/stderr output to prevent JSON span printing
                import sys
                from io import StringIO
                import threading
                
                # Temporarily suppress stdout/stderr to prevent any JSON printing
                old_stdout = sys.stdout
                old_stderr = sys.stderr
                try:
                    sys.stdout = StringIO()
                    sys.stderr = StringIO()
                    
                    # Set up log file path (outside of stdout/stderr redirection)
                    from pathlib import Path
                    import threading
                    project_root = Path(__file__).parent.parent.parent
                    log_file = project_root / "token_count_debug.log"
                    # Ensure directory exists (do this once, in a thread to avoid blocking)
                    if not log_file.parent.exists():
                        def mkdir_safe():
                            try:
                                log_file.parent.mkdir(parents=True, exist_ok=True)
                            except:
                                pass
                        threading.Thread(target=mkdir_safe, daemon=True).start()
                    
                    # Understand OpenLIT span structure:
                    # - Each span represents either an individual LLM call or an aggregation
                    # - Parent spans may aggregate child spans' token usage
                    # - We need to identify which spans are actual LLM API calls vs aggregations
                    
                    # Build parent-child relationships to identify leaf spans
                    span_children_map = {}
                    for span in spans:
                        span_id = span.context.span_id if hasattr(span.context, 'span_id') else None
                        if span_id:
                            span_children_map[span_id] = []
                    
                    # Build parent-child relationships
                    for span in spans:
                        span_id = span.context.span_id if hasattr(span.context, 'span_id') else None
                        if span_id and span.parent and hasattr(span.parent, 'span_id') and span.parent.span_id:
                            parent_id = span.parent.span_id
                            if parent_id in span_children_map:
                                span_children_map[parent_id].append(span_id)
                    
                    # Identify parent spans (spans that have children)
                    parent_span_ids = {span_id for span_id, children in span_children_map.items() if children}
                    
                    # Track processed spans to prevent double-counting
                    processed_span_ids = set()
                    
                    for span in spans:
                        # Extract token usage from span attributes
                        attrs = dict(span.attributes) if span.attributes else {}
                        
                        # Try to extract thread_id from span attributes or resource attributes
                        # LangGraph/LangChain may set this in various places
                        thread_id = (
                            attrs.get("langgraph.thread_id") or
                            attrs.get("langchain.thread_id") or
                            attrs.get("thread_id") or
                            attrs.get("session_id") or
                            None
                        )
                        # Also check resource attributes
                        if not thread_id and hasattr(span, "resource") and span.resource:
                            resource_attrs = dict(span.resource.attributes) if span.resource.attributes else {}
                            thread_id = (
                                resource_attrs.get("langgraph.thread_id") or
                                resource_attrs.get("langchain.thread_id") or
                                resource_attrs.get("thread_id") or
                                resource_attrs.get("session_id") or
                                None
                            )
                        
                        span_id = span.context.span_id if hasattr(span.context, 'span_id') else None
                        
                        # Skip if already processed (prevent double-counting)
                        if span_id and span_id in processed_span_ids:
                            continue
                        
                        # Skip parent spans - they may aggregate child token usage
                        # Only count leaf spans (spans without children) which are actual LLM calls
                        if span_id and span_id in parent_span_ids:
                            continue
                        
                        # OpenLIT uses specific attribute names for token usage
                        input_tokens = (
                            attrs.get("gen_ai.usage.input_tokens") or
                            attrs.get("llm.usage.input_tokens") or
                            attrs.get("input_tokens") or
                            attrs.get("prompt_tokens") or
                            0
                        )
                        output_tokens = (
                            attrs.get("gen_ai.usage.output_tokens") or
                            attrs.get("llm.usage.output_tokens") or
                            attrs.get("output_tokens") or
                            attrs.get("completion_tokens") or
                            0
                        )
                        total_tokens = (
                            attrs.get("gen_ai.usage.total_tokens") or
                            attrs.get("llm.usage.total_tokens") or
                            attrs.get("total_tokens") or
                            (input_tokens + output_tokens) or
                            0
                        )
                        model = (
                            attrs.get("gen_ai.request.model") or
                            attrs.get("llm.request.model") or
                            attrs.get("model") or
                            "unknown"
                        )
                        
                        # Check if this span has LLM-related attributes
                        # OpenLIT adds gen_ai.* or llm.* attributes to LLM-related spans
                        has_llm_attrs = (
                            "gen_ai.usage.input_tokens" in attrs or
                            "llm.usage.input_tokens" in attrs or
                            "gen_ai.request.model" in attrs or
                            "llm.request.model" in attrs
                        )
                        
                        if not has_llm_attrs:
                            # No LLM attributes - skip this span
                            continue
                        
                        # Check for finish_reasons to identify tool calls
                        finish_reasons = attrs.get("gen_ai.response.finish_reasons") or attrs.get("llm.response.finish_reasons")
                        is_tool_call = False
                        if finish_reasons:
                            if isinstance(finish_reasons, (tuple, list)):
                                is_tool_call = "tool_calls" in str(finish_reasons).lower() or any("tool" in str(r).lower() for r in finish_reasons)
                            else:
                                is_tool_call = "tool_calls" in str(finish_reasons).lower() or "tool" in str(finish_reasons).lower()
                        
                        # Check for tool-related attributes
                        tool_name = attrs.get("gen_ai.tool.name") or attrs.get("llm.tool.name")
                        has_tool_info = tool_name is not None
                        
                        # Extract reasoning tokens
                        completion_tokens_details = attrs.get("gen_ai.usage.completion_tokens_details") or attrs.get("llm.usage.completion_tokens_details") or {}
                        if isinstance(completion_tokens_details, dict):
                            reasoning_tokens = completion_tokens_details.get("reasoning_tokens", 0)
                        else:
                            reasoning_tokens = 0
                        
                        # Determine if this span represents an actual LLM API call
                        # OpenLIT attributes should contain the actual token counts for this specific call
                        # If this is a leaf span (no children), it's an actual LLM call
                        # If it has children, it's an aggregation span and we should skip it
                        
                        # Check if we have valid token usage data
                        has_token_data = (
                            (input_tokens > 0 or output_tokens > 0) and
                            total_tokens > 0
                        )
                        
                        if not has_token_data:
                            # No token data - skip this span
                            continue
                        
                        # For tool calls, output_tokens might be 0, but we can calculate from total
                        if is_tool_call and output_tokens == 0 and total_tokens > input_tokens:
                            output_tokens = total_tokens - input_tokens
                        
                        # For spans with input and total but no explicit output, calculate output
                        if output_tokens == 0 and total_tokens > input_tokens:
                            output_tokens = total_tokens - input_tokens
                        
                        # Only process if we have meaningful token counts
                        if input_tokens > 0 or output_tokens > 0:
                            # Mark as processed to prevent double-counting
                            if span_id:
                                processed_span_ids.add(span_id)
                            
                            # Determine if this is a tool call or completion
                            call_type = "tool_call" if (is_tool_call or has_tool_info) else "completion"
                            
                            # Get tool name if available (tool_name was extracted earlier)
                            tool_name_str = tool_name if tool_name else "N/A"
                            
                            # Log to debug file: model, input, output, call_type, tool_name
                            # Write directly to file in a thread to avoid blocking
                            def write_log_entry():
                                try:
                                    with open(log_file, "a", encoding="utf-8") as f:
                                        f.write(f"{model},{input_tokens},{output_tokens},{call_type},{tool_name_str}\n")
                                        f.flush()  # Force write immediately
                                except Exception as e:
                                    # Write error to file directly (bypassing stdout/stderr redirection)
                                    try:
                                        with open(log_file, "a", encoding="utf-8") as f:
                                            f.write(f"# ERROR: Failed to log: {e}\n")
                                    except:
                                        pass
                            
                            # Write in a daemon thread to avoid blocking
                            threading.Thread(target=write_log_entry, daemon=True).start()
                            
                            # Understand OpenLIT's token counting:
                            # - gen_ai.usage.input_tokens / output_tokens: tokens for THIS specific span
                            # - gen_ai.client.token.usage: may be aggregated across multiple spans
                            # We want to use the span-specific counts, not aggregated client totals
                            
                            # Use the span's individual token counts (gen_ai.usage.*)
                            # These should represent the actual tokens for this specific LLM call
                            span_total_tokens = input_tokens + output_tokens
                            
                            # Check if client token usage exists and if it matches the span's usage
                            # If client usage is much higher, it's likely aggregated - don't use it
                            client_total_tokens = (
                                attrs.get("gen_ai.client.token.usage") or
                                attrs.get("llm.client.token.usage") or
                                0
                            )
                            
                            # Use span's individual token counts as the source of truth
                            # Only use client_total_tokens if it's close to our calculated total
                            # (within reasonable margin, suggesting it's for this span, not aggregated)
                            if client_total_tokens > 0 and abs(client_total_tokens - span_total_tokens) < span_total_tokens * 0.1:
                                # Client total is close to span total - likely for this span
                                final_total_tokens = client_total_tokens
                            else:
                                # Use calculated total from span's individual counts
                                final_total_tokens = span_total_tokens
                            
                            # Calculate cost using the span's individual token counts
                            cost = calculate_custom_cost(model, input_tokens, output_tokens) or 0.0
                            
                            # Calculate completion tokens (output - reasoning)
                            completion_tokens = max(0, output_tokens - reasoning_tokens)
                            
                            # Store token usage - using individual span's counts, not aggregated totals
                            # Pass thread_id if we found it in span attributes
                            add_token_usage_from_openlit(
                                input_tokens=input_tokens,
                                output_tokens=output_tokens,
                                completion_tokens=completion_tokens,
                                reasoning_tokens=reasoning_tokens,
                                total_tokens=final_total_tokens,
                                cost=cost,
                                model=model,
                                thread_id=thread_id,
                            )
                finally:
                    # Restore stdout/stderr
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr
                
                return SpanExportResult.SUCCESS
            
            def shutdown(self):
                """Shutdown exporter."""
                pass
        
        # Set up custom exporter BEFORE initializing OpenLIT
        # Use SimpleSpanProcessor for synchronous export (immediate token tracking)
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        
        # Disable OpenTelemetry console logging FIRST to prevent full span JSON from being logged
        import logging
        import os
        
        # Set environment variable to disable OpenTelemetry Python logging
        os.environ.setdefault("OTEL_PYTHON_LOG_LEVEL", "ERROR")
        
        # Disable all OpenTelemetry loggers
        logging.getLogger("opentelemetry").setLevel(logging.ERROR)
        logging.getLogger("opentelemetry.sdk").setLevel(logging.ERROR)
        logging.getLogger("opentelemetry.trace").setLevel(logging.ERROR)
        logging.getLogger("opentelemetry.trace.span").setLevel(logging.ERROR)
        logging.getLogger("opentelemetry.sdk.trace.export").setLevel(logging.ERROR)
        logging.getLogger("opentelemetry.sdk.trace.export.console").setLevel(logging.ERROR)
        
        # Disable OpenLIT's internal logging
        logging.getLogger("openlit").setLevel(logging.ERROR)
        
        # Create provider with ONLY our custom exporter (no console exporter)
        provider = TracerProvider()
        exporter = OpenLITSpanExporter()
        processor = SimpleSpanProcessor(exporter)  # Synchronous export
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        
        # Now initialize OpenLIT (it will use our custom provider)
        # Disable content logging to prevent full prompts/responses from being logged
        # IMPORTANT: We set the tracer provider BEFORE OpenLIT init, so OpenLIT will use our provider
        # and won't add its own console exporter
        import openlit
        import sys
        from io import StringIO
        
        # Temporarily suppress stdout/stderr during OpenLIT init to prevent any console output
        # OpenLIT might print spans to console if not configured properly
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        try:
            # Redirect stdout/stderr to suppress any console output from OpenLIT
            sys.stdout = StringIO()
            sys.stderr = StringIO()
            
            openlit.init(
                capture_message_content=False,
                disable_batch=True,  # Disable batch processing to prevent console output
                # Don't let OpenLIT set up its own tracer provider - we've already set one
                # This prevents OpenLIT from adding a console exporter
            )
        finally:
            # Restore stdout/stderr
            sys.stdout = old_stdout
            sys.stderr = old_stderr
        
        # Ensure OpenLIT uses our provider (it should already, but double-check)
        current_provider = trace.get_tracer_provider()
        if current_provider != provider:
            # If OpenLIT changed the provider, set it back to ours
            trace.set_tracer_provider(provider)
        
        return True
    except ImportError as e:
        print(f"[OpenLIT] ERROR: Missing dependency: {e}")
        print("[OpenLIT] Run: uv add openlit opentelemetry-api opentelemetry-sdk")
        return False
    except Exception as e:
        print(f"[OpenLIT] ERROR: Failed to initialize OpenLIT: {e}")
        import traceback
        traceback.print_exc()
        return False


def setup_custom_exporter():
    """Set up custom exporter (called before OpenLIT init)."""
    # This is now handled in setup_openlit()
    return True
