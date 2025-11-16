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
                for span in spans:
                    # Extract token usage from span attributes
                    attrs = dict(span.attributes) if span.attributes else {}
                    
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
                    
                    # Check if this is an LLM-related span
                    is_llm_span = span.name and ("llm" in span.name.lower() or "chat" in span.name.lower() or "openai" in span.name.lower() or "gen_ai" in span.name.lower())
                    
                    if is_llm_span:
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
                        
                        # Determine if this is an actual LLM call
                        is_actual_llm_call = False
                        if output_tokens > 0 and total_tokens > 0:
                            is_actual_llm_call = True
                        elif is_tool_call and input_tokens > 0:
                            is_actual_llm_call = True
                            if output_tokens == 0 and total_tokens > input_tokens:
                                output_tokens = total_tokens - input_tokens
                        elif has_tool_info and input_tokens > 0:
                            is_actual_llm_call = True
                            if output_tokens == 0 and total_tokens > input_tokens:
                                output_tokens = total_tokens - input_tokens
                        elif input_tokens > 0 and total_tokens > 0 and total_tokens > input_tokens:
                            is_actual_llm_call = True
                            output_tokens = total_tokens - input_tokens
                        
                        if is_actual_llm_call:
                            # Calculate cost
                            cost = calculate_custom_cost(model, input_tokens, output_tokens) or 0.0
                            
                            # Get total tokens from client token usage (more accurate)
                            client_total_tokens = (
                                attrs.get("gen_ai.client.token.usage") or
                                attrs.get("llm.client.token.usage") or
                                total_tokens
                            )
                            
                            # Calculate completion tokens (output - reasoning)
                            completion_tokens = max(0, output_tokens - reasoning_tokens)
                            
                            # Store token usage in thread-local storage for middleware to pick up
                            add_token_usage_from_openlit(
                                input_tokens=input_tokens,
                                output_tokens=output_tokens,
                                completion_tokens=completion_tokens,
                                reasoning_tokens=reasoning_tokens,
                                total_tokens=client_total_tokens,
                                cost=cost,
                                model=model,
                            )
                
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
        openlit.init(
            capture_message_content=False,
            # Don't let OpenLIT set up its own tracer provider - we've already set one
            # This prevents OpenLIT from adding a console exporter
        )
        
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
