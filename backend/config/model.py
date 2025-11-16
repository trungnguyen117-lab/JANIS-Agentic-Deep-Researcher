"""Model configuration and initialization."""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional
from langchain_openai import ChatOpenAI

# Path to models.json file (in project root)
_project_root = Path(__file__).parent.parent.parent
MODELS_JSON_PATH = _project_root / "models.json"

# Cache for models data
_MODELS_DATA: Optional[Dict] = None
_AVAILABLE_MODELS: Optional[List[str]] = None


def load_models_config() -> Dict:
    """Load models configuration from models.json file.
    
    Returns:
        Dictionary containing models configuration
    """
    global _MODELS_DATA
    
    if _MODELS_DATA is not None:
        return _MODELS_DATA
    
    if not MODELS_JSON_PATH.exists():
        raise FileNotFoundError(f"Models configuration file not found: {MODELS_JSON_PATH}")
    
    try:
        with open(MODELS_JSON_PATH, "r", encoding="utf-8") as f:
            _MODELS_DATA = json.load(f)
        return _MODELS_DATA
    except Exception as e:
        raise RuntimeError(f"Failed to load models configuration: {e}")


def get_available_models() -> List[str]:
    """Get list of available model names.
    
    Returns:
        List of model names
    """
    global _AVAILABLE_MODELS
    
    if _AVAILABLE_MODELS is not None:
        return _AVAILABLE_MODELS
    
    config = load_models_config()
    models = config.get("models", {})
    _AVAILABLE_MODELS = list(models.keys())
    return _AVAILABLE_MODELS


def get_model_pricing(model_name: str) -> Dict[str, float]:
    """Get pricing for a specific model.
    
    Args:
        model_name: Name of the model
    
    Returns:
        Dictionary with 'input_price_per_million' and 'output_price_per_million'
    """
    config = load_models_config()
    models = config.get("models", {})
    default = config.get("default", {})
    
    model_config = models.get(model_name)
    if model_config:
        return {
            "input_price_per_million": model_config.get("input_price_per_million", default.get("input_price_per_million", 1.0)),
            "output_price_per_million": model_config.get("output_price_per_million", default.get("output_price_per_million", 3.0)),
        }
    
    # Fall back to default pricing
    return {
        "input_price_per_million": default.get("input_price_per_million", 1.0),
        "output_price_per_million": default.get("output_price_per_million", 3.0),
    }


# Export available models list for backward compatibility
# Try to load at module level, but fall back gracefully if models.json doesn't exist
try:
    AVAILABLE_MODELS = get_available_models()
except Exception:
    # Fallback to default list if models.json not found
    AVAILABLE_MODELS = ["gpt-4o", "gpt-3.5-turbo"]


def get_model(model_name: str | None = None):
    """Initialize and return the chat model.
    
    Args:
        model_name: Name of the model to use. If None, uses default from environment
                    or falls back to "gpt-4o". Model name should be one of AVAILABLE_MODELS.
    
    Returns:
        The initialized chat model
    """
    # Get model name from parameter, environment variable, or default
    if model_name is None:
        model_name = os.environ.get("MODEL_NAME", "gpt-4o")
    
    # Validate model name (optional - models.json might not have all models)
    try:
        available_models = get_available_models()
        if model_name not in available_models:
            # If model not in list, try to use it anyway (might be a valid model name)
            pass
    except Exception:
        # If models.json fails to load, continue anyway
        pass
    
    # Use ChatOpenAI directly with OpenAI-compatible interface
    # Langfuse will automatically track token usage via callbacks
    # stream_usage=True is required for LangGraph to capture token usage data
    base_url = os.environ.get("API_BASE_URL", "http://api.pinkyne.com/v1/")
    api_key = os.environ.get("OPENAI_API_KEY")
    
    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0,
        stream_usage=True,  # Required for LangGraph to capture token usage
    )
    
    return llm
