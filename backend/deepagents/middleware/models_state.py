"""Middleware to add available models list to agent state."""

from typing import Any
from langchain.agents.middleware.types import AgentMiddleware, AgentState
from langgraph.runtime import Runtime
from backend.config.model import load_models_config


class ModelsStateMiddleware(AgentMiddleware):
    """Middleware that adds available models list to agent state."""
    
    def __init__(self):
        """Initialize middleware."""
        super().__init__()
    
    def before_agent(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Update models list in state before agent runs."""
        try:
            config = load_models_config()
            models = config.get("models", {})
            
            # Extract model names and pricing
            models_list = []
            for model_name, model_config in models.items():
                models_list.append({
                    "name": model_name,
                    "input_price_per_million": model_config.get("input_price_per_million"),
                    "output_price_per_million": model_config.get("output_price_per_million"),
                })
            
            # Models loaded silently
            # Return state update
            return {"available_models": models_list}
        except Exception as e:
            # If models.json fails to load, return empty list
            # Models load failed silently
            return {"available_models": []}

